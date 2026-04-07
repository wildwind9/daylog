from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel


class ScrapedItem(BaseModel):
    """爬虫抓取结果的统一格式，对应数据库 content_item 表"""
    source: str                          # weibo / douyin / xiaohongshu
    source_id: str
    source_url: Optional[str] = None
    content_type: str = "text"           # text / image / video
    title: Optional[str] = None
    body: Optional[str] = None
    body_format: str = "plain"
    media: Optional[list[str]] = None    # 图片/视频 URL 列表
    item_date: date
    item_time: datetime


class ScrapeResult(BaseModel):
    platform: str
    new_count: int
    status: str                          # success / failed
    error: Optional[str] = None
