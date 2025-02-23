import os


def clear_videos(videos_root):
    files = os.listdir(videos_root)
    for file in files:
        file_path = os.path.join(videos_root, file)
        if os.path.isfile(file_path):
            os.remove(file_path)
