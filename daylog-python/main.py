"""Daylog Python 微服务 - FastAPI 入口"""
import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response

# 显式指定 .env 路径，避免后台启动时工作目录不对导致加载失败
_ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(_ENV_PATH, override=True)

from analyzers.llm import extract_tags
from db.repository import (
    get_items_without_tags,
    get_latest_source_id,
    save_items,
    save_tags,
)
from models import ScrapeResult
from scrapers.base import PlatformScraper
from scrapers.douyin import DouyinScraper
from scrapers.weibo import WeiboScraper
from scrapers.xiaohongshu import XiaohongshuScraper

# ── 平台注册表：新增平台只需在此处加一行 ──────────────────────────
SCRAPERS: dict[str, PlatformScraper] = {
    "weibo":       WeiboScraper(),
    "douyin":      DouyinScraper(),
    "xiaohongshu": XiaohongshuScraper(),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Daylog Python service started")
    yield
    print("Daylog Python service stopped")


app = FastAPI(
    title="Daylog Python Service",
    description="负责多平台内容抓取和 AI 标签分析",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/proxy/img")
async def proxy_img(url: str):
    """代理图片请求，解决第三方图床防盗链问题"""
    allowed_hosts = ("sinaimg.cn", "sina.com.cn", "weibo.com", "weibo.net")
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    if not any(host.endswith(h) for h in allowed_hosts):
        raise HTTPException(status_code=403, detail="不允许代理该域名")
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        r = await client.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://weibo.com/",
        })
    return Response(
        content=r.content,
        media_type=r.headers.get("content-type", "image/jpeg"),
    )


@app.post("/scrape/{platform}", response_model=ScrapeResult)
async def scrape(platform: str, full: bool = False):
    """触发指定平台的内容抓取和标签分析。full=true 时忽略 since_id，全量重抓"""
    if platform not in SCRAPERS:
        raise HTTPException(status_code=404, detail=f"未知平台: {platform}")

    scraper = SCRAPERS[platform]

    try:
        since_id = None if full else get_latest_source_id(platform)
        items = await scraper.fetch(since_id=since_id)

        if not items:
            return ScrapeResult(platform=platform, new_count=0, status="success")

        # 写入数据库
        item_dicts = [item.model_dump() for item in items]
        new_count = save_items(item_dicts)

        # 异步打标签（不阻塞抓取结果返回）
        asyncio.create_task(_analyze_new_items(platform))

        return ScrapeResult(platform=platform, new_count=new_count, status="success")

    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        return ScrapeResult(platform=platform, new_count=0,
                            status="failed", error=str(e))


@app.post("/analyze/{platform}")
async def analyze(platform: str):
    """手动触发标签分析（处理尚未打标签的内容）"""
    await _analyze_new_items(platform)
    return {"status": "ok"}


async def _analyze_new_items(platform: str) -> None:
    """为没有标签的内容条目批量打标签"""
    pending = get_items_without_tags(platform, limit=50)
    for row in pending:
        try:
            tags = await extract_tags(row["body"])
            if tags:
                save_tags(row["id"], tags, source="llm")
        except Exception as e:
            print(f"Tag analysis failed for item {row['id']}: {e}")


if __name__ == "__main__":
    import sys
    import uvicorn
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    uvicorn.run("main:app", host="0.0.0.0",
                port=int(os.getenv("PORT", 8000)), reload=False)
