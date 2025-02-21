from detection import WebsiteDetector
# from downloader import YTDLPDownloader
# from uploader import YouTubeUploader
import asyncio

import json

async def main():
    with open("latest.json", "r", encoding="utf-8") as file:
        latest_data = json.load(file)
    item_number = 0
    all_items = []

    detector = WebsiteDetector(
        url="https://www.twitch.tv/shxtou/videos?filter=archives&sort=time",
        item_selector=f"//*[@data-a-target='video-tower-card-{item_number}']",
        headless=True,
        wait_time=600,
    )

    while True:
        await detector.detect_once()
        detected_item = detector.last_items
        print(detected_item)
        if detected_item == latest_data:
            break
        
        all_items.append(detected_item)
        
        item_number += 1
        detector.item_selector = f"//*[@data-a-target='video-tower-card-{item_number}']"

    if all_items:
        with open("latest.json", "w") as file:
            json.dump(all_items[0], file)

        for item in all_items:
            value = next(iter(item.values()))
            print(value)

if __name__=="__main__":
    asyncio.run(main())