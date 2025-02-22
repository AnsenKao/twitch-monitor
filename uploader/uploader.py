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
        if os.path.exists(self.credentials_file):
            with open(self.credentials_file, "rb") as token:
                self.credentials = pickle.load(token)

        if not self.credentials or not self.credentials.valid:
            if (
                self.credentials
                and self.credentials.expired
                and self.credentials.refresh_token
            ):
                self.credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.client_secrets_file, self.scopes
                )
                flow.redirect_uri = "http://localhost:8080/"  # 確保這裡的 URI 與 Google Cloud Console 中設定的一致
                self.credentials = flow.run_local_server(port=8080)

            with open(self.credentials_file, "wb") as token:
                pickle.dump(self.credentials, token)

        self.youtube = build("youtube", "v3", credentials=self.credentials)

    def upload_video(self, file_path, title, description, category_id, tags):
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


if __name__ == "__main__":
    CLIENT_SECRETS_FILE = r"E:\Projects\twitch-monitor\client_secret.json"
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    CREDENTIALS_FILE = r"E:\Projects\twitch-monitor\credentials.pkl"

    uploader = YouTubeUploader(CLIENT_SECRETS_FILE, SCOPES, CREDENTIALS_FILE)
    uploader.upload_video(
        r"E:\Projects\twitch-monitor\downloaded_video.mp4",
        "Ansen is handsome",
        "test",
        "22",
        ["Ansen", "Shoto"],
    )
