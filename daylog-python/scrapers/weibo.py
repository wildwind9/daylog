import base64
import asyncio
import json
import os
import re
import shutil
import time
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path
from dataclasses import dataclass, field

import httpx
import logging
import pytz
from dotenv import set_key
from playwright.async_api import async_playwright

from models import ScrapedItem
from scrapers.base import PlatformScraper

WEIBO_URL = "https://weibo.com"
CST = pytz.timezone("Asia/Shanghai")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

logger = logging.getLogger(__name__)

QR_SESSION_TTL_SECONDS = 180

# page.evaluate() has no built-in timeout; if the renderer dies (e.g. OOM-killed)
# the await never resolves. Bound every in-page fetch.
EVALUATE_TIMEOUT_SECONDS = 30
# Upper bound on /ajax/statuses/mymblog pages per sync, to cap memory and runtime.
MAX_STATUS_PAGES = 200


async def _evaluate(page, expression: str, arg=None):
    return await asyncio.wait_for(page.evaluate(expression, arg), timeout=EVALUATE_TIMEOUT_SECONDS)


@dataclass
class WeiboQrLoginSession:
    user_id: int
    session_id: str
    client: httpx.Client
    login_signin_url: str
    qrid: str
    image_base64: str
    created_at: float = field(default_factory=time.time)
    status: str = "pending"
    message: str = "请使用微博 App 扫码登录"
    uid: str = ""
    cookie_saved: bool = False

    def expired(self) -> bool:
        return time.time() - self.created_at > QR_SESSION_TTL_SECONDS


_qr_sessions: dict[str, WeiboQrLoginSession] = {}


class WeiboScraper(PlatformScraper):
    """Weibo scraper using Playwright and a reusable browser profile."""

    def __init__(self, user_id: int | None = None, binding: dict | None = None):
        self.user_id = user_id
        self.binding = binding or {}
        self.last_fetch_mode = "unknown"

    def platform(self) -> str:
        return "weibo"

    async def fetch(self, since_id: str | None = None) -> list[ScrapedItem]:
        access_token = self.binding.get("access_token")
        weibo_uid = self.binding.get("weibo_uid")
        has_browser_login_state = bool(await _resolve_uid_from_login_state(self.user_id))
        if since_id is None and weibo_uid and not has_browser_login_state:
            items = await _fetch_via_public_timeline(weibo_uid, since_id=None)
            if items:
                self.last_fetch_mode = "public_timeline"
                return sorted(items, key=lambda x: x.item_time)

        if access_token and weibo_uid and (since_id is not None or not has_browser_login_state):
            items = await _fetch_via_oauth_api(access_token, weibo_uid, since_id)
            if items:
                self.last_fetch_mode = "oauth_api"
                return sorted(items, key=lambda x: x.item_time)

        async with async_playwright() as p:
            browser = None
            profile_dir = _get_profile_dir(self.user_id)
            cookie_str = _get_weibo_cookie(self.user_id)
            # A fresh QR-login cookie beats an old browser profile, whose session may have expired.
            if _has_valid_cookie(cookie_str):
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=USER_AGENT,
                    viewport={"width": 1280, "height": 800},
                )
                await context.add_cookies(_parse_cookie_string(cookie_str))
            elif _profile_exists(profile_dir):
                context = await p.chromium.launch_persistent_context(
                    str(profile_dir),
                    headless=True,
                    user_agent=USER_AGENT,
                    viewport={"width": 1280, "height": 800},
                )
            else:
                raise RuntimeError("微博登录态不存在，请先在首页设置中完成微博登录")

            try:
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto(WEIBO_URL, wait_until="networkidle", timeout=30000)
                uid = _extract_uid(await page.content())
                if not uid:
                    raise RuntimeError("微博登录态已失效，请在首页设置中重新登录微博")

                since_int = int(since_id) if since_id else None
                all_statuses = await _collect_web_statuses(page, uid, since_int)

                items: list[ScrapedItem] = []
                for status in all_statuses:
                    item = await _parse_status(page, status)
                    if item is not None:
                        items.append(item)
            finally:
                await context.close()
                if browser:
                    await browser.close()

        self.last_fetch_mode = "web_ajax"
        return sorted(items, key=lambda x: x.item_time)


async def login_weibo(user_id: int, timeout_seconds: int = 300) -> dict:
    """Open a visible Weibo login window and persist the browser profile."""
    profile_dir = _get_profile_dir(user_id)
    profile_dir.mkdir(parents=True, exist_ok=True)
    resolved_uid = await _resolve_uid_from_login_state(user_id)
    if resolved_uid:
        return {
            "loggedIn": True,
            "uid": resolved_uid,
            "profileDir": str(profile_dir),
            "cookieSaved": _has_valid_cookie(_get_weibo_cookie(user_id)),
        }

    if os.name != "nt" and not os.getenv("DISPLAY"):
        raise RuntimeError("当前服务器没有图形界面，暂不支持直接打开微博登录窗口；请先配置该用户的微博 Cookie，或后续改为扫码登录流程")

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(profile_dir),
            headless=False,
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800},
        )
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(WEIBO_URL, wait_until="domcontentloaded", timeout=30000)

            deadline = time.monotonic() + timeout_seconds
            uid = ""
            while time.monotonic() < deadline:
                uid = _extract_uid(await page.content())
                if uid:
                    break
                await page.wait_for_timeout(1000)

            if not uid:
                raise RuntimeError("微博登录超时，请重新点击登录并完成扫码或账号登录")

            cookie_str = _format_cookie_string(await context.cookies())
            if cookie_str:
                _persist_weibo_cookie(cookie_str, user_id)

            return {
                "loggedIn": True,
                "uid": uid,
                "profileDir": str(profile_dir),
                "cookieSaved": bool(cookie_str),
            }
        finally:
            await context.close()


def get_weibo_login_status(user_id: int) -> dict:
    profile_dir = _get_profile_dir(user_id)
    cookie_configured = _has_valid_cookie(_get_weibo_cookie(user_id))
    return {
        "profileExists": _profile_exists(profile_dir),
        "cookieConfigured": cookie_configured,
        "loginStateReady": cookie_configured,
        "profileDir": str(profile_dir),
    }


async def import_weibo_cookie(user_id: int, cookie_str: str, expected_uid: str | None = None) -> dict:
    if not _has_valid_cookie(cookie_str):
        raise RuntimeError("微博网页登录 cookie 为空，请确认当前浏览器已登录微博")

    profile_dir = _get_profile_dir(user_id)
    profile_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        context = None
        try:
            context = await p.chromium.launch_persistent_context(
                str(profile_dir),
                headless=True,
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 800},
            )
            page = context.pages[0] if context.pages else await context.new_page()
            await context.add_cookies(_parse_cookie_string(cookie_str))
            await page.goto(WEIBO_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1500)
            uid = _extract_uid(await page.content())
            if not uid:
                raise RuntimeError("微博网页登录态校验失败，请重新确认微博网页已登录")
            if expected_uid and uid != expected_uid:
                raise RuntimeError("当前网页登录的微博账号和已绑定账号不一致，请切换到正确微博账号后重试")

            refreshed_cookie = _format_cookie_string(await context.cookies())
            _persist_weibo_cookie(refreshed_cookie or cookie_str, user_id)
            return {
                "uid": uid,
                "cookieConfigured": True,
                "loginStateReady": True,
                "profileDir": str(profile_dir),
            }
        finally:
            if context:
                await context.close()


def clear_weibo_login_state(user_id: int) -> dict:
    profile_dir = _get_profile_dir(user_id)
    if profile_dir.exists():
        shutil.rmtree(profile_dir, ignore_errors=True)

    env_path = Path(__file__).resolve().parents[1] / ".env"
    user_key = f"WEIBO_COOKIE_USER_{user_id}"
    set_key(str(env_path), user_key, "", quote_mode="always")
    os.environ[user_key] = ""

    if user_id == 1:
        set_key(str(env_path), "WEIBO_COOKIE", "", quote_mode="always")
        os.environ["WEIBO_COOKIE"] = ""

    return {
        "profileExists": False,
        "cookieConfigured": False,
        "loginStateReady": False,
        "profileDir": str(profile_dir),
    }


def _weibo_login_signin_headers() -> dict:
    return {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin",
        "upgrade-insecure-requests": "1",
        "user-agent": USER_AGENT,
    }


def _weibo_login_ajax_headers(referer: str, csrf_token: str | None = None) -> dict:
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "referer": referer,
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": USER_AGENT,
        "x-requested-with": "XMLHttpRequest",
    }
    if csrf_token:
        headers["x-csrf-token"] = csrf_token
    return headers


def _cleanup_expired_qr_sessions() -> None:
    expired_ids = [session_id for session_id, session in _qr_sessions.items() if session.expired()]
    for session_id in expired_ids:
        session = _qr_sessions.pop(session_id, None)
        if session:
            session.client.close()


async def start_weibo_qr_login(user_id: int) -> dict:
    _cleanup_expired_qr_sessions()
    existing_session = next((s for s in _qr_sessions.values() if s.user_id == user_id and not s.expired()), None)
    if existing_session:
        return _qr_session_to_dict(existing_session)

    client = httpx.Client(follow_redirects=True, timeout=20)
    signin_response = client.get(
        "https://passport.weibo.com/sso/signin",
        params={
            "entry": "miniblog",
            "source": "miniblog",
            "disp": "popup",
            "url": "https://weibo.com/newlogin?tabtype=weibo&gid=102803&openLoginLayer=0&url=https%3A%2F%2Fweibo.com%2F",
            "from": "weibopro",
        },
        headers=_weibo_login_signin_headers(),
    )
    signin_response.raise_for_status()
    login_signin_url = str(signin_response.url)
    csrf_token = client.cookies.get("X-CSRF-TOKEN")

    qr_response = client.get(
        "https://passport.weibo.com/sso/v2/qrcode/image",
        params={"entry": "miniblog", "size": "180"},
        headers=_weibo_login_ajax_headers(login_signin_url, csrf_token),
    )
    qr_response.raise_for_status()
    qr_data = qr_response.json().get("data") or {}
    qrid = qr_data.get("qrid")
    image_url = qr_data.get("image")
    if not qrid or not image_url:
        client.close()
        raise RuntimeError("微博二维码获取失败")

    image_response = httpx.get(image_url, timeout=20)
    image_response.raise_for_status()
    image_base64 = base64.b64encode(image_response.content).decode("ascii")

    session_id = f"weibo-qr-{user_id}-{int(time.time())}"
    session = WeiboQrLoginSession(
        user_id=user_id,
        session_id=session_id,
        client=client,
        login_signin_url=login_signin_url,
        qrid=qrid,
        image_base64=image_base64,
    )
    _qr_sessions[session_id] = session
    return _qr_session_to_dict(session)


async def get_weibo_qr_login_status(user_id: int, session_id: str) -> dict:
    _cleanup_expired_qr_sessions()
    session = _qr_sessions.get(session_id)
    if session is None or session.user_id != user_id:
        raise RuntimeError("微博二维码登录会话不存在或已失效")
    if session.expired():
        _qr_sessions.pop(session_id, None)
        session.client.close()
        raise RuntimeError("微博二维码已过期，请重新生成")

    if session.status == "completed":
        return _qr_session_to_dict(session)

    check_response = session.client.get(
        "https://passport.weibo.com/sso/v2/qrcode/check",
        params={
            "entry": "miniblog",
            "source": "miniblog",
            "url": "https://weibo.com/newlogin?tabtype=weibo&gid=102803&openLoginLayer=0&url=https%3A%2F%2Fweibo.com%2F",
            "qrid": session.qrid,
            "disp": "popup",
        },
        headers=_weibo_login_ajax_headers(session.login_signin_url, session.client.cookies.get("X-CSRF-TOKEN")),
    )
    check_response.raise_for_status()
    payload = check_response.json()
    retcode = payload.get("retcode")
    logger.info("weibo qr check user_id=%s session_id=%s retcode=%s payload=%s", user_id, session_id, retcode, payload)

    if retcode == 20000000:
        login_url = ((payload.get("data") or {}).get("url")) or ""
        if login_url:
            # Without browser navigation headers passport answers 432 and sets no SUB cookie.
            final_response = session.client.get(
                login_url,
                headers={**_weibo_login_signin_headers(), "referer": session.login_signin_url},
            )
            logger.info(
                "weibo qr final login user_id=%s session_id=%s http_status=%s cookie_keys=%s",
                user_id,
                session_id,
                final_response.status_code,
                list(session.client.cookies.keys()),
            )
        cookie_str = _cookie_string_from_client(session.client.cookies)
        if _has_valid_cookie(cookie_str):
            _persist_weibo_cookie(cookie_str, user_id)
            uid = await _resolve_uid_from_login_state(user_id)
            session.uid = uid
            session.cookie_saved = True
            session.status = "completed"
            session.message = "微博扫码登录成功"
            logger.info(
                "weibo qr persisted user_id=%s session_id=%s cookie_length=%s resolved_uid=%s",
                user_id,
                session_id,
                len(cookie_str),
                uid,
            )
        else:
            session.status = "failed"
            session.message = "微博扫码已确认，但未获取到登录凭证（SUB），请重新生成二维码再试"
            logger.warning("weibo qr missing cookie user_id=%s session_id=%s", user_id, session_id)
    elif retcode == 50114015:
        session.status = "expired"
        session.message = "微博二维码已过期，请重新生成"
    elif retcode == 50114002:
        session.message = "二维码已扫描，请在微博 App 中确认登录"
    else:
        session.message = payload.get("msg") or session.message

    return _qr_session_to_dict(session)


def _qr_session_to_dict(session: WeiboQrLoginSession) -> dict:
    return {
        "sessionId": session.session_id,
        "status": session.status,
        "message": session.message,
        "uid": session.uid,
        "cookieSaved": session.cookie_saved,
        "imageBase64": session.image_base64,
    }


async def _resolve_uid_from_login_state(user_id: int) -> str:
    profile_dir = _get_profile_dir(user_id)
    cookie_str = _get_weibo_cookie(user_id)

    if not _profile_exists(profile_dir) and not _has_valid_cookie(cookie_str):
        return ""

    async with async_playwright() as p:
        async def try_profile() -> str:
            context = None
            try:
                context = await p.chromium.launch_persistent_context(
                    str(profile_dir),
                    headless=True,
                    user_agent=USER_AGENT,
                    viewport={"width": 1280, "height": 800},
                )
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto(WEIBO_URL, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(1500)
                uid = _extract_uid(await page.content())
                if uid:
                    refreshed_cookie = _format_cookie_string(await context.cookies())
                    if refreshed_cookie:
                        _persist_weibo_cookie(refreshed_cookie, user_id)
                return uid
            finally:
                if context:
                    await context.close()

        async def try_cookie() -> str:
            browser = None
            context = None
            try:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=USER_AGENT,
                    viewport={"width": 1280, "height": 800},
                )
                await context.add_cookies(_parse_cookie_string(cookie_str))
                page = context.pages[0] if context.pages else await context.new_page()
                await page.goto(WEIBO_URL, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(1500)
                uid = _extract_uid(await page.content())
                if uid:
                    refreshed_cookie = _format_cookie_string(await context.cookies())
                    if refreshed_cookie:
                        _persist_weibo_cookie(refreshed_cookie, user_id)
                return uid
            finally:
                if context:
                    await context.close()
                if browser:
                    await browser.close()

        if _profile_exists(profile_dir):
            try:
                uid = await try_profile()
                if uid:
                    return uid
            except Exception:
                pass

        if _has_valid_cookie(cookie_str):
            try:
                return await try_cookie()
            except Exception:
                return ""

    return ""


async def _fetch_via_oauth_api(access_token: str, uid: str, since_id: str | None) -> list[ScrapedItem]:
    params = {
        "access_token": access_token,
        "uid": uid,
        "count": "100",
        "trim_user": "0",
    }
    since_int = int(since_id) if since_id else None
    all_statuses: list[dict] = []
    seen_ids: set[str] = set()
    page_number = 1

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        while page_number <= 200:
            response = await client.get(
                "https://api.weibo.com/2/statuses/user_timeline.json",
                params={**params, "page": str(page_number)},
            )
            response.raise_for_status()
            payload = response.json()
            statuses = payload.get("statuses") or []
            if not statuses:
                break

            hit_since = False
            page_added = 0
            for status in statuses:
                try:
                    sid_int = int(status.get("id", 0))
                except (TypeError, ValueError):
                    continue

                sid = str(sid_int)
                if sid in seen_ids:
                    continue
                seen_ids.add(sid)
                if since_int and sid_int <= since_int:
                    hit_since = True
                    break
                all_statuses.append(status)
                page_added += 1

            if hit_since or page_added == 0:
                break
            page_number += 1

    items: list[ScrapedItem] = []
    for status in all_statuses:
        item = _parse_oauth_status(status)
        if item is not None:
            items.append(item)
    return items


async def _fetch_via_public_timeline(uid: str, since_id: str | None) -> list[ScrapedItem]:
    try:
        return await _fetch_via_public_timeline_browser(uid, since_id)
    except Exception:
        return await _fetch_via_public_timeline_http(uid, since_id)


async def _fetch_via_public_timeline_browser(uid: str, since_id: str | None) -> list[ScrapedItem]:
    since_int = int(since_id) if since_id else None
    all_statuses: list[dict] = []
    seen_ids: set[str] = set()
    seen_cursors: set[str] = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 "
                "Mobile/15E148 Safari/604.1"
            ),
            viewport={"width": 430, "height": 932},
            locale="zh-CN",
        )
        try:
            page = await context.new_page()
            await page.goto(f"https://m.weibo.cn/u/{uid}", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1500)

            cursor: str | None = None
            while True:
                data = await _fetch_public_status_page(page, uid, cursor)
                cards = ((data or {}).get("data") or {}).get("cards") or []
                statuses = _extract_public_statuses(cards)
                if not statuses:
                    break

                hit_since = False
                page_added = 0
                for status in statuses:
                    try:
                        sid_int = int(status.get("id", 0))
                    except (TypeError, ValueError):
                        continue
                    sid = str(sid_int)
                    if sid in seen_ids:
                        continue
                    seen_ids.add(sid)
                    if since_int and sid_int <= since_int:
                        hit_since = True
                        break
                    all_statuses.append(status)
                    page_added += 1

                if hit_since or page_added == 0:
                    break
                next_cursor = _extract_public_timeline_cursor(data, statuses)
                if not next_cursor or next_cursor in seen_cursors:
                    break
                seen_cursors.add(next_cursor)
                cursor = next_cursor
        finally:
            await context.close()
            await browser.close()

    items: list[ScrapedItem] = []
    for status in all_statuses:
        item = _parse_public_status(status)
        if item is not None:
            items.append(item)
    return items


async def _fetch_via_public_timeline_http(uid: str, since_id: str | None) -> list[ScrapedItem]:
    params = {
        "type": "uid",
        "value": uid,
        "containerid": f"107603{uid}",
    }
    since_int = int(since_id) if since_id else None
    all_statuses: list[dict] = []
    seen_ids: set[str] = set()
    seen_cursors: set[str] = set()
    cursor: str | None = None

    headers = {
        "User-Agent": USER_AGENT,
        "Referer": f"https://m.weibo.cn/u/{uid}",
    }

    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as client:
        while True:
            response = await client.get(
                "https://m.weibo.cn/api/container/getIndex",
                params={**params, **({"since_id": cursor} if cursor else {})},
            )
            response.raise_for_status()
            payload = response.json()
            cards = ((payload.get("data") or {}).get("cards")) or []
            statuses = _extract_public_statuses(cards)
            if not statuses:
                break

            hit_since = False
            page_added = 0
            for status in statuses:
                try:
                    sid_int = int(status.get("id", 0))
                except (TypeError, ValueError):
                    continue
                sid = str(sid_int)
                if sid in seen_ids:
                    continue
                seen_ids.add(sid)
                if since_int and sid_int <= since_int:
                    hit_since = True
                    break
                all_statuses.append(status)
                page_added += 1

            if hit_since or page_added == 0:
                break
            next_cursor = _extract_public_timeline_cursor(payload, statuses)
            if not next_cursor or next_cursor in seen_cursors:
                break
            seen_cursors.add(next_cursor)
            cursor = next_cursor

    items: list[ScrapedItem] = []
    for status in all_statuses:
        item = _parse_public_status(status)
        if item is not None:
            items.append(item)
    return items


async def _fetch_public_status_page(page, uid: str, cursor: str | None) -> dict | None:
    try:
        raw = await _evaluate(
            page,
            """
            async ({ uid, cursor }) => {
              const url = new URL("/api/container/getIndex", location.origin);
              url.searchParams.set("type", "uid");
              url.searchParams.set("value", uid);
              url.searchParams.set("containerid", `107603${uid}`);
              if (cursor) {
                url.searchParams.set("since_id", cursor);
              }
              const response = await fetch(`${url.pathname}${url.search}`, {
                credentials: "include",
                headers: {
                  "Accept": "application/json, text/plain, */*",
                  "X-Requested-With": "XMLHttpRequest",
                },
              });
              if (!response.ok) {
                return JSON.stringify({ __status: response.status, __body: await response.text() });
              }
              return response.text();
            }
            """,
            {"uid": uid, "cursor": cursor},
        )
        data = json.loads(raw)
        if data.get("__status"):
            return None
        return data
    except Exception:
        return None


def _extract_public_timeline_cursor(payload: dict | None, statuses: list[dict]) -> str | None:
    data = (payload or {}).get("data") or {}
    cardlist_info = data.get("cardlistInfo") or {}
    next_cursor = cardlist_info.get("since_id") or cardlist_info.get("sinceid")
    if next_cursor:
        return str(next_cursor)

    for status in reversed(statuses):
        status_id = status.get("id")
        if status_id:
            return str(status_id)
    return None


def _extract_public_statuses(cards: list[dict]) -> list[dict]:
    statuses: list[dict] = []
    for card in cards:
        mblog = card.get("mblog")
        if isinstance(mblog, dict):
            statuses.append(mblog)
        for nested in card.get("card_group") or []:
            nested_mblog = nested.get("mblog")
            if isinstance(nested_mblog, dict):
                statuses.append(nested_mblog)
    return statuses


def _parse_public_status(status: dict) -> ScrapedItem | None:
    try:
        weibo_id = str(status["id"])
        summary_body = _html_to_text(status.get("raw_text") or status.get("text", ""))
        full_body = summary_body

        retweeted = status.get("retweeted_status")
        if retweeted:
            rt_user = (retweeted.get("user") or {}).get("screen_name", "")
            rt_summary = _html_to_text(retweeted.get("raw_text") or retweeted.get("text", ""))
            if rt_summary:
                full_body = (
                    f"{full_body}\n\n//@{rt_user}: {rt_summary}".strip()
                    if full_body
                    else f"//@{rt_user}: {rt_summary}"
                )

        media = _extract_media(status)
        if not media and retweeted:
            media = _extract_media(retweeted)

        created_at = _parse_created_at(status.get("created_at"))
        if created_at is None:
            return None

        user = status.get("user") or {}
        bid = status.get("bid", "")
        source_url = f"https://weibo.com/{user.get('id', '')}/{bid}" if bid else None
        content_type = "image" if media else "text"

        return ScrapedItem(
            source="weibo",
            source_id=weibo_id,
            source_url=source_url,
            content_type=content_type,
            title=_summary_title(summary_body, full_body),
            body=full_body or summary_body,
            media=media,
            item_date=created_at.date(),
            item_time=created_at.replace(tzinfo=None),
        )
    except (KeyError, ValueError):
        return None


def _parse_oauth_status(status: dict) -> ScrapedItem | None:
    try:
        weibo_id = str(status["id"])
        summary_body = _html_to_text(status.get("text", ""))
        full_body = summary_body

        retweeted = status.get("retweeted_status")
        if retweeted:
            rt_user = (retweeted.get("user") or {}).get("screen_name", "")
            rt_summary = _html_to_text(retweeted.get("text", ""))
            if rt_summary:
                full_body = (
                    f"{full_body}\n\n//@{rt_user}: {rt_summary}".strip()
                    if full_body
                    else f"//@{rt_user}: {rt_summary}"
                )

        media = _extract_media(status)
        if not media and retweeted:
            media = _extract_media(retweeted)

        created_at = datetime.strptime(
            status["created_at"], "%a %b %d %H:%M:%S %z %Y"
        ).astimezone(CST)

        user = status.get("user") or {}
        source_url = f"https://weibo.com/{user.get('id', '')}/{status.get('id', '')}"
        content_type = "image" if media else "text"

        return ScrapedItem(
            source="weibo",
            source_id=weibo_id,
            source_url=source_url,
            content_type=content_type,
            title=_summary_title(summary_body, full_body),
            body=full_body or summary_body,
            media=media,
            item_date=created_at.date(),
            item_time=created_at.replace(tzinfo=None),
        )
    except (KeyError, ValueError):
        return None


def _parse_created_at(value: str | None) -> datetime | None:
    if not value:
        return None

    raw = value.strip()
    now = datetime.now(CST)

    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%m-%d %H:%M", "%m-%d"):
        try:
            parsed = datetime.strptime(raw, fmt)
            if fmt == "%a %b %d %H:%M:%S %z %Y":
                return parsed.astimezone(CST)
            if fmt.startswith("%m-%d"):
                parsed = parsed.replace(year=now.year)
            return CST.localize(parsed)
        except ValueError:
            continue

    if raw == "刚刚":
        return now

    minutes_match = re.fullmatch(r"(\d+)\s*分钟前", raw)
    if minutes_match:
        return now - timedelta(minutes=int(minutes_match.group(1)))

    hours_match = re.fullmatch(r"(\d+)\s*小时前", raw)
    if hours_match:
        return now - timedelta(hours=int(hours_match.group(1)))

    if raw.startswith("今天 "):
        try:
            parsed_time = datetime.strptime(raw[3:].strip(), "%H:%M").time()
            return now.replace(
                hour=parsed_time.hour,
                minute=parsed_time.minute,
                second=0,
                microsecond=0,
            )
        except ValueError:
            return now

    if raw.startswith("昨天 "):
        try:
            parsed_time = datetime.strptime(raw[3:].strip(), "%H:%M").time()
            yesterday = now - timedelta(days=1)
            return yesterday.replace(
                hour=parsed_time.hour,
                minute=parsed_time.minute,
                second=0,
                microsecond=0,
            )
        except ValueError:
            return now - timedelta(days=1)

    return None


async def _parse_status(page, status: dict) -> ScrapedItem | None:
    try:
        weibo_id = str(status["id"])
        summary_body = _html_to_text(status.get("text", ""))
        full_body = await _extract_status_body(page, status)

        retweeted = status.get("retweeted_status")
        if retweeted:
            rt_user = (retweeted.get("user") or {}).get("screen_name", "")
            rt_summary = _html_to_text(retweeted.get("text", ""))
            rt_full = await _extract_status_body(page, retweeted)
            if rt_summary:
                summary_body = (
                    f"{summary_body}\n\n//@{rt_user}: {rt_summary}".strip()
                    if summary_body
                    else f"//@{rt_user}: {rt_summary}"
                )
            if rt_full:
                full_body = (
                    f"{full_body}\n\n//@{rt_user}: {rt_full}".strip()
                    if full_body
                    else f"//@{rt_user}: {rt_full}"
                )

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
            title=_summary_title(summary_body, full_body),
            body=full_body or summary_body,
            media=media,
            item_date=created_at.date(),
            item_time=created_at.replace(tzinfo=None),
        )
    except (KeyError, ValueError):
        return None


async def _collect_web_statuses(page, uid: str, since_int: int | None) -> list[dict]:
    """Page through /ajax/statuses/mymblog until since_id, an empty/repeated page, or MAX_STATUS_PAGES."""
    all_statuses: list[dict] = []
    seen_ids: set[int] = set()
    for pg in range(1, MAX_STATUS_PAGES + 1):
        data = await _fetch_status_page(page, uid, pg)
        if data is None and pg == 1:
            await asyncio.sleep(1.5)
            data = await _fetch_status_page(page, uid, pg)
        if data is None:
            break
        lst = (data.get("data") or {}).get("list", [])
        if not lst:
            break
        hit_since = False
        page_added = 0
        for status in lst:
            try:
                sid_int = int(status.get("id", 0))
            except (TypeError, ValueError):
                continue
            if sid_int in seen_ids:
                continue
            seen_ids.add(sid_int)
            if since_int and sid_int <= since_int:
                hit_since = True
                break
            all_statuses.append(status)
            page_added += 1
        if hit_since or page_added == 0:
            break
    else:
        logger.warning("Weibo web sync stopped at MAX_STATUS_PAGES=%s for uid=%s", MAX_STATUS_PAGES, uid)
    return all_statuses


async def _fetch_status_page(page, uid: str, page_number: int) -> dict | None:
    try:
        raw = await _evaluate(
            page,
            """
            async ({ uid, pageNumber }) => {
              const url = new URL("/ajax/statuses/mymblog", location.origin);
              url.searchParams.set("uid", uid);
              url.searchParams.set("page", String(pageNumber));
              url.searchParams.set("feature", "0");
              const response = await fetch(`${url.pathname}${url.search}`, { credentials: "include" });
              if (!response.ok) {
                return JSON.stringify({ __status: response.status, __body: await response.text() });
              }
              return response.text();
            }
            """,
            {"uid": uid, "pageNumber": page_number},
        )
        data = json.loads(raw)
        if data.get("__status"):
            return None
        return data
    except Exception:
        return None


async def _extract_status_body(page, status: dict) -> str:
    list_text = _html_to_text(status.get("text_raw") or status.get("text", ""))
    status_id = str(status.get("id") or "")
    if not status_id or not _is_long_status(status, list_text):
        return list_text

    long_text = await _fetch_long_text(page, status_id)
    return _html_to_text(long_text) or list_text


def _is_long_status(status: dict, list_text: str) -> bool:
    return bool(
        status.get("isLongText")
        or status.get("longText")
        or status.get("longTextContent")
        or list_text.endswith("...")
        or list_text.endswith("全文")
    )


async def _fetch_long_text(page, status_id: str) -> str | None:
    try:
        return await _evaluate(
            page,
            """
            async (statusId) => {
              const response = await fetch(
                `/ajax/statuses/longtext?id=${encodeURIComponent(statusId)}`,
                { credentials: "include" },
              );
              if (!response.ok) return null;
              const payload = await response.json();
              return payload?.data?.longTextContent
                ?? payload?.data?.long_text
                ?? payload?.data?.text
                ?? payload?.longTextContent
                ?? null;
            }
            """,
            status_id,
        )
    except Exception:
        return None


def _extract_uid(html: str) -> str:
    match = re.search(r'"uid"\s*:\s*"?(\d+)', html or "")
    return match.group(1) if match else ""


def _summary_title(summary_body: str, full_body: str) -> str | None:
    if not summary_body or summary_body == full_body:
        return None
    return summary_body[:512]


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r'<img[^>]+alt="([^"]*)"[^>]*/?>',  r'\1', html)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    return unescape(text).strip()


def _extract_media(status: dict) -> list[str] | None:
    urls: list[str] = []

    pic_ids = status.get("pic_ids") or []
    pic_infos = status.get("pic_infos") or {}
    for pid in pic_ids:
        info = pic_infos.get(str(pid), {})
        url = _pick_media_url(info)
        if url:
            urls.append(url)

    for pic in status.get("pic_urls") or []:
        url = _pick_media_url(pic)
        if url:
            urls.append(url)

    for pic in status.get("pics") or []:
        url = _pick_media_url(pic)
        if url:
            urls.append(url)

    mix_media = (status.get("mix_media_info") or {}).get("items") or []
    for media_item in mix_media:
        url = _pick_media_url(media_item.get("data") or media_item)
        if url:
            urls.append(url)

    page_info = status.get("page_info") or {}
    page_pic_url = _pick_media_url(page_info.get("page_pic") or {})
    if page_pic_url:
        urls.append(page_pic_url)

    unique_urls = list(dict.fromkeys(urls))
    return unique_urls or None


def _pick_media_url(info: dict | str | None) -> str | None:
    if isinstance(info, str):
        return _normalize_media_url(info)
    if not isinstance(info, dict):
        return None

    candidates = [
        info.get("url"),
        info.get("largest", {}).get("url") if isinstance(info.get("largest"), dict) else None,
        info.get("large", {}).get("url") if isinstance(info.get("large"), dict) else None,
        info.get("original", {}).get("url") if isinstance(info.get("original"), dict) else None,
        info.get("bmiddle", {}).get("url") if isinstance(info.get("bmiddle"), dict) else None,
        info.get("thumbnail", {}).get("url") if isinstance(info.get("thumbnail"), dict) else None,
        info.get("mw2000", {}).get("url") if isinstance(info.get("mw2000"), dict) else None,
        info.get("thumbnail_pic"),
        info.get("page_pic", {}).get("url") if isinstance(info.get("page_pic"), dict) else None,
    ]
    for candidate in candidates:
        normalized = _normalize_media_url(candidate)
        if normalized:
            return normalized
    return None


def _normalize_media_url(url: str | None) -> str | None:
    if not url:
        return None
    normalized = f"https:{url}" if url.startswith("//") else url
    normalized = normalized.replace("http://", "https://")
    normalized = normalized.replace("/thumbnail/", "/large/")
    normalized = normalized.replace("/orj360/", "/large/")
    normalized = normalized.replace("/wap360/", "/large/")
    return normalized


def _parse_cookie_string(cookie_str: str) -> list[dict]:
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


def _format_cookie_string(cookies: list[dict]) -> str:
    return "; ".join(
        f"{cookie['name']}={cookie['value']}"
        for cookie in cookies
        if cookie.get("name") and cookie.get("value")
        and any((cookie.get("domain") or "").endswith(domain) for domain in ("weibo.com", "weibo.cn", "sina.com.cn"))
    )


def _has_valid_cookie(cookie_str: str) -> bool:
    """A usable Weibo web login state must carry the SUB session cookie."""
    if not cookie_str or cookie_str == "your-weibo-cookie-here":
        return False
    names = {part.split("=", 1)[0].strip() for part in cookie_str.split(";") if "=" in part}
    return "SUB" in names


def _cookie_string_from_client(cookies) -> str:
    """Flatten an httpx cookie jar; same-named cookies on several domains prefer weibo.com."""
    jar = getattr(cookies, "jar", None)
    if jar is None:
        values = dict(cookies)
    else:
        values = {}
        for cookie in sorted(jar, key=lambda c: (c.domain or "").endswith("weibo.com")):
            values[cookie.name] = cookie.value
    return "; ".join(f"{key}={value}" for key, value in values.items())


def _get_profile_base_dir() -> Path:
    project_dir = Path(__file__).resolve().parents[1]
    configured_dir = os.getenv("WEIBO_PROFILE_DIR")
    if configured_dir:
        profile_dir = Path(configured_dir)
        base_dir = profile_dir if profile_dir.is_absolute() else project_dir / profile_dir
    else:
        base_dir = project_dir / ".browser" / "weibo-profile"
    if re.fullmatch(r"user-\d+", base_dir.name):
        return base_dir.parent
    return base_dir


def _is_legacy_profile_dir(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    if any(child.is_dir() and re.fullmatch(r"user-\d+", child.name) for child in path.iterdir()):
        return False
    return any(child.name in {"Default", "Local State", "First Run", "Cookies"} for child in path.iterdir())


def _get_profile_dir(user_id: int | None = None) -> Path:
    base_dir = _get_profile_base_dir()
    if user_id is None:
        return base_dir
    if _is_legacy_profile_dir(base_dir):
        if user_id == 1:
            return base_dir
        return base_dir.parent / f"{base_dir.name}-users" / f"user-{user_id}"
    return base_dir / f"user-{user_id}"


def _profile_exists(profile_dir: Path) -> bool:
    return profile_dir.exists() and any(profile_dir.iterdir())


def _legacy_weibo_cookie() -> str:
    return os.getenv("WEIBO_COOKIE", "")


def _get_weibo_cookie(user_id: int | None = None) -> str:
    if user_id:
        user_cookie = os.getenv(f"WEIBO_COOKIE_USER_{user_id}", "")
        if _has_valid_cookie(user_cookie):
            return user_cookie
        if user_id == 1:
            legacy_cookie = _legacy_weibo_cookie()
            if _has_valid_cookie(legacy_cookie):
                _persist_weibo_cookie(legacy_cookie, 1)
                return legacy_cookie
        return ""
    return _legacy_weibo_cookie()


def _persist_weibo_cookie(cookie_str: str, user_id: int) -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    user_key = f"WEIBO_COOKIE_USER_{user_id}"
    set_key(str(env_path), user_key, cookie_str, quote_mode="always")
    os.environ[user_key] = cookie_str
