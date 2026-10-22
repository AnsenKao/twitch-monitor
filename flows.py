from detection import DetectionFlow
from detection.monitor import StreamMonitor, get_twitch_metadata
from downloader import DownloadFlow
from downloader.recorder import StreamRecorder
from uploader import UploadFlow
from utils import (
    get_logger,
    clear_empty_data,
    send_discord,
    format_yt_links,
    sanitize_filename,
    is_shutting_down,
)
from utils.video_processor import VideoProcessor
import asyncio
import json
import os
import queue
import requests
from bs4 import BeautifulSoup
import threading
import time

logger = get_logger(__name__)
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
            upload_success, yt_urls, uploaded_names = upload_existing_videos(playlist_id)

            if upload_success:
                # Double check if directory is empty after upload (upload_existing_videos should clean up)
                if not os.listdir(videos_root):
                    logger.info(f"Successfully processed {title}. Updating trace.")
                    yt_links = format_yt_links(yt_urls, uploaded_names)
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
        # 用 streamlink 取得 Twitch 標題（VOD 與直播網址皆適用）
        metadata = get_twitch_metadata(url, logger=logger)
        stream_title = (metadata.get("title") or "").strip() if metadata else ""
        if stream_title:
            logger.info(f"Successfully extracted title: {stream_title}")
        else:
            logger.error(f"Failed to fetch stream title for {url}, falling back to timestamp")
            stream_title = f"video_{int(time.time())}"
        logger.info(f"Using stream title for filename: {stream_title}")
        # 交給 DownloadFlow 處理檔名合法化
        detection_item = {stream_title: url}
        download_flow = DownloadFlow(detection_item)
        logger.info(f"Running download flow for single URL, title: {stream_title}")
        if download_flow.run():
            # 下載完直接呼叫 upload_existing_videos
            upload_success, yt_urls, uploaded_names = upload_existing_videos(playlist_id)
            if upload_success:
                yt_links = format_yt_links(yt_urls, uploaded_names)
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
    try:
        upload_flow = UploadFlow()
    except Exception as e:
        logger.error(f"Failed to initialize UploadFlow (authentication error): {e}")
        return False, [], []
    all_success = True
    youtube_urls = []
    uploaded_names = []

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
            uploaded_names.append(video_info['name'])
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
    return success, youtube_urls, uploaded_names


def upload_existing_flow(playlist_id):
    """videos 目錄已有檔案時的獨立入口（例如上次上傳失敗留下的檔案）。"""
    upload_success, yt_urls, names = upload_existing_videos(playlist_id)
    if upload_success:
        if len(names) == 1:
            headline = f"✅ 既有影片上傳完成：{names[0]}"
        else:
            headline = f"✅ 既有影片上傳完成（{len(names)} 部）"
        send_discord(f"{headline}\n{format_yt_links(yt_urls, names)}")
    else:
        send_discord("❌ 既有影片上傳失敗，檔案保留於 videos 目錄")
    return upload_success, yt_urls


def _resolve_output_name(base_name, fallback_name):
    """
    避免和既有檔案同名（例如上次上傳失敗留下的檔案）而被覆蓋。

    背景轉檔上傳期間 .ts／.mp4 可能已經刪掉、只剩切段目錄，所以也要看
    recording marker 和 _segments，否則同標題重開台會寫進同一個切段目錄。
    """
    candidate = base_name or fallback_name
    suffix = 2
    while any(
        os.path.exists(os.path.join(videos_root, f"{candidate}{ext}"))
        for ext in (".ts", ".mp4", ".recording.json", "_segments")
    ):
        candidate = f"{base_name}_{suffix}"
        suffix += 1
    return candidate


def _marker_path(base_name):
    return os.path.join(videos_root, f"{base_name}.recording.json")


def _write_recording_marker(base_name, channel_name, stream_title):
    """錄影開始時留下紀錄，流程正常走完才刪。

    服務在錄影中被重啟時錄影一定不完整，launchd 也只給 60 秒不夠轉檔上傳，
    所以不自動補救，改由下次啟動時提醒去 VOD 重抓。檔名經過合法化會跟
    直播標題不同，這裡保留原始標題方便在 VOD 列表裡找。
    """
    marker = {
        "channel": channel_name,
        "title": stream_title,
        "file": base_name,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_recording_marker(base_name, marker)


def _mark_recording_finished(base_name):
    """錄影已完整結束、交給背景轉檔上傳時標記。

    之後若在轉檔上傳途中被重啟，影片本身是完整的，下次啟動的提醒要改成
    「手動處理殘留檔案」而不是「去 VOD 重抓」。
    """
    try:
        with open(_marker_path(base_name), encoding="utf-8") as f:
            marker = json.load(f)
    except (OSError, ValueError) as e:
        logger.error(f"Failed to read recording marker for {base_name}: {e}")
        return
    marker["recorded_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _save_recording_marker(base_name, marker)


def _save_recording_marker(base_name, marker):
    try:
        with open(_marker_path(base_name), "w", encoding="utf-8") as f:
            json.dump(marker, f, ensure_ascii=False)
    except OSError as e:
        logger.error(f"Failed to write recording marker for {base_name}: {e}")


def _remove_recording_marker(base_name):
    """刪不掉只記錄錯誤、不往上拋，回傳是否已不存在。"""
    try:
        os.remove(_marker_path(base_name))
    except FileNotFoundError:
        pass
    except OSError as e:
        logger.error(f"Failed to remove recording marker for {base_name}: {e}")
        return False
    return True


def _warn_interrupted_recordings(channel_name):
    """啟動時檢查上次是否在錄影中被中斷，有的話發警告。

    兩個頻道共用 videos/，所以只處理自己頻道的紀錄。每筆只警告一次。
    """
    if not os.path.isdir(videos_root):
        return
    for name in sorted(os.listdir(videos_root)):
        if not name.endswith(".recording.json"):
            continue
        path = os.path.join(videos_root, name)
        try:
            with open(path, encoding="utf-8") as f:
                marker = json.load(f)
        except (OSError, ValueError) as e:
            logger.error(f"Unreadable recording marker {name}: {e}")
            continue
        if marker.get("channel") != channel_name:
            continue

        # 先刪紀錄檔再警告。刪除失敗不能讓 process 結束，否則 launchd 會一直
        # 重啟、每次都發同一則警告，monitor 也永遠起不來。
        if not _remove_recording_marker(name[: -len(".recording.json")]):
            logger.error(f"{name} could not be removed; this warning will repeat on next start.")

        title = marker.get("title") or "(無標題)"
        if marker.get("recorded_at"):
            # 錄影有錄完，是背景的轉檔／上傳被中斷：檔案完整，不必去 VOD 重抓。
            # .mp4 會在下次上傳時一起傳，.ts 則需要手動轉檔。
            logger.warning(
                f"Previous post-processing was interrupted: {title} "
                f"(recorded {marker.get('recorded_at')}, file {marker.get('file')})"
            )
            send_discord(
                f"⚠️ {channel_name} 上次錄影已完成，但轉檔或上傳被中斷\n"
                f"標題：{title}\n"
                f"錄影結束：{marker.get('recorded_at')}\n"
                f"殘留檔案：{videos_root}{marker.get('file')}.*\n"
                f".mp4 會在下次上傳時一起上傳；若只剩 .ts 請手動轉檔"
            )
            continue

        logger.warning(
            f"Previous recording was interrupted: {title} "
            f"(started {marker.get('started_at')}, file {marker.get('file')})"
        )
        send_discord(
            f"⚠️ {channel_name} 上次錄影被中斷，檔案不完整，請從 VOD 重新下載\n"
            f"標題：{title}\n"
            f"開始錄影：{marker.get('started_at')}\n"
            f"VOD 列表：https://www.twitch.tv/{channel_name}/videos?filter=archives\n"
            f"殘留檔案：{videos_root}{marker.get('file')}.*"
        )


def _retry_stream_title(monitor, channel_url, attempts=3, delay=3):
    """開台當下標題偶爾查不到，隔幾秒重問。

    streamlink 的 Twitch plugin 是用另一支 API 取 metadata，失敗時會靜默把
    title 留成 None（見 plugins/twitch.py 的 _get_metadata），串流本身照樣
    抓得到，所以不會有例外也不會有錯誤 log。一次偶發失敗就足以讓整支影片
    用時間戳當檔名和 YouTube 標題，所以這裡多問幾次。

    重試會延後開始錄影（最多 attempts * delay 秒），取不到就放棄回傳 ""。
    """
    for attempt in range(1, attempts + 1):
        if is_shutting_down():
            return ""
        time.sleep(delay)
        info = get_twitch_metadata(channel_url, session=monitor.session, logger=logger)
        title = (info.get("title") or "").strip() if info else ""
        if title:
            logger.info(f"Stream title resolved on retry {attempt}: {title}")
            return title
    logger.warning(f"Stream title still unavailable after {attempts} retries")
    return ""


def _post_process_recording(
    recorder, video_processor, channel_name, playlist_id,
    base_name, stream_title, ts_path, output_path,
):
    """錄完的 .ts 轉成 mp4、必要時切段、上傳並通知。在背景執行緒裡跑。"""
    logger.info(f"Post-processing {base_name}: remuxing to MP4...")
    if recorder.remux_video(ts_path, output_path):
        os.remove(ts_path)
        logger.info("Remuxing successful and TS file removed.")
        # 超過 10 小時要先切段，否則單檔會超過 YouTube 的 12 小時上限而上傳失敗
        video_processor.check_and_split_if_long(output_path, base_name, videos_root)
        logger.info("Starting upload...")
        upload_success, yt_urls, _ = upload_existing_videos(playlist_id)
        if upload_success:
            yt_links = format_yt_links(yt_urls)
            send_discord(f"✅ {channel_name} 直播錄製並上傳完成：{stream_title or base_name}\n{yt_links}")
        else:
            send_discord(f"❌ {channel_name} 直播錄製完成但上傳失敗：{stream_title or base_name}")
    else:
        logger.error("Remuxing failed. Keeping TS file.")
        send_discord(f"❌ {channel_name} 錄製後轉檔失敗")

    # 已經走到有通知的結局（成功或失敗），不需要下次啟動再警告
    _remove_recording_marker(base_name)


class _PostProcessWorker:
    """用單一背景執行緒依序處理錄完的影片。

    只開一條執行緒是刻意的：upload_existing_videos 會上傳整個 videos/，
    兩份轉檔上傳同時跑會互相搶檔案。新的錄影只會寫 .ts，不會被上傳撿走。

    執行緒是 daemon：launchd 停服務時只給 60 秒，長時間的上傳不可能等完，
    被中斷的工作由 recording marker 在下次啟動時提醒。
    """

    _SHUTDOWN_WAIT = 20  # 秒，讓剛好快結束的工作有機會收尾

    def __init__(self):
        self._jobs = queue.Queue()
        self._thread = threading.Thread(
            target=self._run, name="post-process", daemon=True
        )
        self._thread.start()

    def submit(self, func, *args):
        self._jobs.put((func, args))

    def pending(self):
        """尚未完成的工作數（包含正在跑的那一個）。"""
        return self._jobs.unfinished_tasks

    def shutdown(self):
        if not self.pending():
            return
        logger.warning(
            f"{self.pending()} post-processing job(s) still running, "
            f"waiting up to {self._SHUTDOWN_WAIT}s..."
        )
        deadline = time.monotonic() + self._SHUTDOWN_WAIT
        while self.pending() and time.monotonic() < deadline:
            time.sleep(1)
        if self.pending():
            logger.warning(
                "Exiting with unfinished post-processing; it will be reported on next start."
            )

    def _run(self):
        while True:
            func, args = self._jobs.get()
            try:
                func(*args)
            except Exception as e:
                # 一支影片出錯不能讓整條背景執行緒掛掉，後面的錄影還要處理。
                # marker 會留著，下次啟動時也會再提醒一次。
                logger.error(f"Post-processing failed: {e}")
                send_discord(f"❌ 錄影後的轉檔或上傳發生錯誤：{e}")
            finally:
                self._jobs.task_done()


def live_monitor_flow(channel_name, playlist_id, check_interval=30):
    monitor = StreamMonitor()
    recorder = StreamRecorder()
    video_processor = VideoProcessor()
    post_processor = _PostProcessWorker()
    channel_url = f"https://www.twitch.tv/{channel_name}"

    logger.info(f"Starting live monitor for channel: {channel_name}")
    _warn_interrupted_recordings(channel_name)
    
    while True:
        try:
            # Check if channel is live
            stream_info = monitor.check_live_status(channel_url)
            
            if stream_info:
                stream_title = (stream_info.get("title") or "").strip()
                if not stream_title:
                    logger.warning(f"{channel_name} is LIVE but the title came back empty; retrying...")
                    stream_title = _retry_stream_title(monitor, channel_url)
                logger.info(f"{channel_name} is LIVE! Title: {stream_title or '(無標題)'}")

                # 以直播標題當檔名（同時也會成為 YouTube 影片標題），沒有標題才退回時間戳
                fallback_name = f"{channel_name}_{int(time.time())}"
                base_name = _resolve_output_name(
                    sanitize_filename(stream_title, fallback=fallback_name), fallback_name
                )
                logger.info(f"Using filename: {base_name}")

                if stream_title:
                    send_discord(f"🔴 {channel_name} 開始直播，準備錄製...\n標題：{stream_title}")
                else:
                    # 取不到標題不影響錄影，但上傳後的 YouTube 標題會是時間戳，要手動改
                    send_discord(
                        f"🔴 {channel_name} 開始直播，準備錄製...\n"
                        f"⚠️ 取不到直播標題，改用 `{base_name}` 當檔名與 YouTube 標題，上傳後請手動改名"
                    )
                ts_path = os.path.join(videos_root, f"{base_name}.ts")
                output_path = os.path.join(videos_root, f"{base_name}.mp4")
                
                _write_recording_marker(base_name, channel_name, stream_title)

                # Start recording to .ts (resilient to interruption)
                success = recorder.start_recording(channel_url, ts_path)

                # 錄影中收到終止訊號：直播沒錄完，也沒時間轉檔上傳。
                # 保留 .ts 和紀錄檔直接離開，下次啟動時會發警告。
                if is_shutting_down():
                    logger.warning(
                        f"Shutdown during recording, keeping {ts_path} unprocessed."
                    )
                    break

                if success and os.path.exists(ts_path):
                    # 轉檔、切割、上傳交給背景，主迴圈馬上回去偵測，
                    # 主播斷線後重開台才不會在上傳期間漏錄
                    _mark_recording_finished(base_name)
                    post_processor.submit(
                        _post_process_recording,
                        recorder, video_processor, channel_name, playlist_id,
                        base_name, stream_title, ts_path, output_path,
                    )
                    logger.info(
                        f"Recording finished, queued for post-processing "
                        f"({post_processor.pending()} pending). Resuming live checks."
                    )
                else:
                    logger.warning("Recording finished but no file created or failed.")
                    send_discord(f"❌ {channel_name} 錄製失敗，無法產生檔案")
                    # 已經走到有通知的結局，不需要下次啟動再警告
                    _remove_recording_marker(base_name)
            else:
                # logger.info(f"{channel_name} is offline. Checking again in {check_interval}s...")
                pass

            # 錄影結束或離線等待時，才回應先前收到的終止訊號
            if is_shutting_down():
                logger.info("Shutdown requested, exiting monitor loop.")
                break

            time.sleep(check_interval)

        except KeyboardInterrupt:
            logger.info("Monitor stopped by user.")
            break
        except Exception as e:
            logger.error(f"Error in live_monitor_flow: {e}")
            time.sleep(check_interval)

    post_processor.shutdown()
