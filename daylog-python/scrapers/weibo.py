import json
import os
import re
from datetime import datetime

import pytz
from playwright.async_api import async_playwright

from models import ScrapedItem
from scrapers.base import PlatformScraper

WEIBO_URL = "https://weibo.com"
CST = pytz.timezone("Asia/Shanghai")


class WeiboScraper(PlatformScraper):
    """微博爬虫：使用 Playwright + Cookie 抓取 weibo.com 桌面版 API"""

    def platform(self) -> str:
        return "weibo"

    async def fetch(self, since_id: str | None = None) -> list[ScrapedItem]:
        cookie_str = os.getenv("WEIBO_COOKIE", "")
        if not cookie_str:
            raise RuntimeError("WEIBO_COOKIE 未配置，请先在 .env 中填入 Cookie")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
            )

            await context.add_cookies(_parse_cookie_string(cookie_str))
            page = await context.new_page()

            await page.goto(WEIBO_URL, wait_until="networkidle", timeout=30000)
            html = await page.content()
            m = re.search(r'"uid"\s*:\s*"?(\d+)', html)
            if not m:
                await browser.close()
                raise RuntimeError("无法从页面获取 uid，Cookie 可能已失效")
            uid = m.group(1)

            all_statuses: list[dict] = []
            since_int = int(since_id) if since_id else None
            for pg in range(1, 2000):
                js = (
                    f'fetch("/ajax/statuses/mymblog?uid={uid}&page={pg}&feature=0",'
                    '{credentials:"include"}).then(r=>r.text())'
                )
                raw = await page.evaluate(js)
                try:
                    data = json.loads(raw)
                except Exception:
                    break
                lst = (data.get("data") or {}).get("list", [])
                if not lst:
                    break
                hit_since = False
                for s in lst:
                    try:
                        sid_int = int(s.get("id", 0))
                    except (TypeError, ValueError):
                        continue
                    if since_int and sid_int <= since_int:
                        hit_since = True
                        break
                    all_statuses.append(s)
                if hit_since:
                    break

            await browser.close()

        items: list[ScrapedItem] = []
        for status in all_statuses:
            item = _parse_status(status)
            if item is not None:
                items.append(item)

        return sorted(items, key=lambda x: x.item_time)


# ── 解析单条微博 ──────────────────────────────────────────────


def _parse_status(status: dict) -> ScrapedItem | None:
    try:
        weibo_id = str(status["id"])
        body = _html_to_text(status.get("text", ""))

        # 转发：附加原微博内容
        retweeted = status.get("retweeted_status")
        if retweeted:
            rt_user = (retweeted.get("user") or {}).get("screen_name", "")
            rt_body = _html_to_text(retweeted.get("text", ""))
            if rt_body:
                body = f"{body}\n\n//@{rt_user}: {rt_body}".strip() if body else f"//@{rt_user}: {rt_body}"

        # 图片：主帖优先，没有再取转发的图
        media = _extract_media(status)
        if not media and retweeted:
            media = _extract_media(retweeted)

        created_at = datetime.strptime(
            status["created_at"], "%a %b %d %H:%M:%S %z %Y"
        ).astimezone(CST)

        user = status.get("user") or {}
        bid = status.get("bid", "")
        source_url = f"https://weibo.com/{user.get('id', '')}/{bid}" if bid else None
        content_type = "image" if media else "text"

        return ScrapedItem(
            source="weibo",
            source_id=weibo_id,
            source_url=source_url,
            content_type=content_type,
            body=body,
            media=media,
            item_date=created_at.date(),
            item_time=created_at.replace(tzinfo=None),
        )
    except (KeyError, ValueError):
        return None


def _html_to_text(html: str) -> str:
    """微博 HTML 正文 → 纯文本，保留 emoji alt 文字和换行"""
    if not html:
        return ""
    # <img alt="[emoji]"> → [emoji]
    text = re.sub(r'<img[^>]+alt="([^"]*)"[^>]*/?>',  r'\1', html)
    # <br> → 换行
    text = re.sub(r'<br\s*/?>', "\n", text)
    # 去除剩余 HTML 标签
    text = re.sub(r"<[^>]+>", "", text)
    # 清理零宽字符
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    return text.strip()


def _extract_media(status: dict) -> list[str] | None:
    """从 weibo.com API 的 pic_ids + pic_infos 中提取原图 URL"""
    pic_ids = status.get("pic_ids") or []
    pic_infos = status.get("pic_infos") or {}
    if not pic_ids:
        return None
    urls = []
    for pid in pic_ids:
        info = pic_infos.get(str(pid), {})
        # 按清晰度优先：original > large > bmiddle > thumbnail
        url = (
            (info.get("original") or info.get("large") or
             info.get("bmiddle") or info.get("thumbnail") or {})
            .get("url")
        )
        if url:
            urls.append(url)
    return urls or None


def _parse_cookie_string(cookie_str: str) -> list[dict]:
    """将浏览器复制的 Cookie 字符串注入到多个域名"""
    cookies = []
    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        name, _, value = part.partition("=")
        name, value = name.strip(), value.strip()
        for domain in (".weibo.com", ".weibo.cn", ".sina.com.cn"):
            cookies.append({"name": name, "value": value, "domain": domain, "path": "/"})
    return cookies
