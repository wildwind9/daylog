"""Regression tests for the 2026-09-29 QR login bug: final login hop got 432 and only X-CSRF-TOKEN was saved."""
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from scrapers import weibo
from scrapers.weibo import WeiboQrLoginSession, _has_valid_cookie, get_weibo_qr_login_status


def _response(payload: dict | None = None, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload or {}
    resp.raise_for_status.return_value = None
    return resp


class _FakeCookies(dict):
    def keys(self):
        return list(super().keys())


def _session(client) -> WeiboQrLoginSession:
    return WeiboQrLoginSession(
        user_id=1,
        session_id="weibo-qr-1-test",
        client=client,
        login_signin_url="https://passport.weibo.com/sso/signin?entry=miniblog",
        qrid="qrid",
        image_base64="",
    )


class HasValidCookieTest(unittest.TestCase):
    def test_csrf_only_cookie_is_not_a_login_state(self):
        self.assertFalse(_has_valid_cookie("X-CSRF-TOKEN=abc"))

    def test_cookie_with_sub_is_a_login_state(self):
        self.assertTrue(_has_valid_cookie("SUB=_2A25abc; SUBP=0033; X-CSRF-TOKEN=abc"))

    def test_placeholder_and_empty_are_invalid(self):
        self.assertFalse(_has_valid_cookie(""))
        self.assertFalse(_has_valid_cookie("your-weibo-cookie-here"))


class QrLoginFinalHopTest(unittest.IsolatedAsyncioTestCase):
    def tearDown(self):
        weibo._qr_sessions.clear()

    async def test_final_login_request_sends_browser_headers(self):
        cookies = _FakeCookies({"X-CSRF-TOKEN": "t"})
        client = MagicMock()
        client.cookies = cookies

        def fake_get(url, params=None, headers=None, **kwargs):
            if "qrcode/check" in url:
                return _response({"retcode": 20000000, "data": {"url": "https://passport.weibo.com/sso/v2/login?x=1"}})
            # Weibo rejects the final hop with 432 unless it looks like a browser navigation.
            if not (headers or {}).get("user-agent"):
                return _response(status_code=432)
            cookies["SUB"] = "sub"
            cookies["SUBP"] = "subp"
            return _response()

        client.get.side_effect = fake_get
        session = _session(client)
        weibo._qr_sessions[session.session_id] = session

        with (
            patch("scrapers.weibo._persist_weibo_cookie") as persist,
            patch("scrapers.weibo._resolve_uid_from_login_state", new=AsyncMock(return_value="123")),
        ):
            result = await get_weibo_qr_login_status(1, session.session_id)

        self.assertEqual(result["status"], "completed")
        saved = persist.call_args.args[0]
        self.assertIn("SUB=sub", saved)

    async def test_missing_sub_cookie_is_reported_as_failure_and_not_persisted(self):
        client = MagicMock()
        client.cookies = _FakeCookies({"X-CSRF-TOKEN": "t"})
        client.get.side_effect = lambda url, **kw: (
            _response({"retcode": 20000000, "data": {"url": "https://passport.weibo.com/sso/v2/login?x=1"}})
            if "qrcode/check" in url
            else _response(status_code=432)
        )
        session = _session(client)
        weibo._qr_sessions[session.session_id] = session

        with patch("scrapers.weibo._persist_weibo_cookie") as persist:
            result = await get_weibo_qr_login_status(1, session.session_id)

        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["cookieSaved"])
        persist.assert_not_called()


class FetchPrefersFreshCookieTest(unittest.IsolatedAsyncioTestCase):
    async def test_valid_cookie_is_used_instead_of_stale_profile(self):
        page = MagicMock()
        page.goto = AsyncMock()
        page.content = AsyncMock(return_value='{"uid":"123"}')
        context = MagicMock(pages=[])
        context.new_page = AsyncMock(return_value=page)
        context.add_cookies = AsyncMock()
        context.close = AsyncMock()
        browser = MagicMock()
        browser.new_context = AsyncMock(return_value=context)
        browser.close = AsyncMock()
        p = MagicMock()
        p.chromium.launch = AsyncMock(return_value=browser)
        p.chromium.launch_persistent_context = AsyncMock(side_effect=AssertionError("stale profile used"))
        pw = MagicMock()
        pw.__aenter__ = AsyncMock(return_value=p)
        pw.__aexit__ = AsyncMock(return_value=False)

        scraper = weibo.WeiboScraper(user_id=1, binding={})
        with (
            patch("scrapers.weibo.async_playwright", return_value=pw),
            patch("scrapers.weibo._resolve_uid_from_login_state", new=AsyncMock(return_value="123")),
            patch("scrapers.weibo._profile_exists", return_value=True),
            patch("scrapers.weibo._get_weibo_cookie", return_value="SUB=abc; SUBP=def"),
            patch("scrapers.weibo._collect_web_statuses", new=AsyncMock(return_value=[])),
        ):
            items = await scraper.fetch(since_id="100")

        self.assertEqual(items, [])
        context.add_cookies.assert_awaited()


class LoginStatusReadyTest(unittest.TestCase):
    def test_login_state_ready_follows_cookie(self):
        with patch.dict(os.environ, {"WEIBO_COOKIE_USER_7": "SUB=abc", "WEIBO_COOKIE": ""}, clear=False):
            self.assertTrue(weibo.get_weibo_login_status(7)["loginStateReady"])
        with patch.dict(os.environ, {"WEIBO_COOKIE_USER_7": "X-CSRF-TOKEN=abc", "WEIBO_COOKIE": ""}, clear=False):
            self.assertFalse(weibo.get_weibo_login_status(7)["loginStateReady"])


if __name__ == "__main__":
    unittest.main()
