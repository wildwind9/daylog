import unittest
from unittest.mock import AsyncMock, patch

from analyzers.llm import infer_mood_from_tags
from main import _analyze_new_items


class WeiboMoodSyncTest(unittest.IsolatedAsyncioTestCase):
    async def test_weibo_sync_updates_mood_once_per_day_from_aggregated_tags(self):
        pending_rows = [
            {"id": 101, "body": "第一条微博", "item_date": "2026-04-12"},
            {"id": 102, "body": "第二条微博", "item_date": "2026-04-12"},
            {"id": 103, "body": "第三条微博", "item_date": "2026-04-13"},
        ]

        with (
            patch("main.get_items_without_tags", side_effect=[pending_rows, []]),
            patch("main.extract_tags", new=AsyncMock(side_effect=[
                ["工作", "疲惫"],
                ["朋友", "开心"],
                ["美食"],
            ])),
            patch("main.save_tags") as save_tags,
            patch("main.update_mood_for_item_date") as update_mood,
        ):
            analyzed = await _analyze_new_items("weibo", user_id=7, limit=50, all_batches=False)

        self.assertEqual(analyzed, 3)
        self.assertEqual(save_tags.call_count, 3)
        update_mood.assert_called_once_with(101, infer_mood_from_tags(["工作", "疲惫", "朋友", "开心"]))

    async def test_non_weibo_sources_keep_item_level_mood_updates(self):
        pending_rows = [
            {"id": 201, "body": "手写日记", "item_date": "2026-04-12"},
        ]

        with (
            patch("main.get_items_without_tags", side_effect=[pending_rows, []]),
            patch("main.extract_tags", new=AsyncMock(return_value=["工作", "疲惫"])),
            patch("main.save_tags"),
            patch("main.update_mood_for_item_date") as update_mood,
        ):
            analyzed = await _analyze_new_items("manual", user_id=7, limit=50, all_batches=False)

        self.assertEqual(analyzed, 1)
        update_mood.assert_called_once_with(201, infer_mood_from_tags(["工作", "疲惫"]))


if __name__ == "__main__":
    unittest.main()
