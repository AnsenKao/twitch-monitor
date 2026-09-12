from downloader import YTDLPDownloader
from utils import get_logger, sanitize_filename
from utils.video_processor import VideoProcessor
import os
import time

logger = get_logger(__name__)


class DownloadFlow:
    def __init__(self, all_items):
        # 修正檔名並使用絕對路徑
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.yt_dlp_path = os.path.join(self.current_dir, "yt-dlp.exe")
        self.all_items = all_items
        self.downloader = YTDLPDownloader(self.yt_dlp_path)
        self.video_processor = VideoProcessor()

    def download(self):
        all_success = True
        for key, value in self.all_items.items():
            # 將 Windows 不允許的檔名字元都替換掉，並去除 emoji
            sanitized_key = sanitize_filename(key, fallback=f"video_{int(time.time())}")
            self.path = os.path.join(self.current_dir, "videos", f"{sanitized_key}.mp4")
            try:
                # 將 path 傳給 download_video 方法
                success = self.downloader.download_video(value, self.path)
                if success:
                    logger.info(f"{value} has been downloaded to {self.path}")

                    # 檢查影片是否超過10小時，如果是則進行切割
                    self.video_processor.check_and_split_if_long(
                        self.path,
                        sanitized_key,
                        os.path.join(self.current_dir, "videos"),
                    )
                else:
                    logger.error(f"Failed to download {value}")
                    all_success = False
            except Exception as e:
                logger.error(f"Error downloading {value}: {str(e)}")
                all_success = False
        return all_success

    def run(self):
        return self.download()
