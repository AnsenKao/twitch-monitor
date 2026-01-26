from utils import setup_logger
from streamlink import Streamlink

class StreamMonitor:
    def __init__(self):
        self.logger = setup_logger("Monitor", log_file="monitor.log")
        self.session = Streamlink()

    def check_live_status(self, channel_url):
        """
        Checks if a Twitch channel is live.
        Returns the stream object if live, None otherwise.
        """
        try:
            streams = self.session.streams(channel_url)
            if streams:
                # self.logger.info(f"Channel {channel_url} is LIVE")
                return streams
            else:
                # self.logger.info(f"Channel {channel_url} is OFFLINE")
                return None
        except Exception as e:
            self.logger.error(f"Error checking status for {channel_url}: {e}")
            return None
