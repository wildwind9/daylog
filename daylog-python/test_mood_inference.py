import unittest

from analyzers.llm import infer_mood_from_tags


class MoodInferenceTest(unittest.TestCase):
    def test_maps_positive_tags_to_blue_mood(self):
        self.assertEqual(infer_mood_from_tags(["工作", "开心"]), "😍")
        self.assertEqual(infer_mood_from_tags(["惊喜", "美食"]), "🤩")

    def test_maps_calm_tired_and_negative_tags_to_existing_moods(self):
        self.assertEqual(infer_mood_from_tags(["运动", "平静"]), "😊")
        self.assertEqual(infer_mood_from_tags(["疲惫", "加班"]), "😌")
        self.assertEqual(infer_mood_from_tags(["焦虑", "工作"]), "😢")

    def test_returns_none_without_emotion_tags(self):
        self.assertIsNone(infer_mood_from_tags(["工作", "美食"]))


if __name__ == "__main__":
    unittest.main()
