import os
import argparse
import dotenv
from utils import configure_logging, get_logger
from flows import auto_detect_and_upload, single_url_flow, upload_existing_flow, live_monitor_flow

dotenv.load_dotenv()

videos_root = "downloader/videos/"
playlist_id = os.getenv("PLAYLIST")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', type=str, help='Download and upload a single video by URL')
    parser.add_argument('--monitor', type=str, help='Continuously monitor and record a Twitch channel by name')
    args = parser.parse_args()

    # 每個頻道寫到自己的 logs/<channel>/，多個 monitor 實例才不會互相覆寫
    log_path = configure_logging(channel=args.monitor)
    logger = get_logger(__name__)
    logger.info(f"Logging to {log_path}")

    if args.url:
        single_url_flow(args.url, playlist_id)
    elif args.monitor:
        live_monitor_flow(args.monitor, playlist_id)
    else:
        videos = [f for f in os.listdir(videos_root) if not f.startswith('.')]
        if not videos:
            auto_detect_and_upload(playlist_id)
        else:
            upload_existing_flow(playlist_id)
