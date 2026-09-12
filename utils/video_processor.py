import subprocess
import os
import json
import shutil
from utils import get_logger

logger = get_logger(__name__)


class VideoProcessor:
    def __init__(self):
        self.ffmpeg_path = self._find_ffmpeg()
        self.ffprobe_path = self._find_ffprobe()

    def _find_ffmpeg(self):
        """查找系統中的FFmpeg"""
        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            logger.warning("FFmpeg not found in system PATH. Please install FFmpeg.")
            return None
        return ffmpeg_path

    def _find_ffprobe(self):
        """查找系統中的FFprobe"""
        ffprobe_path = shutil.which("ffprobe")
        if not ffprobe_path:
            logger.warning("FFprobe not found in system PATH. Please install FFmpeg.")
            return None
        return ffprobe_path

    def get_video_duration(self, video_path):
        """
        獲取影片的時長（以秒為單位）
        
        :param video_path: 影片檔案路徑
        :return: 影片時長（秒），如果失敗返回None
        """
        if not self.ffprobe_path or not os.path.exists(video_path):
            return None

        try:
            cmd = [
                self.ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                video_path
            ]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                duration = float(data['format']['duration'])
                logger.info(f"Video duration: {duration:.2f} seconds ({duration/3600:.2f} hours)")
                return duration
            else:
                logger.error(f"FFprobe error: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting video duration: {str(e)}")
            return None

    def split_video_by_time(self, input_path, output_dir, segment_duration_hours=10):
        """
        按時間切割影片
        
        :param input_path: 輸入影片路徑
        :param output_dir: 輸出目錄
        :param segment_duration_hours: 每段的時長（小時）
        :return: 成功切割的片段列表
        """
        if not self.ffmpeg_path or not os.path.exists(input_path):
            return []

        # 確保輸出目錄存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 獲取原檔案名稱（不含副檔名）
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        
        # 計算每段的秒數
        segment_duration_seconds = segment_duration_hours * 3600
        
        try:
            # 使用FFmpeg的segment參數來切割
            output_pattern = os.path.join(output_dir, f"{base_name}_part%03d.mp4")
            
            cmd = [
                self.ffmpeg_path,
                "-i", input_path,
                "-c", "copy",  # 使用複製模式，不重新編碼，速度更快
                "-map", "0",
                "-segment_time", str(segment_duration_seconds),
                "-f", "segment",
                "-reset_timestamps", "1",
                output_pattern
            ]
            
            logger.info(f"Starting video split: {input_path}")
            logger.info(f"Command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=7200  # 2小時超時
            )
            
            if result.returncode == 0:
                # 找到所有生成的片段檔案
                segments = []
                part_num = 0
                while True:
                    segment_path = os.path.join(output_dir, f"{base_name}_part{part_num:03d}.mp4")
                    if os.path.exists(segment_path):
                        segments.append(segment_path)
                        part_num += 1
                    else:
                        break
                
                logger.info(f"Successfully split video into {len(segments)} segments")
                
                # 刪除原始檔案（可選）
                # os.remove(input_path)
                # logger.info(f"Removed original file: {input_path}")
                
                return segments
            else:
                logger.error(f"FFmpeg error: {result.stderr}")
                return []
                
        except subprocess.TimeoutExpired:
            logger.error("Video splitting timed out")
            return []
        except Exception as e:
            logger.error(f"Error splitting video: {str(e)}")
            return []

    def is_video_long(self, video_path, threshold_hours=10):
        """
        檢查影片是否超過指定時長
        
        :param video_path: 影片檔案路徑
        :param threshold_hours: 閾值時長（小時）
        :return: True if 影片超過閾值時長
        """
        duration = self.get_video_duration(video_path)
        if duration is None:
            return False
            
        threshold_seconds = threshold_hours * 3600
        return duration > threshold_seconds

    def check_and_split_if_long(
        self,
        video_path,
        video_name,
        output_root,
        threshold_hours=10,
        segment_duration_hours=10,
    ):
        """
        檢查影片長度，超過 threshold_hours 就切成多段並刪除原始檔。
        VOD 下載與直播錄影兩條路徑共用這個入口。

        :param video_path: 影片檔案路徑
        :param video_name: 影片名稱（用於建立 {video_name}_segments 目錄）
        :param output_root: 放置 segments 目錄的父目錄
        :param threshold_hours: 超過幾小時才需要切割
        :param segment_duration_hours: 每段的時長（小時）
        :return: True 表示已切成多段；False 表示未切割（不需要、或切割失敗）
        """
        try:
            if not self.is_video_long(video_path, threshold_hours=threshold_hours):
                logger.info(
                    f"Video {video_name} is under {threshold_hours} hours, no splitting needed"
                )
                return False

            logger.info(
                f"Video {video_name} is longer than {threshold_hours} hours, starting to split..."
            )
            split_output_dir = os.path.join(output_root, f"{video_name}_segments")

            segments = self.split_video_by_time(
                input_path=video_path,
                output_dir=split_output_dir,
                segment_duration_hours=segment_duration_hours,
            )

            if not segments:
                logger.error(f"Failed to split video: {video_name}")
                return False

            logger.info(f"Successfully split {video_name} into {len(segments)} segments:")
            for i, segment in enumerate(segments, 1):
                logger.info(f"  Part {i}: {segment}")

            # 切割成功後刪除原始檔案以節省空間；刪不掉的話原檔與片段會一起被上傳，
            # 所以這裡失敗要當成錯誤記錄下來。
            try:
                os.remove(video_path)
                logger.info(f"Removed original file: {video_path}")
            except Exception as e:
                logger.error(f"Failed to remove original file {video_path}: {str(e)}")

            return True

        except Exception as e:
            logger.error(f"Error checking/splitting video {video_name}: {str(e)}")
            return False
