import os
import argparse
import dotenv
from utils import setup_logger
from flows import auto_detect_and_upload, single_url_flow, upload_existing_videos

dotenv.load_dotenv()

logger = setup_logger("log")
videos_root = "downloader/videos/"
playlist_id = os.getenv("PLAYLIST")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', type=str, help='Download and upload a single video by URL')
    args = parser.parse_args()
    if args.url:
        single_url_flow(args.url, playlist_id)
    else:
        videos = os.listdir(videos_root)
        if not videos:
            auto_detect_and_upload(playlist_id)
        else:
            upload_existing_videos(playlist_id)
