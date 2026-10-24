import unittest
from unittest.mock import AsyncMock, patch

import quiz_api


class QuizApiTests(unittest.IsolatedAsyncioTestCase):
    def test_parse_accepts_valid_wrapped_batch(self):
        raw = ('```json\n{"questions":['
               '{"question":"章鱼有三颗心。","answer":true,"explanation":"两颗负责送鳃。"},'
               '{"question":"企鹅是不会飞的鸟类。","answer":false,"explanation":"企鹅只能游泳。"}'
               "]}\n```")
        self.assertEqual(quiz_api.parse_quiz_batch(raw), [
            ("章鱼有三颗心。", True, "两颗负责送鳃。"),
            ("企鹅是不会飞的鸟类。", False, "企鹅只能游泳。"),
        ])

    def test_parse_rejects_bad_items_and_repeats(self):
        raw = ('{"questions":['
               '{"question":"太短","answer":true,"explanation":"解释足够长。"},'
               '{"question":"答案不是布尔。","answer":"true","explanation":"解释足够长。"},'
               '{"question":"这是一条疑问句吗？","answer":true,"explanation":"解释足够长。"},'
               '{"question":"解释太长的题目。","answer":true,'
               '"explanation":"' + "长" * 200 + '"},'
               '{"question":"章鱼有三颗心。","answer":true,"explanation":"解释第一次。"},'
               '{"question":"章鱼有三颗心。","answer":false,"explanation":"解释重复了。"}'
               "]}")
        self.assertEqual(quiz_api.parse_quiz_batch(raw),
                         [("章鱼有三颗心。", True, "解释第一次。")])

    def test_parse_ignores_recent_questions_and_garbage(self):
        self.assertEqual(
            quiz_api.parse_quiz_batch("不是 JSON", []), [])
        self.assertEqual(quiz_api.parse_quiz_batch(
            '{"questions":[{"question":"章鱼有三颗心。","answer":true,'
            '"explanation":"两颗负责送鳃。"}]}',
            ["章鱼有三颗心。"]), [])

    async def test_generate_returns_empty_without_config(self):
        with patch.object(quiz_api, "gen_config",
                          return_value=quiz_api.QuizGenConfig()):
            self.assertEqual(await quiz_api.generate_quiz_batch(5), [])

    async def test_generate_returns_empty_on_api_error(self):
        config = quiz_api.QuizGenConfig(
            quiz_api_key="k", quiz_api_base_url="https://example.com")
        with patch.object(quiz_api, "gen_config", return_value=config), \
             patch.object(quiz_api, "AsyncOpenAI", side_effect=RuntimeError("boom")):
            self.assertEqual(await quiz_api.generate_quiz_batch(5, ("games",)), [])


if __name__ == "__main__":
    unittest.main()
