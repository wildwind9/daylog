from models import ScrapedItem
from scrapers.base import PlatformScraper


class XiaohongshuScraper(PlatformScraper):
    """小红书爬虫（占位实现，后期填充）"""

    def platform(self) -> str:
        return "xiaohongshu"

    async def fetch(self, since_id: str | None = None) -> list[ScrapedItem]:
        raise NotImplementedError("小红书爬虫尚未实现")
