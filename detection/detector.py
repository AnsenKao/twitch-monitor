from typing import Optional, Dict
from datetime import datetime
import json
from dataclasses import dataclass
import asyncio
from playwright.async_api import async_playwright


@dataclass
class DetectionResult:
    """檢測結果的資料類別"""

    timestamp: datetime
    url: str
    items: Dict[str, str]
    changed: bool = False
    error: Optional[str] = None


class WebsiteDetector:
    def __init__(
        self, url: str, item_selector: str, headless: bool = True, wait_time: int = 10
    ):
        self.url = url
        self.item_selector = item_selector
        self.wait_time = wait_time
        self.last_items: Dict[str, str] = {}
        self.headless = headless

    async def detect_once(self) -> bool:
        """
        執行單次檢測
        Returns:
            bool: 如果內容有變化返回 True，否則返回 False
        """
        try:
            items = await self._detect_async()
            self.last_items = items
            return True
        except Exception as e:
            print(f"Error detecting items: {str(e)}")
            return False

    async def _detect_async(self) -> Dict[str, str]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()
            await page.goto(self.url)
            await page.wait_for_selector(self.item_selector, timeout=self.wait_time * 1000)
            elements = await page.query_selector_all(self.item_selector)
            items = {}
            for element in elements:
                text = await element.inner_text()
                a_tag = await element.query_selector('a')
                href = await a_tag.get_attribute('href') if a_tag else ""
                # 自動補全 Twitch 相對路徑
                if href and not href.startswith("http"):
                    href = f"https://www.twitch.tv{href}"
                items[text.strip().split("\n")[0]] = href.replace(" ", "") if href else ""
            await browser.close()
            return items

    async def monitor(self, interval_seconds: int = 60) -> None:
        """
        持續監測網站

        Args:
            interval_seconds: 檢測間隔（秒）
        """
        while True:
            has_changed = await self.detect_once()
            if has_changed:
                print(f"Changes detected at {datetime.now()}!")
                print(
                    f"Current items: {json.dumps(self.last_items, indent=2, ensure_ascii=False)}"
                )
                return True
            await asyncio.sleep(interval_seconds)

    def close(self):
        pass  # Playwright 自動關閉

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":

    async def main():
        detector = WebsiteDetector(
            url="https://www.twitch.tv/shxtou/videos?filter=archives&sort=time",
            item_selector='[data-a-target^="video-tower-card-"]',
            headless=True,
            wait_time=15,
        )
        try:
            await detector.detect_once()
            print(f"Current items: {detector.last_items}")
        finally:
            detector.close()

    # 使用 asyncio 運行異步主函數
    asyncio.run(main())
