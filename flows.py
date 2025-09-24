from detection import DetectionFlow
from downloader import DownloadFlow
from uploader import UploadFlow
from utils import setup_logger, clear_empty_data
import asyncio
import os
import requests
from bs4 import BeautifulSoup
import time

logger = setup_logger("log")
videos_root = "downloader/videos/"


def auto_detect_and_upload(playlist_id):
    try:
        logger.info("Starting main process")
        detection_flow = DetectionFlow(
            url="https://www.twitch.tv/shxtou/videos?filter=archives&sort=time",
            item_selector="//*[@data-a-target='video-tower-card-0']",
        )
        logger.info("Running detection flow")
        items = asyncio.run(detection_flow.run())
        if not items:
            logger.info("No items detected, exiting")
            clear_empty_data("logs")
            return
        logger.info(f"Detected items: {items}")

        download_flow = DownloadFlow(items)
        logger.info("Running download flow")
        download_flow.run()
        if len(os.listdir(videos_root)) != len(items):
            logger.error("Detect missing downloaded items")

        # 下載完直接呼叫 upload_existing_videos
        upload_existing_videos(playlist_id)

    except Exception as e:
        logger.error(f"An error occurred in main process: {e}")
    clear_empty_data("logs")


def single_url_flow(url, playlist_id):
    try:
        logger.info(f"Processing single URL: {url}")
        # 只抓 meta[name=title] 當作 stream title
        try:
            resp = requests.get(url)
            soup = BeautifulSoup(resp.text, 'html.parser')
            meta_title = soup.find('meta', {'name': 'title'})
            if meta_title and meta_title.has_attr('content') and meta_title['content'].strip():
                stream_title = meta_title['content']
            else:
                raise ValueError('No stream title found in meta[name=title]')
        except Exception as e:
            logger.error(f"Failed to fetch stream title: {e}")
            stream_title = f"video_{int(time.time())}"
        logger.info(f"Using stream title for filename: {stream_title}")
        # 交給 DownloadFlow 處理檔名合法化
        detection_item = {stream_title: url}
        download_flow = DownloadFlow(detection_item)
        logger.info(f"Running download flow for single URL, title: {stream_title}")
        download_flow.run()
        # 下載完直接呼叫 upload_existing_videos
        upload_existing_videos(playlist_id)
    except Exception as e:
        logger.error(f"An error occurred in single_url_flow: {e}")
    clear_empty_data("logs")


def upload_existing_videos(playlist_id):
    upload_flow = UploadFlow()
    
    # 獲取所有需要上傳的影片（包含切割片段）
    videos_to_upload = []
    
    for item in os.listdir(videos_root):
        item_path = os.path.join(videos_root, item)
        
        if os.path.isfile(item_path) and item.endswith('.mp4'):
            # 這是一個普通的影片檔案
            videos_to_upload.append({
                'path': item_path,
                'name': item.split(".mp4")[0],
                'type': 'single'
            })
        elif os.path.isdir(item_path) and item.endswith('_segments'):
            # 這是一個切割片段目錄
            logger.info(f"Found segments directory: {item}")
            segment_files = [f for f in os.listdir(item_path) if f.endswith('.mp4')]
            segment_files.sort()  # 確保按順序上傳
            
            for segment_file in segment_files:
                segment_path = os.path.join(item_path, segment_file)
                videos_to_upload.append({
                    'path': segment_path,
                    'name': segment_file.split(".mp4")[0],
                    'type': 'segment'
                })
    
    # 上傳所有影片
    for video_info in videos_to_upload:
        try:
            logger.info(f"Uploading video: {video_info['name']} (type: {video_info['type']})")
            upload_flow.upload(
                video_info['path'],
                video_info['name'],
                "",
                playlist_id,
            )
            os.remove(video_info['path'])  # 只有上傳成功才刪除
            logger.info(f"Successfully uploaded and removed: {video_info['path']}")
        except Exception as e:
            logger.error(f"An error occurred while uploading video {video_info['name']}: {e}")
    
    # 清理空的 segments 目錄
    for item in os.listdir(videos_root):
        item_path = os.path.join(videos_root, item)
        if os.path.isdir(item_path) and item.endswith('_segments'):
            try:
                if not os.listdir(item_path):  # 如果目錄是空的
                    os.rmdir(item_path)
                    logger.info(f"Removed empty segments directory: {item_path}")
            except Exception as e:
                logger.error(f"Error removing segments directory {item_path}: {e}")
    
    clear_empty_data("logs")
