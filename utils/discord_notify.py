import os

import requests

WEBHOOK_ENV_KEY = "DISCORD_WEBHOOK"


def send_discord(message: str) -> None:
    # 延遲讀取：main.py 的 load_dotenv() 在 import flows 之後才執行，
    # 在 module 層讀會拿到 None。
    webhook_url = os.getenv(WEBHOOK_ENV_KEY)
    if not webhook_url:
        print(f"未設定 {WEBHOOK_ENV_KEY}，略過 Discord 通知：{message}")
        return
    try:
        requests.post(webhook_url, json={"content": message}, timeout=10)
    except Exception as e:
        print(f"Discord 通知發送失敗: {e}")


def format_yt_links(yt_urls, names=None) -> str:
    if not yt_urls:
        return "（無 YouTube 連結）"
    if len(yt_urls) == 1:
        return f"YouTube：{yt_urls[0]}"
    # names 由呼叫端與 yt_urls 一一對應地累積，長度不符時退回純連結列表
    if names and len(names) == len(yt_urls):
        return "\n".join(
            f"YouTube ({i + 1})：{n}\n{u}"
            for i, (n, u) in enumerate(zip(names, yt_urls))
        )
    return "\n".join(f"YouTube ({i + 1})：{u}" for i, u in enumerate(yt_urls))
