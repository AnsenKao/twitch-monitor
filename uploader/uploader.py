import os
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pickle


class YouTubeUploader:
    def __init__(self, client_secrets_file, scopes, credentials_file):
        self.client_secrets_file = client_secrets_file
        self.scopes = scopes
        self.credentials_file = credentials_file
        self.credentials = None
        self.youtube = None
        self.authenticate()

    def authenticate(self):
        """ 授權並獲取 YouTube API Token """
        # 1️⃣ 嘗試讀取 `credentials.pkl`
        if os.path.exists(self.credentials_file):
            try:
                with open(self.credentials_file, "rb") as token:
                    self.credentials = pickle.load(token)
                print("✅ 成功讀取 credentials.pkl")
            except Exception as e:
                print(f"⚠️ 無法讀取 credentials.pkl: {e}")
                self.credentials = None  # 確保無效的 token 不會影響判斷

        # 2️⃣ 嘗試刷新 `access_token`
        if self.credentials and self.credentials.expired:
            if self.credentials.refresh_token:
                try:
                    print("🔄 正在刷新 access token...")
                    self.credentials.refresh(Request())
                    print("✅ access token 刷新成功")
                except Exception as e:
                    print(f"❌ 無法刷新 token: {e}，需要重新登入")
                    self.get_new_credentials()  # 強制重新登入
            else:
                print("❌ 沒有 refresh token，必須重新登入")
                self.get_new_credentials()  # 強制重新登入

        # 3️⃣ 儲存 `credentials.pkl`
        with open(self.credentials_file, "wb") as token:
            pickle.dump(self.credentials, token)
        print("✅ credentials.pkl 已更新")

        # 4️⃣ 建立 YouTube API 連線
        self.youtube = build("youtube", "v3", credentials=self.credentials)

    def get_new_credentials(self):
        """ 強制重新登入並獲取新的 token """
        flow = InstalledAppFlow.from_client_secrets_file(
            self.client_secrets_file, self.scopes
        )
        self.credentials = flow.run_local_server(port=8080, access_type="offline", prompt="consent")

        # 確保 refresh_token 被存儲
        if not self.credentials.refresh_token:
            print("⚠️ 警告: Google 沒有提供 refresh_token，這可能導致需要頻繁登入！")
        else:
            print("✅ 獲取到 refresh_token，可以自動刷新 token")

        with open(self.credentials_file, "wb") as token:
            pickle.dump(self.credentials, token)
        print("✅ 已儲存新的 credentials.pkl")

    def upload_video(
        self, file_path, title, description, category_id, tags, playlist_id=None
    ):
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id,
                "defaultLanguage": "zh-TW",
            },
            "status": {"privacyStatus": "private", "madeForKids": False},
        }

        media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
        request = self.youtube.videos().insert(
            part="snippet,status", body=body, media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")

        print(f"Upload Complete! Video ID: {response['id']}")

        if playlist_id:
            self.add_video_to_playlist(response["id"], playlist_id)

    def add_video_to_playlist(self, video_id, playlist_id):
        body = {
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id,
                },
            }
        }

        request = self.youtube.playlistItems().insert(part="snippet", body=body)

        response = request.execute()
        print(f"Video added to playlist! Playlist Item ID: {response['id']}")


if __name__ == "__main__":
    CLIENT_SECRETS_FILE = r"E:\Projects\twitch-monitor\client_secret.json"
    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.force-ssl",
    ]
    CREDENTIALS_FILE = r"E:\Projects\twitch-monitor\credentials.pkl"

    uploader = YouTubeUploader(CLIENT_SECRETS_FILE, SCOPES, CREDENTIALS_FILE)
    # uploader.upload_video(
    #     r"E:\Projects\twitch-monitor\downloaded_video.mp4",
    #     "Ansen is handsome",
    #     "test",
    #     "22",
    #     ["Ansen", "Shoto"],
    # )
    uploader.add_video_to_playlist("OC5PBE51Y9A", "PLCqOEsFJbTpCI6bJplqSfmHMsEUupPw3i")
