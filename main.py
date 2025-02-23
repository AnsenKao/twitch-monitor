from detection import DetectionFlow
from downloader import DownloadFlow
from uploader import UploadFlow
from utils import setup_logger, clear_videos
import asyncio
import os

logger = setup_logger(__name__)
videos_root = "downloader/videos/"


def main():
    detection_flow = DetectionFlow(
        url="https://www.twitch.tv/shxtou/videos?filter=archives&sort=time",
        item_selector="//*[@data-a-target='video-tower-card-0']",
    )
    items = asyncio.run(detection_flow.run())
    if not items:
        return
    download_flow = DownloadFlow(items)
    download_flow.run()

    upload_flow = UploadFlow()
    for key, value in items:
        upload_flow.upload(f"{videos_root}{key}.mp4", key, value)

    clear_videos(videos_root)


if __name__ == "__main__":
    videos = os.listdir(videos_root)
    if not videos:
        main()
    else:
        upload_flow = UploadFlow()
        for video in videos:
            upload_flow.upload(
                os.path.join(videos_root, video), video.split(".mp4")[0], ""
            )

        clear_videos(videos_root)
