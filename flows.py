from detection import DetectionFlow
from downloader import DownloadFlow
from uploader import UploadFlow
from utils import setup_logger, clear_empty_data
import asyncio
import os

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

        upload_flow = UploadFlow()
        for key, value in items.items():
            logger.info(f"Uploading video: {key}.mp4 with value: {value}")
            video_file = f"{videos_root}{key}.mp4"
            try:
                upload_flow.upload(video_file, key, value, playlist_id)
                os.remove(video_file)  # 只有上傳成功才刪除
            except Exception as e:
                logger.error(f"An error occurred while uploading video {key}: {e}")

    except Exception as e:
        logger.error(f"An error occurred in main process: {e}")
    clear_empty_data("logs")


def single_url_flow(url, playlist_id):
    try:
        logger.info(f"Processing single URL: {url}")
        detection_item = {url: url}  # key/value 都用 url，或可自訂
        download_flow = DownloadFlow(detection_item)
        logger.info("Running download flow for single URL")
        download_flow.run()
        key = list(detection_item.keys())[0]
        video_file = f"{videos_root}{key}.mp4"
        upload_flow = UploadFlow()
        logger.info(f"Uploading video: {key}.mp4 with value: {url}")
        try:
            upload_flow.upload(video_file, key, url, playlist_id)
            os.remove(video_file)  # 只有上傳成功才刪除
        except Exception as e:
            logger.error(f"An error occurred while uploading video {key}: {e}")
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
