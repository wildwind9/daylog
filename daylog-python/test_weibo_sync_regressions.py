import unittest
from unittest.mock import AsyncMock, patch

from db.repository import _merge_item_with_existing
from scrapers.weibo import (
    WeiboScraper,
    _extract_media,
    _fetch_via_oauth_api,
    _fetch_via_public_timeline,
    _fetch_via_public_timeline_http,
)


def _build_status(status_id: int) -> dict:
    return {
        "id": status_id,
        "text": f"微博 {status_id}",
        "created_at": "Tue Apr 15 12:00:00 +0800 2026",
        "user": {"id": 12345},
    }


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, pages: dict[int, list[dict]], *args, **kwargs):
        self.pages = pages
        self.calls: list[dict | None] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, params: dict | None = None):
        self.calls.append(dict(params or {}))
        page = int((params or {}).get("page", "1"))
        return _FakeResponse({"statuses": self.pages.get(page, [])})


class WeiboSyncRegressionTest(unittest.IsolatedAsyncioTestCase):
    async def test_full_sync_falls_back_to_oauth_when_browser_login_state_is_missing(self):
        scraper = WeiboScraper(user_id=7, binding={"access_token": "token", "weibo_uid": "12345"})
        oauth_item = type("Item", (), {"item_time": 2, "source_id": "42"})()

        with (
            patch("scrapers.weibo._fetch_via_public_timeline", new=AsyncMock(return_value=[])),
            patch("scrapers.weibo._fetch_via_oauth_api", new=AsyncMock(return_value=[oauth_item])),
            patch("scrapers.weibo._profile_exists", return_value=False),
            patch("scrapers.weibo._has_valid_cookie", return_value=False),
            patch("scrapers.weibo.async_playwright") as async_playwright_mock,
        ):
            items = await scraper.fetch(since_id=None)

        self.assertEqual([item.source_id for item in items], ["42"])
        async_playwright_mock.assert_not_called()

    async def test_full_sync_prefers_public_timeline_before_oauth_when_browser_login_state_is_missing(self):
        scraper = WeiboScraper(user_id=7, binding={"access_token": "token", "weibo_uid": "12345"})
        public_item = type("Item", (), {"item_time": 2, "source_id": "84"})()

        with (
            patch("scrapers.weibo._fetch_via_public_timeline", new=AsyncMock(return_value=[public_item])),
            patch("scrapers.weibo._fetch_via_oauth_api", new=AsyncMock(side_effect=AssertionError("oauth should not be used"))),
            patch("scrapers.weibo._profile_exists", return_value=False),
            patch("scrapers.weibo._has_valid_cookie", return_value=False),
            patch("scrapers.weibo.async_playwright") as async_playwright_mock,
        ):
            items = await scraper.fetch(since_id=None)

        self.assertEqual([item.source_id for item in items], ["84"])
        async_playwright_mock.assert_not_called()

    async def test_full_sync_prefers_browser_flow_when_browser_login_state_exists(self):
        scraper = WeiboScraper(user_id=7, binding={"access_token": "token", "weibo_uid": "12345"})

        with (
            patch("scrapers.weibo._fetch_via_oauth_api", new=AsyncMock(side_effect=AssertionError("oauth should not be used"))),
            patch("scrapers.weibo._profile_exists", return_value=True),
            patch("scrapers.weibo.async_playwright") as async_playwright_mock,
        ):
            async_playwright_mock.side_effect = RuntimeError("browser path reached")
            with self.assertRaises(RuntimeError) as context:
                await scraper.fetch(since_id=None)

        self.assertIn("browser path reached", str(context.exception))

    async def test_oauth_fetch_keeps_paging_with_page_until_no_more_statuses(self):
        pages = {
            1: [_build_status(5003), _build_status(5002)],
            2: [_build_status(5001), _build_status(5000)],
            3: [],
        }

        fake_client = _FakeAsyncClient(pages)
        with patch("scrapers.weibo.httpx.AsyncClient", return_value=fake_client):
            items = await _fetch_via_oauth_api("token", "12345", since_id=None)

        self.assertEqual([item.source_id for item in items], ["5003", "5002", "5001", "5000"])
        self.assertEqual(fake_client.calls[0].get("page"), "1")
        self.assertEqual(fake_client.calls[1].get("page"), "2")

    async def test_public_timeline_fetch_keeps_paging_using_since_id_cursor(self):
        pages = {
            None: {
                "data": {
                    "cards": [{"mblog": _build_status(7003)}, {"mblog": _build_status(7002)}],
                    "cardlistInfo": {"since_id": "cursor-2"},
                }
            },
            "cursor-2": {
                "data": {
                    "cards": [{"mblog": _build_status(7001)}, {"mblog": _build_status(7000)}],
                    "cardlistInfo": {"since_id": "cursor-3"},
                }
            },
            "cursor-3": {"data": {"cards": []}},
        }

        class _FakePublicAsyncClient(_FakeAsyncClient):
            async def get(self, url: str, params: dict | None = None):
                cursor = (params or {}).get("since_id")
                return _FakeResponse(self.pages.get(cursor, {"data": {"cards": []}}))

        with patch("scrapers.weibo.httpx.AsyncClient", return_value=_FakePublicAsyncClient(pages)):
            items = await _fetch_via_public_timeline_http("12345", since_id=None)

        self.assertEqual([item.source_id for item in items], ["7003", "7002", "7001", "7000"])

    async def test_public_timeline_falls_back_to_http_when_browser_fetch_fails(self):
        public_item = type("Item", (), {"item_time": 2, "source_id": "91"})()

        with (
            patch("scrapers.weibo._fetch_via_public_timeline_browser", new=AsyncMock(side_effect=RuntimeError("blocked"))),
            patch("scrapers.weibo._fetch_via_public_timeline_http", new=AsyncMock(return_value=[public_item])),
        ):
            items = await _fetch_via_public_timeline("12345", since_id=None)

        self.assertEqual([item.source_id for item in items], ["91"])

    def test_extract_media_supports_pic_urls_and_mix_media(self):
        status = {
            "pic_urls": [
                {"thumbnail_pic": "https://wx1.sinaimg.cn/thumbnail/a.jpg"},
                {"thumbnail_pic": "//wx2.sinaimg.cn/thumbnail/b.jpg"},
            ],
            "mix_media_info": {
                "items": [
                    {"type": "pic", "data": {"largest": {"url": "https://wx3.sinaimg.cn/large/c.jpg"}}},
                    {"type": "video", "data": {"page_pic": {"url": "https://wx4.sinaimg.cn/large/d.jpg"}}},
                ]
            },
        }

        self.assertEqual(
            _extract_media(status),
            [
                "https://wx1.sinaimg.cn/large/a.jpg",
                "https://wx2.sinaimg.cn/large/b.jpg",
                "https://wx3.sinaimg.cn/large/c.jpg",
                "https://wx4.sinaimg.cn/large/d.jpg",
            ],
        )

    def test_merge_item_with_existing_preserves_existing_media_when_new_payload_has_none(self):
        merged = _merge_item_with_existing(
            {
                "source": "weibo",
                "source_id": "1001",
                "content_type": "text",
                "title": None,
                "body": "新正文",
                "body_format": "plain",
                "media": None,
                "source_url": None,
            },
            {
                "source_url": "https://weibo.com/123/abc",
                "content_type": "image",
                "title": "旧标题",
                "body": "旧正文",
                "body_format": "plain",
                "media": '["https://wx1.sinaimg.cn/large/a.jpg"]',
            },
        )

        self.assertEqual(merged["media"], ["https://wx1.sinaimg.cn/large/a.jpg"])
        self.assertEqual(merged["content_type"], "image")
        self.assertEqual(merged["source_url"], "https://weibo.com/123/abc")


if __name__ == "__main__":
    unittest.main()
