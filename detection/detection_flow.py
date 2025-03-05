from detection import WebsiteDetector
from utils import setup_logger
import asyncio
import json

logger = setup_logger("log")


class DetectionFlow(WebsiteDetector):
    def __init__(self, url, item_selector, headless=True, wait_time=600):
        super().__init__(url, item_selector, headless, wait_time)
        self.latest_data = self.load_latest_data()
        self.item_number = 0
        self.all_items = []

    def load_latest_data(self):
        try:
            with open("latest.json", "r", encoding="utf-8") as file:
                latest_data = json.load(file)
                logger.info(f"Successfully loaded latest.json: {latest_data}")
                return latest_data
        except FileNotFoundError:
            logger.error("latest.json not found")
            return {}

    async def detect_items(self):
        while True:
            logger.info(f"Detecting item number: {self.item_number}")
            await self.detect_once()
            detected_item = self.last_items

            if detected_item == self.latest_data and self.item_number == 0:
                logger.info("No new items detected, ending detection")
                break

            elif detected_item == self.latest_data:
                logger.info("Update to latest!")
                break

            logger.info(f"New item detected: {detected_item}")
            self.all_items.append(detected_item)

            self.item_number += 1
            self.item_selector = (
                f"//*[@data-a-target='video-tower-card-{self.item_number}']"
            )

    def update_latest(self):
        if self.all_items:
            logger.info(f"Total new items found: {len(self.all_items)}")
            try:
                with open("latest.json", "w", encoding="utf-8") as file:
                    json.dump(self.all_items[0], file)
                    logger.info("Successfully updated latest.json")
            except Exception as e:
                logger.error(f"Error updating latest.json: {str(e)}")
        else:
            logger.info("No new items to process")

    async def run(self):
        await self.detect_items()
        self.update_latest()
        self.close()
        return {k: v for d in self.all_items for k, v in d.items()}


if __name__ == "__main__":
    flow = DetectionFlow(
        url="https://www.twitch.tv/shxtou/videos?filter=archives&sort=time",
    )
    asyncio.run(flow.run())
