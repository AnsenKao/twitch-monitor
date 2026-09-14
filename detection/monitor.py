import re
import time
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


class _OutageTracker:
    """網路偶爾斷一下不記錄，連續失敗才記錯誤，恢復時記中斷多久。

    輪詢每 30 秒一次，單次失敗通常下一輪就好了，不影響任何事。
    連續失敗代表真的斷線（例如剛好在開台時斷線導致沒錄到），才值得留紀錄。
    """

    def __init__(self, logger, threshold=3):
        self._logger = logger
        self._threshold = threshold
        self._failures = 0
        self._started_at = None  # 第一次失敗的時間，用來算中斷多久
        self._started_label = None
        self._failed_this_check = False

    def begin_check(self):
        self._failed_this_check = False

    def error(self, message):
        """get_twitch_metadata 失敗時會呼叫。"""
        self._failed_this_check = True
        self._failures += 1
        if self._failures == 1:
            self._started_at = time.monotonic()
            self._started_label = time.strftime("%H:%M:%S")
        if self._failures == self._threshold:
            self._logger.error(
                f"連續 {self._failures} 次取得直播狀態失敗（{self._started_label} 起）：{message}"
            )

    def end_check(self):
        """這一輪沒有失敗就代表連線正常（開台或離線都算）。"""
        if self._failed_this_check or not self._failures:
            return
        if self._failures >= self._threshold:
            self._logger.info(
                f"已恢復，中斷約 {_format_duration(time.monotonic() - self._started_at)}"
                f"（{self._started_label} 起，共失敗 {self._failures} 次）"
            )
        self._failures = 0
        self._started_at = None
        self._started_label = None


def _format_duration(seconds):
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours} 小時 {minutes} 分"
    if minutes:
        return f"{minutes} 分 {secs} 秒"
    return f"{secs} 秒"


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
        self._outage = _OutageTracker(self.logger)
        self.session = Streamlink()

    def check_live_status(self, channel_url):
        """
        Checks if a Twitch channel is live.
        Returns a dict with the stream list and metadata (title/author/category)
        if live, None otherwise.
        """
        self._outage.begin_check()
        result = get_twitch_metadata(
            channel_url, session=self.session, logger=self._outage
        )
        self._outage.end_check()
        return result
