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
        
        # 檢查下載結果（考慮切割後的檔案結構）
        downloaded_content = os.listdir(videos_root)
        if not downloaded_content:
            logger.error("No content found after download")
        else:
            logger.info(f"Download completed. Found {len(downloaded_content)} items in videos directory")

        # 下載完直接呼叫 upload_existing_videos
        upload_existing_videos(playlist_id)

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
        logger.info(f"Uploading video: {video_info['name']} (type: {video_info['type']})")
        upload_success = upload_flow.upload(
            video_info['path'],
            video_info['name'],
            "",
            playlist_id,
        )
        
        if upload_success:
            os.remove(video_info['path'])  # 只有上傳成功才刪除
            logger.info(f"Successfully uploaded and removed: {video_info['path']}")
        else:
            logger.warning(f"Upload failed for {video_info['name']}, file kept at: {video_info['path']}")
    
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
