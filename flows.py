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
    videos = os.listdir(videos_root)
    upload_flow = UploadFlow()
    for video in videos:
        try:
            logger.info(f"Uploading existing video: {video}")
            video_path = os.path.join(videos_root, video)
            upload_flow.upload(
                video_path,
                video.split(".mp4")[0],
                "",
                playlist_id,
            )
            os.remove(video_path)  # 只有上傳成功才刪除
        except Exception as e:
            logger.error(f"An error occurred while uploading video {video}: {e}")
    clear_empty_data("logs")
