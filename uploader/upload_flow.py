from uploader import YouTubeUploader
from utils import setup_logger

logger = setup_logger("log")


class UploadFlow:
    def __init__(self):
        self.client_secrets_file = "client_secret.json"
        self.scopes = [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.force-ssl",
        ]
        self.credentials_file = "credentials.pkl"
        self.uploader = YouTubeUploader(
            self.client_secrets_file, self.scopes, self.credentials_file
        )

    def upload(self, video_file, title, description, playlist_id=None):
        try:
            logger.info("Starting upload process...")
            self.uploader.upload_video(
                video_file, title, description, "22", ["Ansen", "Shoto"], playlist_id
            )
            logger.info(f"Upload {title} successful!")
        except Exception as e:
            logger.error(f"An error occurred during upload: {e}")


if __name__ == "__main__":
    upload_flow = UploadFlow()
    upload_flow.upload(
        r"E:\Projects\twitch-monitor\downloaded_video.mp4", "Ansen is handsome", "test"
    )
