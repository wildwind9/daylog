import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scrapers.weibo import get_weibo_login_status


class WeiboLoginStatusTest(unittest.TestCase):
    def test_profile_files_without_cookie_are_not_treated_as_ready_login_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            profile_root = Path(temp_dir) / "profiles"
            user_dir = profile_root / "user-7"
            user_dir.mkdir(parents=True, exist_ok=True)
            (user_dir / "Default").mkdir()

            with patch.dict(
                os.environ,
                {
                    "WEIBO_PROFILE_DIR": str(profile_root),
                    "WEIBO_COOKIE_USER_7": "",
                    "WEIBO_COOKIE": "",
                },
                clear=False,
            ):
                status = get_weibo_login_status(7)

            self.assertTrue(status["profileExists"])
            self.assertFalse(status["cookieConfigured"])
            self.assertFalse(status["loginStateReady"])


if __name__ == "__main__":
    unittest.main()
