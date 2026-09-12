# lifecycle.py
"""收到終止訊號時，讓錄影能走完 remux／上傳再退出。

launchd 重啟服務時送的是 SIGTERM，Python 預設會直接結束 process，
錄到一半的 .ts 就會變成沒有轉檔也沒有上傳的孤兒檔。
這裡把 SIGTERM 轉成與 Ctrl+C 相同的 KeyboardInterrupt 路徑，
讓既有的收尾邏輯有機會執行。
"""
import signal
import threading

_shutdown = threading.Event()


def request_shutdown():
    _shutdown.set()


def is_shutting_down():
    """主迴圈用來判斷收尾完成後是否該退出。"""
    return _shutdown.is_set()


def install_signal_handlers(logger=None):
    def _handler(signum, _frame):
        name = signal.Signals(signum).name
        if logger:
            logger.info(f"Received {name}, finishing current work before exit...")
        _shutdown.set()
        # 轉成 KeyboardInterrupt，走與 Ctrl+C 相同的收尾路徑
        raise KeyboardInterrupt(f"shutdown requested by {name}")

    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)
