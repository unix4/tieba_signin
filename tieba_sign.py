# -*- coding: utf8 -*-
"""
Tieba 自动签到脚本（Telegram 推送版）
================================================
一次性配置区（最简用法）
------------------------
获取百度账户 BDUSS、Telegram BOT_TOKEN 和 CHAT_ID
* `BDUSS_FALLBACK` —— 必填，支持单账号或多个 BDUSS，用英文逗号 `,` 分隔。（f12获取）
* `BOT_TOKEN` —— Telegram Bot Token，可在 [@BotFather](https://t.me/BotFather) 获取。
* `CHAT_ID` —— Telegram Chat ID，可通过 `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates` 或 `@userinfobot` 查询。

> **覆写逻辑**：脚本会先读取环境变量 `TIEBA_BDUSS`、`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`；
"""

import os
from requests import session, post
from hashlib import md5
import pretty_errors

# -------------------------- 配置变量 --------------------------
BDUSS_FALLBACK = ""  # ← 在此粘贴 BDUSS，多账号用英文逗号分隔
BOT_TOKEN      = ""  # ← 在此粘贴 Telegram Bot Token
CHAT_ID        = ""  # ← 在此粘贴 Telegram Chat ID

# 若设置了环境变量，将覆盖上方值
BDUSS_SOURCE = os.getenv("TIEBA_BDUSS")        or BDUSS_FALLBACK
BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN") or BOT_TOKEN
CHAT_ID      = os.getenv("TELEGRAM_CHAT_ID")   or CHAT_ID

BDUSS_LIST = [bd.strip() for bd in BDUSS_SOURCE.split(",") if bd.strip()]

# ------------------------ Telegram 推送 ------------------------

def send_telegram(msg: str):
    """使用 Telegram Bot 发送 Markdown 消息"""
    if not (BOT_TOKEN and CHAT_ID):
        print("未配置 Telegram Bot Token / Chat ID，跳过推送…")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = post(url, data={
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown"
    })
    if resp.status_code == 200 and resp.json().get("ok"):
        print("Telegram 推送成功")
    else:
        print("Telegram 推送失败：", resp.text)


# -------------------------- Tieba 核心 --------------------------
class Tieba:
    def __init__(self, BDUSS: str):
        self.BDUSS = BDUSS.strip()
        self.success_list, self.sign_list, self.fail_list = [], [], []
        self.result = {}
        self.session = session()
        self.session.headers.update({
            "Accept": "text/html, */*; q=0.01",
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Host": "tieba.baidu.com",
            "Referer": "http://tieba.baidu.com/i/i/forum",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/71.0.3578.98 Safari/537.36"
            ),
            "X-Requested-With": "XMLHttpRequest",
        })

    # ---------------------- 内部工具 ----------------------
    def set_cookie(self):
        """仅需设置 BDUSS cookie"""
        self.session.cookies.update({"BDUSS": self.BDUSS})

    def fetch_tbs(self):
        r = self.session.get("http://tieba.baidu.com/dc/common/tbs").json()
        if r.get("is_login") == 1:
            self.tbs = r["tbs"]
        else:
            raise RuntimeError("获取 tbs 失败！返回数据：" + str(r))

    def fetch_likes(self):
        self.rest, self.already = set(), set()
        r = self.session.get("https://tieba.baidu.com/mo/q/newmoindex?").json()
        if r.get("no") == 0:
            for forum in r["data"].get("like_forum", []):
                (self.already if forum["is_sign"] == 1 else self.rest).add(
                    forum["forum_name"]
                )
        else:
            raise RuntimeError("获取关注贴吧失败！返回数据：" + str(r))

    def sign(self, forum_name: str) -> bool:
        data = {
            "kw": forum_name,
            "tbs": self.tbs,
            "sign": md5(f"kw={forum_name}tbs={self.tbs}tiebaclient!!!".encode()).hexdigest(),
        }
        r = self.session.post("http://c.tieba.baidu.com/c/c/forum/sign", data=data).json()
        if r.get("error_code") == "160002":
            print(f"\"{forum_name}\" 已签到")
            self.sign_list.append(forum_name)
            return True
        elif r.get("error_code") == "0":
            rank = r["user_info"]["user_sign_rank"]
            print(f"\"{forum_name}\" >>>>>> 签到成功，第 {rank} 个签到！")
            self.result[forum_name] = r
            self.success_list.append(forum_name)
            return True
        else:
            print(f"\"{forum_name}\" 签到失败！返回数据：{r}")
            self.fail_list.append(forum_name)
            return False

    # ---------------------- 逻辑控制 ----------------------
    def loop(self, n: int):
        print(f"* 开始第 {n} 轮签到 *")
        self.fetch_tbs()
        rest = set()
        for forum_name in self.rest:
            if not self.sign(forum_name):
                rest.add(forum_name)
        self.rest = rest
        if n >= 10:
            self.rest.clear()

    def main(self, retry: int = 3):
        self.set_cookie()
        self.fetch_likes()
        n = 0
        if self.already:
            print("---------- 已签到的贴吧 ----------")
            for f in self.already:
                print(f"\"{f}\" 已签到")
                self.sign_list.append(f)
        while n < retry and self.rest:
            n += 1
            self.loop(n)

        if self.rest:
            print("--------- 签到失败列表 ----------")
            for f in self.rest:
                print(f"\"{f}\" 签到失败！")


# -------------------------- 入口 --------------------------
if __name__ == "__main__":
    if not BDUSS_LIST:
        raise SystemExit("未检测到 BDUSS，请在顶部 BDUSS_FALLBACK 或环境变量 TIEBA_BDUSS 中设置！")

    for bduss in BDUSS_LIST:
        print("\n========================\n")
        task = Tieba(bduss)
        task.main(3)

        total = len(task.already) + len(task.success_list) + len(task.fail_list)
        msg = (
            f"共关注了 {total} 个贴吧，本次成功签到 {len(task.success_list)} 个，"
            f"失败 {len(task.fail_list)} 个，已有 {len(task.sign_list)} 个贴吧签到。\n\n"
        )

        if task.success_list:
            msg += "*签到成功贴吧*: \n" + "\n".join(
                [f"- {f} (第 {task.result[f]['user_info']['user_sign_rank']} 个)" for f in task.success_list]
            ) + "\n\n"
        if task.fail_list:
            msg += "*签到失败贴吧*: \n" + "\n".join([f"- {f}" for f in task.fail_list]) + "\n\n"
        if task.sign_list:
            msg += "*已签到贴吧*: \n" + "\n".join([f"- {f}" for f in task.sign_list])

        send_telegram(msg)
