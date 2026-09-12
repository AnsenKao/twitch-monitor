# logger.py
import logging
import os
from logging.handlers import TimedRotatingFileHandler

LOG_ROOT = "logs"

_LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _restore_level_names():
    """還原標準的大寫等級名稱。

    streamlink 匯入時會把 INFO/WARNING 等改成小寫（見其 logger 模組），
    導致本專案的 log 等級大小寫不一致。這裡在設定 handler 前復原。
    """
    for level, name in (
        (logging.DEBUG, "DEBUG"),
        (logging.INFO, "INFO"),
        (logging.WARNING, "WARNING"),
        (logging.ERROR, "ERROR"),
        (logging.CRITICAL, "CRITICAL"),
    ):
        logging.addLevelName(level, name)


def configure_logging(channel=None, level=logging.INFO):
    """設定整個 process 的 logging，只在進入點呼叫一次。

    Args:
        channel (str, optional): 頻道名稱。有給的話 log 會寫到
            logs/<channel>/monitor.log，讓多個 monitor 實例不會寫進同一個檔案；
            沒給則寫 logs/manual.log。
        level (int, optional): logging 等級. Defaults to logging.INFO.

    Returns:
        str: 實際使用的 log 檔路徑
    """
    _restore_level_names()

    if channel:
        log_dir = os.path.join(LOG_ROOT, channel)
        log_name = "monitor.log"
    else:
        # --url／手動上傳等一次性執行
        log_dir = LOG_ROOT
        log_name = "manual.log"
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_name)

    root = logging.getLogger()
    root.setLevel(level)

    # 重複呼叫時先清掉舊 handler，避免同一行 log 被寫兩次
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # 跨日自動換檔，保留 14 天。長駐 process 也能正確切檔
    file_handler = TimedRotatingFileHandler(
        log_path,
        when="midnight",
        backupCount=14,
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    return log_path


def get_logger(name):
    """取得模組專用的 logger，name 請一律傳 __name__。"""
    return logging.getLogger(name)
