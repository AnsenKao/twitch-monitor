from downloader import YTDLPDownloader
from utils import setup_logger
from utils.video_processor import VideoProcessor
import os
import re

logger = setup_logger("log")


class DownloadFlow:
    def __init__(self, all_items):
        # 修正檔名並使用絕對路徑
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.yt_dlp_path = os.path.join(self.current_dir, "yt-dlp.exe")
        self.all_items = all_items
        self.downloader = YTDLPDownloader(self.yt_dlp_path)
        self.video_processor = VideoProcessor()

    def download(self):
        for key, value in self.all_items.items():
            # 將 Windows 不允許的檔名字元都替換掉，並去除 emoji
            sanitized_key = key
            for ch in r'\/\:*?"<>|':
                sanitized_key = sanitized_key.replace(ch, "_")
            sanitized_key = sanitized_key.replace("@", "feat")
            # 去除 emoji
            sanitized_key = re.sub(r'[\U00010000-\U0010ffff\u2600-\u26FF\u2700-\u27BF]+', '', sanitized_key)
            self.path = os.path.join(self.current_dir, "videos", f"{sanitized_key}.mp4")
            try:
                # 將 path 傳給 download_video 方法
                success = self.downloader.download_video(value, self.path)
                if success:
                    logger.info(f"{value} has been downloaded to {self.path}")
                    
                    # 檢查影片是否超過12小時，如果是則進行切割
                    self._check_and_split_video(self.path, sanitized_key)
                else:
                    logger.error(f"Failed to download {value}")
            except Exception as e:
                logger.error(f"Error downloading {value}: {str(e)}")

    def _check_and_split_video(self, video_path, video_name):
        """
        檢查影片長度，如果超過12小時則切割成6小時的片段
        
        :param video_path: 影片檔案路徑
        :param video_name: 影片名稱（用於建立切割檔案的目錄）
        """
        try:
            # 檢查影片是否超過12小時
            if self.video_processor.is_video_long(video_path, threshold_hours=12):
                logger.info(f"Video {video_name} is longer than 12 hours, starting to split...")
                
                # 建立切割檔案的輸出目錄
                split_output_dir = os.path.join(self.current_dir, "videos", f"{video_name}_segments")
                
                # 切割影片（每6小時一段）
                segments = self.video_processor.split_video_by_time(
                    input_path=video_path,
                    output_dir=split_output_dir,
                    segment_duration_hours=6
                )
                
                if segments:
                    logger.info(f"Successfully split {video_name} into {len(segments)} segments:")
                    for i, segment in enumerate(segments, 1):
                        logger.info(f"  Part {i}: {segment}")
                    
                    # 可選：刪除原始檔案以節省空間
                    # os.remove(video_path)
                    # logger.info(f"Removed original file: {video_path}")
                else:
                    logger.error(f"Failed to split video: {video_name}")
            else:
                logger.info(f"Video {video_name} is under 12 hours, no splitting needed")
                
        except Exception as e:
            logger.error(f"Error checking/splitting video {video_name}: {str(e)}")

    def run(self):
        self.download()
