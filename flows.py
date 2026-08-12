from detection import DetectionFlow
from detection.monitor import StreamMonitor
from downloader import DownloadFlow
from downloader.recorder import StreamRecorder
from uploader import UploadFlow
from utils import setup_logger, clear_empty_data, send_discord
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
        items_dict = asyncio.run(detection_flow.run())
        
        if not items_dict:
            logger.info("No items detected, exiting")
            clear_empty_data("logs")
            return
            
        logger.info(f"Detected items: {items_dict}")
        
        # Convert to list and reverse to process Oldest -> Newest
        items_list = list(items_dict.items())
        items_list.reverse()
        
        logger.info(f"Processing {len(items_list)} items sequentially")

        for title, url in items_list:
            logger.info(f"--- Processing item: {title} ---")
            
            # Ensure clean state (optional warning)
            if os.listdir(videos_root):
                 logger.warning(f"Videos directory not empty before download: {os.listdir(videos_root)}")

            # Download
            detection_item = {title: url}
            download_flow = DownloadFlow(detection_item)
            logger.info(f"Downloading: {title}")
            if not download_flow.run():
                 logger.error(f"Download failed for {title}. Skipping to next item.")
                 send_discord(f"❌ 下載失敗：{title}")
                 continue
            
            # Check if download produced files
            if not os.listdir(videos_root):
                 logger.error(f"Download reported success but no files found in {videos_root}. Skipping to next item.")
                 continue
            
            # Upload
            logger.info(f"Uploading content for: {title}")
            upload_success, yt_urls = upload_existing_videos(playlist_id)

            if upload_success:
                # Double check if directory is empty after upload (upload_existing_videos should clean up)
                if not os.listdir(videos_root):
                    logger.info(f"Successfully processed {title}. Updating trace.")
                    if len(yt_urls) == 1:
                        yt_links = f"YouTube：{yt_urls[0]}"
                    elif yt_urls:
                        yt_links = "\n".join(f"YouTube ({i+1})：{u}" for i, u in enumerate(yt_urls))
                    else:
                        yt_links = "（無 YouTube 連結）"
                    send_discord(f"✅ 下載並上傳完成：{title}\nTwitch：{url}\n{yt_links}")
                    detection_flow.update_latest(url)
                else:
                    logger.warning(f"Upload reported success but files remain in {videos_root}. Not updating trace to be safe.")
                    send_discord(f"⚠️ 上傳完成但目錄仍有殘留檔案：{title}\nTwitch：{url}")
                    break
            else:
                logger.error(f"Failed to upload {title}. Stopping workflow to preserve order.")
                send_discord(f"❌ 上傳失敗：{title}\nTwitch：{url}")
                break

    except Exception as e:
        logger.error(f"An error occurred in main process: {e}")
    clear_empty_data("logs")


def single_url_flow(url, playlist_id):
    try:
        logger.info(f"Processing single URL: {url}")
        # 使用 Playwright 獲取 Twitch 影片標題
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # 設置 User-Agent
                page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                logger.info(f"Loading page: {url}")
                page.goto(url, wait_until='networkidle', timeout=30000)
                
                # 等待內容載入
                page.wait_for_timeout(2000)
                
                # 使用主要的標題選擇器
                stream_title_elem = page.query_selector('p[data-a-target="stream-title"]')
                if stream_title_elem:
                    stream_title = stream_title_elem.text_content().strip()
                    if stream_title:
                        logger.info(f"Successfully extracted title: {stream_title}")
                        browser.close()
                        # 這裡不能 return，需要繼續執行下載流程
                    else:
                        browser.close()
                        raise ValueError('Stream title element is empty')
                else:
                    browser.close()
                    raise ValueError('Stream title element not found')
                
        except Exception as e:
            logger.error(f"Failed to fetch stream title with Playwright: {e}")
            stream_title = f"video_{int(time.time())}"
        logger.info(f"Using stream title for filename: {stream_title}")
        # 交給 DownloadFlow 處理檔名合法化
        detection_item = {stream_title: url}
        download_flow = DownloadFlow(detection_item)
        logger.info(f"Running download flow for single URL, title: {stream_title}")
        if download_flow.run():
            # 下載完直接呼叫 upload_existing_videos
            upload_success, yt_urls = upload_existing_videos(playlist_id)
            if upload_success:
                if len(yt_urls) == 1:
                    yt_links = f"YouTube：{yt_urls[0]}"
                elif yt_urls:
                    yt_links = "\n".join(f"YouTube ({i+1})：{u}" for i, u in enumerate(yt_urls))
                else:
                    yt_links = "（無 YouTube 連結）"
                send_discord(f"✅ 下載並上傳完成：{stream_title}\nTwitch：{url}\n{yt_links}")
            else:
                send_discord(f"❌ 上傳失敗：{stream_title}\nTwitch：{url}")
        else:
            logger.error(f"Download failed for {stream_title}. Skipping upload.")
            send_discord(f"❌ 下載失敗：{stream_title}\nTwitch：{url}")
    except Exception as e:
        logger.error(f"An error occurred in single_url_flow: {e}")
    clear_empty_data("logs")


def upload_existing_videos(playlist_id):
    upload_flow = UploadFlow()
    all_success = True
    youtube_urls = []

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
    if not videos_to_upload:
        logger.info("No videos found to upload.")
    
    for video_info in videos_to_upload:
        logger.info(f"Uploading video: {video_info['name']} (type: {video_info['type']})")
        yt_url = upload_flow.upload(
            video_info['path'],
            video_info['name'],
            "",
            playlist_id,
        )

        if yt_url:
            youtube_urls.append(yt_url)
            os.remove(video_info['path'])  # 只有上傳成功才刪除
            logger.info(f"Successfully uploaded and removed: {video_info['path']}")
        else:
            logger.warning(f"Upload failed for {video_info['name']}, file kept at: {video_info['path']}")
            all_success = False
    
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
    success = all_success and (len(videos_to_upload) > 0 or not os.listdir(videos_root))
    return success, youtube_urls


def live_monitor_flow(channel_name, playlist_id, check_interval=30):
    monitor = StreamMonitor()
    recorder = StreamRecorder()
    channel_url = f"https://www.twitch.tv/{channel_name}"
    
    logger.info(f"Starting live monitor for channel: {channel_name}")
    
    while True:
        try:
            # Check if channel is live
            stream_info = monitor.check_live_status(channel_url)
            
            if stream_info:
                logger.info(f"{channel_name} is LIVE! Preparing to record...")
                send_discord(f"🔴 {channel_name} 開始直播，準備錄製...")
                
                # Create a filename based on timestamp
                timestamp = int(time.time())
                ts_filename = f"{channel_name}_{timestamp}.ts"
                mp4_filename = f"{channel_name}_{timestamp}.mp4"
                ts_path = os.path.join(videos_root, ts_filename)
                output_path = os.path.join(videos_root, mp4_filename)
                
                # Start recording to .ts (resilient to interruption)
                success = recorder.start_recording(channel_url, ts_path)
                
                if success and os.path.exists(ts_path):
                    logger.info("Recording finished. Remuxing to MP4...")
                    
                    # Remux to MP4
                    remux_success = recorder.remux_video(ts_path, output_path)
                    
                    if remux_success:
                        # Remove the original TS file
                        os.remove(ts_path)
                        logger.info("Remuxing successful and TS file removed. Starting upload...")
                        # Upload the recorded file
                        upload_success, yt_urls = upload_existing_videos(playlist_id)
                        if upload_success:
                            if len(yt_urls) == 1:
                                yt_links = f"YouTube：{yt_urls[0]}"
                            elif yt_urls:
                                yt_links = "\n".join(f"YouTube ({i+1})：{u}" for i, u in enumerate(yt_urls))
                            else:
                                yt_links = "（無 YouTube 連結）"
                            send_discord(f"✅ {channel_name} 直播錄製並上傳完成\n{yt_links}")
                        else:
                            send_discord(f"❌ {channel_name} 直播錄製完成但上傳失敗")
                    else:
                        logger.error("Remuxing failed. Keeping TS file.")
                        send_discord(f"❌ {channel_name} 錄製後轉檔失敗")
                else:
                    logger.warning("Recording finished but no file created or failed.")
                    send_discord(f"❌ {channel_name} 錄製失敗，無法產生檔案")
            else:
                # logger.info(f"{channel_name} is offline. Checking again in {check_interval}s...")
                pass
            
            time.sleep(check_interval)
            
        except KeyboardInterrupt:
            logger.info("Monitor stopped by user.")
            break
        except Exception as e:
            logger.error(f"Error in live_monitor_flow: {e}")
            time.sleep(check_interval)
