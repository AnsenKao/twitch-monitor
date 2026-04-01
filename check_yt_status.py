import os
import json
import pickle
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

# Configuration
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(PROJECT_DIR, "credentials.pkl")
CLIENT_SECRETS_FILE = os.path.join(PROJECT_DIR, "client_secret.json")
STATE_FILE = os.path.join(PROJECT_DIR, "notified_videos.json")
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly", "https://www.googleapis.com/auth/youtube.force-ssl"]

def get_service():
    creds = None
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "rb") as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(CREDENTIALS_FILE, "wb") as token:
                pickle.dump(creds, token)
        else:
            # Should not happen in automated flow usually, but handled just in case
            raise Exception("Credentials expired and no refresh token available.")
            
    return build("youtube", "v3", credentials=creds)

def load_notified():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            try:
                return set(json.load(f))
            except (json.JSONDecodeError, ValueError):
                return set()
    return set()

def save_notified(video_ids):
    # Load existing
    current = load_notified()
    
    # 將正在處理的 video_ids 從目前的集合中移除 (如果存在)
    # 這樣我們可以將它們重新加到列表末尾，確保它們被視為"最新"且不會被截斷
    remaining = [vid for vid in current if vid not in video_ids]
    
    # 組合: [舊的且不在本次清單中的] + [本次清單中的]
    # 這樣本次掃描到的影片一定在最後面 (Safe from truncation)
    new_list = remaining + video_ids
    
    # 截斷保持最後 100 筆
    if len(new_list) > 100:
        new_list = new_list[-100:]
        
    with open(STATE_FILE, "w") as f:
        json.dump(new_list, f)

def check_new_videos():
    try:
        youtube = get_service()
        
        # 1. Get Uploads Playlist ID
        channels_response = youtube.channels().list(
            mine=True,
            part="contentDetails"
        ).execute()
        
        if not channels_response["items"]:
            return []
            
        uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        
        # 2. Get recent videos from playlist
        playlist_response = youtube.playlistItems().list(
            playlistId=uploads_playlist_id,
            part="snippet,contentDetails",
            maxResults=20
        ).execute()
        
        video_ids = []
        video_map = {}
        
        for item in playlist_response.get("items", []):
            vid = item["contentDetails"]["videoId"]
            video_ids.append(vid)
            video_map[vid] = {
                "title": item["snippet"]["title"],
                "publishedAt": item["snippet"]["publishedAt"],
                "channelTitle": item["snippet"]["channelTitle"]
            }
            
        if not video_ids:
            return []

        # 3. Check processing status
        videos_response = youtube.videos().list(
            id=",".join(video_ids),
            part="status,snippet"
        ).execute()
        
        notified = load_notified()
        new_ready_videos = []
        processed_ids_for_state = []
        
        
        current_time = datetime.now(timezone.utc)
        
        for item in videos_response.get("items", []):
            vid = item["id"]
            title = video_map.get(vid, {}).get("title", "Unknown")
            status = item["status"]
            upload_status = status.get("uploadStatus")
            privacy_status = status.get("privacyStatus")
            
            # publishedAt is in format "2026-02-05T07:16:21Z"
            published_at_str = video_map.get(vid, {}).get("publishedAt")
            published_at_dt = None
            if published_at_str:
                try:
                    # Replace Z with +00:00 for compatibility if fromisoformat is strict on some versions
                    published_at_dt = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
                except ValueError:
                    # Fallback for older python or different format
                    pass

            
            
            # Auto-delete stuck videos logic
            # If status is 'uploaded' and it has been more than 2 days since publishedAt
            if upload_status == "uploaded" and published_at_dt:
                age = current_time - published_at_dt
                # Consider using timedelta(hours=48) for clarity, user said "2 days"
                if age > timedelta(days=2):
                    print(f"WARNING: Video {title} ({vid}) is stuck in 'uploaded' for {age}. Deleting...")
                    try:
                        youtube.videos().delete(id=vid).execute()
                        print(f"SUCCESS: Deleted video {vid}")
                        continue # Skip further processing for this video
                    except Exception as e:
                        print(f"ERROR: Failed to delete video {vid}: {e}")
            
            if upload_status == "processed":
                if vid not in notified:
                    video_info = video_map.get(vid, {})
                    # Add privacy info
                    video_info["privacy"] = privacy_status
                    video_info["id"] = vid
                    video_info["url"] = f"https://www.youtube.com/watch?v={vid}"
                    new_ready_videos.append(video_info)
                else:
                    pass
            else:
                pass
                
            if upload_status == "processed":
                processed_ids_for_state.append(vid)
        
        # Output JSON for the agent
        print(json.dumps(new_ready_videos, ensure_ascii=False))
        
        # Update state immediately to avoid duplicate alerts on next run
        # Risk: Agent fails to send message. 
        # Mitigation: The agent is reliable enough. Better than spamming.
        if processed_ids_for_state:
            save_notified(processed_ids_for_state)
            
    except Exception as e:
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    check_new_videos()
