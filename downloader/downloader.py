import subprocess


class YTDLPDownloader:
    def __init__(self, yt_dlp_path):
        """
        初始化 YTDLPDownloader 類別

        :param yt_dlp_path: yt-dlp.exe 的路徑
        """
        self.yt_dlp_path = yt_dlp_path

    def download_video(self, video_url, output_path=None):
        """
        下載影片

        :param video_url: 要下載的影片 URL
        :param output_path: 下載影片的儲存路徑 (可選)
        :return: 下載結果的標準輸出和標準錯誤
        """
        yt_dlp_args = [self.yt_dlp_path, video_url, "--progress"]

        if output_path:
            yt_dlp_args.extend(["-o", output_path])

        try:
            process = subprocess.Popen(
                yt_dlp_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            # 實時讀取並輸出進度
            for line in process.stdout:
                print(line, end="", flush=True)

            # 等待進程完成
            return_code = process.wait(timeout=3600)  # 1小時超時
            return return_code == 0

        except subprocess.TimeoutExpired:
            print(f"下載超時: {video_url}")
            process.kill()
            return False
        except Exception as e:
            print(f"發生未預期的錯誤: {str(e)}")
            if "process" in locals():
                process.kill()
            return False


# 使用範例
if __name__ == "__main__":
    yt_dlp_path = "E:/Projects/twitch-monitor/downloader/yt-dlp.exe"
    video_url = "https://www.youtube.com/watch?v=Z8brPP0U0Ak&ab_channel=%E7%86%8A%E7%8C%AB%E5%A4%A7G-%E6%80%95%E6%AD%BB%E6%B5%81%E5%A1%9E%E6%81%A9"
    output_path = "downloaded_video.mp4"  # 可選

    downloader = YTDLPDownloader(yt_dlp_path)
    result = downloader.download_video(video_url, output_path)

    if result:
        print("下載成功")
    else:
        print("下載失敗")
