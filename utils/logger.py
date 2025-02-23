# logger.py
import logging
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime


def setup_logger(name, log_file=None, level=logging.INFO):
    """設定 logger

    Args:
        name (str): logger 名稱
        log_file (str, optional): log 檔案名稱. 如果為 None，則使用日期作為檔名
        level (int, optional): logging 等級. Defaults to logging.INFO.

    Returns:
        logging.Logger: 設定好的 logger
    """
    # 建立 logs 目錄（如果不存在）
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 如果沒有指定 log_file，使用日期作為檔名
    if log_file is None:
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = f"{name}_{today}.log"

    log_path = os.path.join(log_dir, log_file)

    # 建立 logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重複添加 handlers
    if not logger.handlers:
        # 建立 rotating file handler (最大 10MB，保留 5 個備份)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(level)

        # 建立 console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)

        # 設定 log 格式
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # 將 handlers 加入 logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger
