import os

import requests

from .logger import setup_logger

WEBHOOK_ENV_KEY = "DISCORD_WEBHOOK"

logger = setup_logger("log")


def send_discord(message: str) -> None:
    # 延遲讀取：main.py 的 load_dotenv() 在 import flows 之後才執行，
    # 在 module 層讀會拿到 None。
    webhook_url = os.getenv(WEBHOOK_ENV_KEY)
    if not webhook_url:
        logger.error(f"未設定 {WEBHOOK_ENV_KEY}，略過 Discord 通知：{message}")
        return
    try:
        resp = requests.post(webhook_url, json={"content": message}, timeout=10)
    except Exception as e:
        logger.error(f"Discord 通知發送失敗（連線錯誤）：{e}")
        return
    # 失效的 webhook 會回 401/404 而不是拋例外，不檢查狀態碼的話通知會靜默失敗。
    if resp.status_code >= 400:
        logger.error(
            f"Discord 通知發送失敗（HTTP {resp.status_code}）：{resp.text[:200]}"
        )


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
