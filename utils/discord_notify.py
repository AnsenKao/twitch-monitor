import requests

WEBHOOK_URL = "https://discord.com/api/webhooks/1516286271452872715/RIEvn5KR898gha9TMtjE0EIxYuE3D8xKXxmC7GFAm-51BcPurlOBt_i8OwnH89toXRus"


def send_discord(message: str) -> None:
    try:
        requests.post(WEBHOOK_URL, json={"content": message}, timeout=10)
    except Exception as e:
        print(f"Discord 通知發送失敗: {e}")
