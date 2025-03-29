from detection import DetectionFlow
from downloader import DownloadFlow
from uploader import UploadFlow
from utils import setup_logger
import asyncio
import os
import dotenv

dotenv.load_dotenv()

logger = setup_logger("log")
videos_root = "downloader/videos/"
playlist_id = os.getenv("PLAYLIST")


def main():
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
            upload_flow.upload(video_file, key, value, playlist_id)
            os.remove(video_file)

        logger.info("Clearing downloaded videos")
    except Exception as e:
        logger.error(f"An error occurred in main process: {e}")


if __name__ == "__main__":
    videos = os.listdir(videos_root)
    if not videos:
        main()
    else:
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
                os.remove(video_path)
            except Exception as e:
                logger.error(f"An error occurred while uploading video {video}: {e}")

