from abc import ABC, abstractmethod
from models import ScrapedItem


class PlatformScraper(ABC):
    """所有平台爬虫的统一抽象接口。
    新增平台只需继承此类并实现 fetch 方法，然后在 main.py 注册即可。
    """

    @abstractmethod
    def platform(self) -> str:
        """返回平台标识符，如 'weibo'"""
        ...

    @abstractmethod
    async def fetch(self, since_id: str | None = None) -> list[ScrapedItem]:
        """增量抓取内容。

        Args:
            since_id: 上次抓取的最新 source_id，仅抓取比它更新的内容。
                      为 None 时抓取最近一批。

        Returns:
            ScrapedItem 列表，按时间升序排列。
        """
        ...
