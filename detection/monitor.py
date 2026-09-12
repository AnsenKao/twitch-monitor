import re
from urllib.parse import urlsplit

from utils import get_logger
from streamlink import Streamlink

_URL_RE = re.compile(r"https?://[^\s'\"]+")
_MAX_ERROR_LEN = 300


def _strip_url_query(match):
    """只留 scheme://host/path，丟掉 query。

    Twitch 的 usher 網址會把存取 token 放在 query string，完整記下來
    等於把憑證寫進 log，而且單行可以超過 2000 字元。
    """
    parts = urlsplit(match.group(0))
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def summarize_error(exc):
    """把例外壓成單行摘要：類型 + 去掉 query 的訊息，並截斷長度。"""
    message = _URL_RE.sub(_strip_url_query, str(exc))
    message = " ".join(message.split())
    if len(message) > _MAX_ERROR_LEN:
        message = message[:_MAX_ERROR_LEN] + "..."
    return f"{type(exc).__name__}: {message}"


class _DedupErrorLogger:
    """連續出現的同一種錯誤只記一次，恢復或換錯誤時補記次數。

    離線輪詢每 30 秒一次，網路不穩時同一則錯誤會洗掉整個 log。
    """

    def __init__(self, logger):
        self._logger = logger
        self._last = None
        self._repeats = 0

    def error(self, message):
        if message == self._last:
            self._repeats += 1
            return
        self._flush()
        self._logger.error(message)
        self._last = message
        self._repeats = 0

    def _flush(self):
        if self._last is not None and self._repeats:
            self._logger.error(f"(前一則錯誤又重複了 {self._repeats} 次)")
        self._repeats = 0

    def reset(self):
        """成功取得資料時呼叫，讓下次同樣的錯誤會重新記錄。"""
        self._flush()
        self._last = None


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
            logger.error(f"Error fetching metadata for {url}: {summarize_error(e)}")
        return None


class StreamMonitor:
    def __init__(self):
        self.logger = get_logger(__name__)
        self._error_logger = _DedupErrorLogger(self.logger)
        self.session = Streamlink()

    def check_live_status(self, channel_url):
        """
        Checks if a Twitch channel is live.
        Returns a dict with the stream list and metadata (title/author/category)
        if live, None otherwise.
        """
        result = get_twitch_metadata(
            channel_url, session=self.session, logger=self._error_logger
        )
        if result:
            self._error_logger.reset()
        return result
