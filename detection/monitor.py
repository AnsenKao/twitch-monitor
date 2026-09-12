from utils import get_logger
from streamlink import Streamlink


def get_twitch_metadata(url, session=None, logger=None):
    """
    取得 Twitch 網址（直播頻道或 VOD）的 streams 與 metadata。
    取不到（離線／影片不存在／解析失敗）時回傳 None。
    """
    session = session or Streamlink()
    try:
        pluginname, pluginclass, resolved_url = session.resolve_url(url)
        plugin = pluginclass(session, resolved_url)
        # streams() 會順便讓 plugin 抓到 metadata
        streams = plugin.streams()
        if not streams:
            return None

        return {
            "streams": streams,
            "title": plugin.get_title(),
            "author": plugin.get_author(),
            "category": plugin.get_category(),
        }
    except Exception as e:
        if logger:
            logger.error(f"Error fetching metadata for {url}: {e}")
        return None


class StreamMonitor:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.session = Streamlink()

    def check_live_status(self, channel_url):
        """
        Checks if a Twitch channel is live.
        Returns a dict with the stream list and metadata (title/author/category)
        if live, None otherwise.
        """
        return get_twitch_metadata(channel_url, session=self.session, logger=self.logger)
