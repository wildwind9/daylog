"""Daylog Python service entrypoint."""
import asyncio
import os
from collections import defaultdict
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import Response

_ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(_ENV_PATH, override=True)

from analyzers.llm import extract_tags, infer_mood_from_tags
from db.repository import (
    clear_tags_for_platform,
    get_items_without_tags,
    get_latest_source_id,
    get_weibo_binding_auth,
    save_items,
    save_tags,
    update_mood_for_item_date,
)
from models import ScrapeResult
from scrapers.base import PlatformScraper
from scrapers.douyin import DouyinScraper
from scrapers.weibo import (
    WeiboScraper,
    clear_weibo_login_state,
    get_weibo_login_status,
    login_weibo,
    start_weibo_qr_login,
    get_weibo_qr_login_status,
)
from scrapers.xiaohongshu import XiaohongshuScraper

SCRAPERS: dict[str, PlatformScraper] = {
    "weibo": WeiboScraper(),
    "douyin": DouyinScraper(),
    "xiaohongshu": XiaohongshuScraper(),
}
ANALYZABLE_SOURCES = {*SCRAPERS.keys(), "manual"}
# Hard cap for a single /scrape call. Must stay below the backend's client timeout.
SCRAPE_TIMEOUT_SECONDS = int(os.getenv("SCRAPE_TIMEOUT_SECONDS", "900"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Daylog Python service started")
    yield
    print("Daylog Python service stopped")


app = FastAPI(
    title="Daylog Python Service",
    description="Handles multi-platform content scraping and AI tag analysis.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/weibo/login/status")
def weibo_login_status(userId: int):
    return get_weibo_login_status(userId)


@app.post("/weibo/login")
async def start_weibo_login(userId: int, timeout_seconds: int = 300):
    try:
        return await login_weibo(user_id=userId, timeout_seconds=timeout_seconds)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/weibo/login/qr")
async def start_weibo_login_qr(userId: int):
    try:
        return await start_weibo_qr_login(userId)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/weibo/login/qr/{session_id}")
async def get_weibo_login_qr_status(session_id: str, userId: int):
    try:
        return await get_weibo_qr_login_status(userId, session_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/weibo/login/state")
def delete_weibo_login_state(userId: int):
    try:
        return clear_weibo_login_state(userId)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/proxy/img")
async def proxy_img(url: str):
    """Proxy image requests to avoid third-party anti-hotlinking issues."""
    allowed_hosts = ("sinaimg.cn", "sina.com.cn", "weibo.com", "weibo.net")
    from urllib.parse import urlparse

    host = urlparse(url).hostname or ""
    if not any(host.endswith(candidate) for candidate in allowed_hosts):
        raise HTTPException(status_code=403, detail="Unsupported image host")

    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        response = await client.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
                ),
                "Referer": "https://weibo.com/",
            },
        )

    return Response(
        content=response.content,
        media_type=response.headers.get("content-type", "image/jpeg"),
    )


@app.post("/scrape/{platform}", response_model=ScrapeResult)
async def scrape(platform: str, userId: int, full: bool = False, bindingId: int | None = None):
    """Trigger platform scraping. When full=true, ignore since_id and rescan all content."""
    if platform not in SCRAPERS:
        raise HTTPException(status_code=404, detail=f"Unknown platform: {platform}")

    weibo_binding = get_weibo_binding_auth(userId, binding_id=bindingId) if platform == "weibo" else None
    scraper = WeiboScraper(user_id=userId, binding=weibo_binding) if platform == "weibo" else SCRAPERS[platform]

    try:
        since_id = None if full else get_latest_source_id(platform, userId, binding_id=bindingId)
        try:
            items = await asyncio.wait_for(scraper.fetch(since_id=since_id), timeout=SCRAPE_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            raise RuntimeError(f"抓取超时（超过 {SCRAPE_TIMEOUT_SECONDS} 秒），已中止")

        if not items:
            return ScrapeResult(platform=platform, new_count=0, fetched_count=0, status="success")

        item_dicts = [item.model_dump() for item in items]
        new_count = save_items(item_dicts, userId, binding_id=bindingId)

        asyncio.create_task(_analyze_new_items(platform, userId))

        return ScrapeResult(
            platform=platform,
            new_count=new_count,
            fetched_count=len(items),
            status="success",
            mode=getattr(scraper, "last_fetch_mode", None),
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    except Exception as exc:
        return ScrapeResult(
            platform=platform,
            new_count=0,
            fetched_count=0,
            status="failed",
            error=str(exc),
            mode=getattr(scraper, "last_fetch_mode", None),
        )


@app.post("/analyze/{platform}")
async def analyze(platform: str, userId: int, force: bool = False):
    """Analyze tags for content that does not have tags yet."""
    if platform not in ANALYZABLE_SOURCES:
        raise HTTPException(status_code=404, detail=f"Unknown platform: {platform}")

    cleared = clear_tags_for_platform(platform, userId) if force else 0
    analyzed = await _analyze_new_items(platform, userId, limit=500 if force else 50, all_batches=force)
    return {"status": "ok", "cleared": cleared, "analyzed": analyzed}


async def _analyze_new_items(
    platform: str,
    user_id: int,
    limit: int = 50,
    all_batches: bool = False,
) -> int:
    """Analyze tags for untagged items in batches."""
    analyzed = 0
    while True:
        pending = get_items_without_tags(platform, user_id=user_id, limit=limit)
        if not pending:
            break

        daily_tags: dict[str, list[str]] = defaultdict(list)
        daily_item_ids: dict[str, int] = {}

        for row in pending:
            try:
                tags = await extract_tags(row["body"])
                if tags:
                    save_tags(row["id"], tags, source="llm")
                    if platform == "weibo":
                        item_date = str(row["item_date"]) if row.get("item_date") else ""
                        if item_date:
                            daily_tags[item_date].extend(tags)
                            daily_item_ids.setdefault(item_date, row["id"])
                    else:
                        mood = infer_mood_from_tags(tags)
                        if mood:
                            update_mood_for_item_date(row["id"], mood)
                    analyzed += 1
            except Exception as exc:
                print(f"Tag analysis failed for item {row['id']}: {exc}")

        if platform == "weibo":
            for item_date, tags in daily_tags.items():
                mood = infer_mood_from_tags(tags)
                if mood:
                    update_mood_for_item_date(daily_item_ids[item_date], mood)

        if not all_batches or len(pending) < limit:
            break
    return analyzed


if __name__ == "__main__":
    import sys
    import uvicorn

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)
