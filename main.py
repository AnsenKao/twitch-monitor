from detection import DetectionFlow
from downloader import DownloadFlow
from uploader import UploadFlow
from config import setup_logger
import asyncio

logger = setup_logger(__name__)


def main():
    detection_flow = DetectionFlow(
        url="https://www.twitch.tv/shxtou/videos?filter=archives&sort=time",
        item_selector="//*[@data-a-target='video-tower-card-0']",
    )
    items = asyncio.run(detection_flow.run())
    download_flow = DownloadFlow(items)
    download_flow.run()

    upload_flow = UploadFlow()
    for key, value in items:
        upload_flow.upload(f"downloader/videos/{key}.mp4", key, value)


if __name__ == "__main__":
    main()
