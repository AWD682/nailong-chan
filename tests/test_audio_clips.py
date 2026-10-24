from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import bot  # noqa: F401 - 先初始化 NoneBot
import nailong_ai
from audio_clips import laugh_request_clip
from nonebot.adapters.qq.event import GroupAtMessageCreateEvent


def at_message(text: str) -> GroupAtMessageCreateEvent:
    return GroupAtMessageCreateEvent(
        id="laugh-test", content=text, timestamp="2026-10-18T12:00:00+08:00",
        group_id="g", group_openid="group-1",
        author={"id": "u", "bot": False,
                "member_openid": "owner-1", "member_role": "member"},
    )


class LaughRequestTests(unittest.TestCase):
    def test_detects_explicit_requests(self):
        for text in ("来一段奶龙大笑", "放个氦气大笑听听喵", "想听奶龙大笑",
                     "奶龙酱给我来个大大的笑声", "能不能放一下大笑"):
            self.assertEqual(laugh_request_clip(text), "helium", text)

    def test_ignores_unrelated_or_negated(self):
        for text in ("", "别笑了，正经点喵", "今天笑死我了", "早上好",
                     "你为什么叫奶龙酱", "哈哈哈真好笑"):
            self.assertIsNone(laugh_request_clip(text), text)


class LaughReplyTests(unittest.IsolatedAsyncioTestCase):
    async def test_handler_sends_local_audio_without_model(self):
        event = at_message("@奶龙酱 来一段奶龙大笑")
        qq_bot = SimpleNamespace(send=AsyncMock())
        with patch.object(nailong_ai.config, "ai_api_key", ""), \
             patch.object(nailong_ai.config, "ai_model", ""), \
             patch.object(nailong_ai.audio_clips, "load_clip",
                          return_value=b"m4a-bytes"):
            await nailong_ai.handle_chat(qq_bot, event)
        # 先发一句文字预告，再发本地音频转成的语音。
        self.assertEqual(qq_bot.send.await_count, 2)
        segment = qq_bot.send.await_args.args[1]
        self.assertEqual(getattr(segment, "type", ""), "file_audio")
        self.assertEqual(segment.data["content"], b"m4a-bytes")

    async def test_handler_reports_missing_clip(self):
        event = at_message("放个奶龙大笑")
        qq_bot = SimpleNamespace(send=AsyncMock())
        with patch.object(nailong_ai.config, "ai_api_key", ""), \
             patch.object(nailong_ai.config, "ai_model", ""), \
             patch.object(nailong_ai.audio_clips, "load_clip", return_value=None):
            await nailong_ai.handle_chat(qq_bot, event)
        self.assertEqual(qq_bot.send.await_count, 2)
        self.assertEqual(qq_bot.send.await_args.args[1],
                         "音频文件突然找不到了喵，稍后再试试。")

    async def test_handler_ignores_unrelated_messages(self):
        event = at_message("早上好喵")
        qq_bot = SimpleNamespace(send=AsyncMock(), put_interaction=AsyncMock())
        with patch.object(nailong_ai.config, "ai_api_key", ""), \
             patch.object(nailong_ai.config, "ai_model", ""), \
             patch.object(nailong_ai, "finish_reply", AsyncMock()) as finish:
            await nailong_ai.handle_chat(qq_bot, event)
        qq_bot.send.assert_not_awaited()
        finish.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
