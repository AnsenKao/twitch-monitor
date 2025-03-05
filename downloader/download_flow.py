from downloader import YTDLPDownloader
from utils import setup_logger
import os

logger = setup_logger("log")


class DownloadFlow:
    def __init__(self, all_items):
        # 修正檔名並使用絕對路徑
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.yt_dlp_path = os.path.join(self.current_dir, "yt-dlp.exe")
        self.all_items = all_items
        self.downloader = YTDLPDownloader(self.yt_dlp_path)

    def download(self):
        for key, value in self.all_items.items():
            self.path = os.path.join(self.current_dir, "videos", f"{key}.mp4")
            try:
                # 將 path 傳給 download_video 方法
                success = self.downloader.download_video(value, self.path)
                if success:
                    logger.info(f"{value} has been downloaded to {self.path}")
                else:
                    logger.error(f"Failed to download {value}")
            except Exception as e:
                logger.error(f"Error downloading {value}: {str(e)}")

    def run(self):
        self.download()
