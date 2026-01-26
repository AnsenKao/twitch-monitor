import os
import signal
import subprocess
import time
from utils import setup_logger

class StreamRecorder:
    def __init__(self):
        self.logger = setup_logger("Recorder")

    def start_recording(self, channel_url, output_path):
        """
        Starts recording a Twitch stream using streamlink.
        This function blocks until the recording stops (stream ends or error).
        """
        self.logger.info(f"Starting recording for {channel_url} to {output_path}")
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # command = [
        #     "streamlink",
        #     channel_url,
        #     "best",
        #     "-o", output_path
        # ]
        
        # Use subprocess to run streamlink
        try:
             # streamlink <url> best -o <output>
            process = subprocess.Popen(
                ["streamlink", 
                 "--hls-live-restart", 
                 "--stream-segment-threads", "5", 
                 "--stream-segment-attempts", "5", 
                 "--stream-segment-timeout", "20", 
                 "--retry-streams", "30", 
                 "--retry-max", "5", 
                 channel_url, "best", "-o", output_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for the process to finish
            try:
                stdout, stderr = process.communicate()
            except KeyboardInterrupt:
                self.logger.info("Recording stopping due to user interrupt...")
                # The subprocess (streamlink) should have received the SIGINT from the OS (Ctrl+C).
                # We simply wait for it to cleanup and exit gracefully.
                try:
                    stdout, stderr = process.communicate(timeout=15) 
                except subprocess.TimeoutExpired:
                    self.logger.warning("Streamlink did not exit gracefully, sending SIGINT...")
                    process.send_signal(signal.SIGINT)
                    stdout, stderr = process.communicate()
            
            # Check for success (0) or user interrupt (-2 or 130)
            if process.returncode != 0 and process.returncode != -2 and process.returncode != 130:
                self.logger.error(f"Streamlink exited with error code {process.returncode}")
                # self.logger.error(f"Stderr: {stderr.decode()}")
                return False
            
            self.logger.info(f"Recording finished: {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error during recording: {e}")
            return False

    def remux_video(self, input_path, output_path):
        """
        Remuxes a video file (e.g., .ts to .mp4) using ffmpeg with stream copy.
        Returns True if successful, False otherwise.
        """
        self.logger.info(f"Remuxing {input_path} to {output_path}")
        try:
            command = [
                "ffmpeg",
                "-y", # Overwrite output file
                "-i", input_path,
                "-c", "copy",
                "-bsf:a", "aac_adtstoasc", # Fix AAC bitstream for MP4
                output_path
            ]
            
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                self.logger.error(f"FFmpeg remux failed: {stderr.decode()}")
                return False
                
            self.logger.info("Remuxing complete.")
            return True
        except Exception as e:
            self.logger.error(f"Error during remuxing: {e}")
            return False
