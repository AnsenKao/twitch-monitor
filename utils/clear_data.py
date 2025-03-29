import os


def clear_empty_data(root):
    files = os.listdir(root)
    for file in files:
        file_path = os.path.join(root, file)
        if os.path.isfile(file_path) and os.path.getsize(file_path) == 0:
            os.remove(file_path)
