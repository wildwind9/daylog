"""Regression tests for the 2026-09-21 hang: scrape must never block forever."""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import main
from scrapers import weibo
from scrapers.weibo import WeiboScraper, _collect_web_statuses, _fetch_long_text, _fetch_status_page


class _HangingPage:
    """Simulates a page whose renderer died: evaluate() never resolves."""

    async def evaluate(self, *args, **kwargs):
        await asyncio.Event().wait()


def _status(status_id: int) -> dict:
    return {"id": status_id}


class EvaluateTimeoutTest(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_status_page_returns_none_when_evaluate_hangs(self):
        with patch.object(weibo, "EVALUATE_TIMEOUT_SECONDS", 0.05):
            result = await asyncio.wait_for(_fetch_status_page(_HangingPage(), "1", 1), timeout=2)
        self.assertIsNone(result)

    async def test_fetch_long_text_returns_none_when_evaluate_hangs(self):
        with patch.object(weibo, "EVALUATE_TIMEOUT_SECONDS", 0.05):
            result = await asyncio.wait_for(_fetch_long_text(_HangingPage(), "1"), timeout=2)
        self.assertIsNone(result)


class WebPaginationGuardTest(unittest.IsolatedAsyncioTestCase):
    async def test_stops_when_page_returns_only_already_seen_statuses(self):
        same_page = {"data": {"list": [_status(3), _status(2)]}}
        fetch_mock = AsyncMock(return_value=same_page)

        with patch("scrapers.weibo._fetch_status_page", new=fetch_mock):
            statuses = await _collect_web_statuses(object(), "1", since_int=None)

        self.assertEqual([s["id"] for s in statuses], [3, 2])
        self.assertEqual(fetch_mock.await_count, 2)

    async def test_stops_at_max_pages(self):
        counter = iter(range(10_000, 0, -1))

        async def fresh_page(page, uid, page_number):
            return {"data": {"list": [_status(next(counter))]}}

        with (
            patch("scrapers.weibo._fetch_status_page", new=fresh_page),
            patch.object(weibo, "MAX_STATUS_PAGES", 5),
        ):
            statuses = await _collect_web_statuses(object(), "1", since_int=None)

        self.assertEqual(len(statuses), 5)

    async def test_stops_when_reaching_since_id(self):
        pages = {
            1: {"data": {"list": [_status(12), _status(11)]}},
            2: {"data": {"list": [_status(10), _status(9)]}},
        }

        async def paged(page, uid, page_number):
            return pages.get(page_number)

        with patch("scrapers.weibo._fetch_status_page", new=paged):
            statuses = await _collect_web_statuses(object(), "1", since_int=10)

        self.assertEqual([s["id"] for s in statuses], [12, 11])


class ScrapeTotalTimeoutTest(unittest.IsolatedAsyncioTestCase):
    async def test_scrape_returns_failed_when_fetch_exceeds_timeout(self):
        async def hang(self, since_id=None):
            await asyncio.Event().wait()

        with (
            patch.object(main, "SCRAPE_TIMEOUT_SECONDS", 0.05),
            patch.object(main, "get_weibo_binding_auth", return_value={}),
            patch.object(main, "get_latest_source_id", return_value="100"),
            patch.object(WeiboScraper, "fetch", new=hang),
        ):
            result = await asyncio.wait_for(
                main.scrape("weibo", userId=1, full=False, bindingId=3), timeout=2
            )

        self.assertEqual(result.status, "failed")
        self.assertIn("超时", result.error)


if __name__ == "__main__":
    unittest.main()
