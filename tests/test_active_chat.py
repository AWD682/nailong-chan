import asyncio
from collections import deque
from contextlib import asynccontextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from nonebot.adapters.qq.event import GroupMessageCreateEvent
from nonebot.adapters.qq import Adapter as QQAdapter
from nonebot.drivers import Request, Timeout
from openai import APITimeoutError, BadRequestError
from httpx2 import Request as HTTPXRequest, Response as HTTPXResponse

import bot  # noqa: F401 - 初始化 NoneBot 后再导入插件
import active_chat
import nailong_ai
from qq_adapter import StableQQAdapter


def message(text: str, message_id: str, *, group: str = "test_group",
            user: str = "member", is_bot: bool = False):
    return SimpleNamespace(
        id=message_id,
        group_openid=group,
        mentions=None,
        reply=None,
        author=SimpleNamespace(
            bot=is_bot, username="群友", member_openid=user
        ),
        get_plaintext=lambda: text,
    )


class ActiveChatTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        active_chat.group_context.clear()
        active_chat.seen_ids.clear()
        active_chat.pending.clear()
        active_chat.pending_tasks.clear()
        active_chat.reply_times.clear()
        active_chat.group_locks.clear()
        nailong_ai.history.clear()
        self.allowed = patch.object(
            active_chat, "allowed_groups", frozenset({"test_group"})
        )
        self.debounce = patch.object(active_chat, "DEBOUNCE_SECONDS", 0.01)
        self.allowed.start()
        self.debounce.start()

    async def asyncTearDown(self):
        for task in active_chat.pending_tasks.values():
            task.cancel()
        if active_chat.pending_tasks:
            await asyncio.gather(*active_chat.pending_tasks.values(),
                                 return_exceptions=True)
        self.debounce.stop()
        self.allowed.stop()

    def test_parse_decision_only_accepts_valid_reply(self):
        self.assertEqual(active_chat.parse_active_decision(
            '{"action":"reply","reply":"  喵  "}'), "喵")
        for raw in ('{"action":"ignore","reply":"喵"}',
                    '{"action":"reply","reply":""}',
                    '```json\n{"action":"reply","reply":"喵"}\n```',
                    'not json'):
            self.assertIsNone(active_chat.parse_active_decision(raw))

    def test_group_rate_limit(self):
        self.assertTrue(active_chat.can_reply("g", 100))
        active_chat.reply_times["g"] = deque([100])
        self.assertFalse(active_chat.can_reply("g", 104))
        self.assertTrue(active_chat.can_reply("g", 105))
        active_chat.reply_times["g"] = deque(100 + i * 4 for i in range(120))
        self.assertFalse(active_chat.can_reply("g", 590))
        self.assertTrue(active_chat.can_reply("g", 701))

    def test_current_model_disables_thinking_by_default(self):
        self.assertEqual(nailong_ai.model_options(), {"reasoning_effort": "none"})

    def test_sticker_choice_rejects_unknown_file_or_id(self):
        self.assertEqual(
            nailong_ai.parse_sticker_reply(
                '{"reply":"来了喵","sticker":"../../secret.png"}'
            ),
            ("来了喵", "wave"),
        )
        self.assertEqual(nailong_ai.parse_sticker_reply("普通回复喵"),
                         ("普通回复喵", "wave"))

    async def test_qq_websocket_waits_longer_than_30_seconds(self):
        from nonebot import get_driver

        adapter = get_driver()._adapters["QQ"]
        self.assertIsInstance(adapter, StableQQAdapter)
        request = Request("GET", "wss://api.sgroup.qq.com/websocket", timeout=30.0)

        @asynccontextmanager
        async def fake_websocket(_adapter, setup):
            self.assertIs(setup, request)
            yield object()

        with patch.object(QQAdapter, "websocket", fake_websocket):
            async with adapter.websocket(request):
                self.assertIsInstance(request.timeout, Timeout)
                self.assertEqual(request.timeout.read, 120.0)

    def test_full_group_mentions_and_replies_route_to_direct_chat(self):
        payload = {
            "id": "m1", "content": "你好", "timestamp": "2026-09-25T10:00:00+08:00",
            "group_id": "g", "group_openid": "test_group",
            "author": {"id": "u", "bot": False,
                       "member_openid": "member", "member_role": "member"},
        }
        qq_bot = SimpleNamespace(self_id="robot")
        ordinary = GroupMessageCreateEvent(**payload)
        self.assertFalse(nailong_ai.is_direct_chat(ordinary, qq_bot))

        mention = GroupMessageCreateEvent(**{
            **payload, "mentions": [{"scope": "single", "bot": True,
                                       "id": "robot", "is_you": True,
                                       "member_openid": "robot_openid",
                                       "username": "奶龙酱"}]
        })
        self.assertTrue(nailong_ai.is_direct_chat(mention, qq_bot))

        reply = GroupMessageCreateEvent(**{
            **payload, "reply": {"content": "之前的回复", "message_type": 0,
                                   "msg_idx": "1", "author": {"id": "robot",
                                                               "bot": True}}
        })
        self.assertTrue(nailong_ai.is_direct_chat(reply, qq_bot))

    async def test_merges_burst_and_sends_once(self):
        qq_bot = SimpleNamespace(send=AsyncMock())
        decision = AsyncMock(return_value="主人先歇一下喵")
        with patch.object(active_chat, "decide_reply", decision):
            await active_chat.handle_group_message(
                qq_bot, message("今天好累", "m1"))
            await active_chat.handle_group_message(
                qq_bot, message("作业还没写完", "m2"))
            await asyncio.sleep(0.06)
        decision.assert_awaited_once()
        self.assertEqual(decision.await_args.args[0], "今天好累\n作业还没写完")
        qq_bot.send.assert_awaited_once()
        self.assertEqual(qq_bot.send.await_args.args[1], "主人先歇一下喵")
        self.assertEqual(len(active_chat.reply_times["test_group"]), 1)

    async def test_explicit_group_voice_request_sends_audio(self):
        qq_bot = SimpleNamespace(send=AsyncMock())
        decision = AsyncMock(return_value="奶龙酱来啦喵！")
        with patch.object(active_chat, "decide_reply", decision), \
             patch.object(active_chat, "send_voice_reply", AsyncMock()) as send_voice:
            await active_chat.handle_group_message(
                qq_bot, message("奶龙酱，给我发条语音", "voice1")
            )
            await asyncio.sleep(0.04)
        send_voice.assert_awaited_once()
        self.assertEqual(send_voice.await_args.kwargs["voice"], "longpaopao_v3.1")
        qq_bot.send.assert_not_awaited()

    async def test_explicit_group_song_request_uses_music(self):
        qq_bot = SimpleNamespace(send=AsyncMock())
        with patch.object(active_chat, "decide_reply", AsyncMock()) as decide, \
             patch.object(active_chat, "send_song_reply", AsyncMock()) as send_song:
            await active_chat.handle_group_message(
                qq_bot, message("奶龙酱，唱两句吧", "song1")
            )
            await asyncio.sleep(0.04)
        send_song.assert_awaited_once()
        decide.assert_not_awaited()
        self.assertIn("谱个小曲", qq_bot.send.await_args.args[1])

    async def test_skips_bots_other_groups_duplicates_and_cooldown(self):
        qq_bot = SimpleNamespace(send=AsyncMock())
        decision = AsyncMock(return_value="喵")
        with patch.object(active_chat, "decide_reply", decision):
            await active_chat.handle_group_message(
                qq_bot, message("你好", "m1", group="other"))
            await active_chat.handle_group_message(
                qq_bot, message("你好", "m2", is_bot=True))
            await active_chat.handle_group_message(
                qq_bot, message("帮帮我", "m3"))
            await active_chat.handle_group_message(
                qq_bot, message("帮帮我", "m3"))
            await asyncio.sleep(0.04)
            await active_chat.handle_group_message(
                qq_bot, message("另一个问题", "m4", user="member2"))
            await asyncio.sleep(0.04)
        self.assertEqual(decision.await_count, 1)
        self.assertEqual(qq_bot.send.await_count, 1)

    async def test_does_not_send_stale_reply_after_new_group_message(self):
        qq_bot = SimpleNamespace(send=AsyncMock())

        async def slow_decision(question, recent):
            active_chat.group_context["test_group"].append("群友：新话题")
            return "过时的回复"

        with patch.object(active_chat, "decide_reply", slow_decision):
            await active_chat.handle_group_message(
                qq_bot, message("原来的话题", "m1"))
            await asyncio.sleep(0.04)
        qq_bot.send.assert_not_awaited()

    async def test_meme_timeout_falls_back_to_normal_reply(self):
        from nonebot.adapters.qq.event import C2CMessageCreateEvent

        event = C2CMessageCreateEvent(
            id="private1", content="你好", timestamp="2026-09-25T10:00:00+08:00",
            author={"id": "u", "user_openid": "u"},
        )
        result = SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="你好喵"))])
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(
                create=AsyncMock(return_value=result))),
            close=AsyncMock(),
        )
        timeout = APITimeoutError(request=HTTPXRequest("POST", "https://example.com"))
        with patch.object(nailong_ai, "AsyncOpenAI", return_value=client), \
             patch.object(nailong_ai, "select_meme", AsyncMock(side_effect=timeout)), \
             patch.object(nailong_ai.chat, "finish", AsyncMock()) as finish:
            await nailong_ai.handle_chat(SimpleNamespace(send=AsyncMock()), event)
        finish.assert_awaited_once_with("你好喵")
        client.close.assert_awaited_once()

    async def test_content_rejection_clears_private_history(self):
        from nonebot.adapters.qq.event import C2CMessageCreateEvent

        event = C2CMessageCreateEvent(
            id="private2", content="普通新话题", timestamp="2026-09-25T10:00:00+08:00",
            author={"id": "u", "user_openid": "u"},
        )
        session = event.get_session_id()
        nailong_ai.history[session] = deque([
            {"role": "user", "content": "之前的话题"},
            {"role": "assistant", "content": "之前的回复"},
        ], maxlen=8)
        request = HTTPXRequest("POST", "https://example.com")
        rejection = BadRequestError(
            "Input text data may contain inappropriate content",
            response=HTTPXResponse(400, request=request),
            body={"code": "data_inspection_failed"},
        )
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(
                create=AsyncMock(side_effect=rejection))),
            close=AsyncMock(),
        )
        with patch.object(nailong_ai, "AsyncOpenAI", return_value=client), \
             patch.object(nailong_ai, "select_meme", AsyncMock(return_value=(None, {}, ""))), \
             patch.object(nailong_ai.chat, "finish", AsyncMock()) as finish:
            await nailong_ai.handle_chat(SimpleNamespace(send=AsyncMock()), event)
        self.assertNotIn(session, nailong_ai.history)
        finish.assert_awaited_once()
        self.assertIn("留点‘喵’头", finish.await_args.args[0])
        client.close.assert_awaited_once()

    async def test_group_at_sends_sticker_before_text(self):
        from nonebot.adapters.qq.event import GroupAtMessageCreateEvent

        event = GroupAtMessageCreateEvent(
            id="at1", content="你好", timestamp="2026-09-25T10:00:00+08:00",
            group_id="g", group_openid="test_group",
            author={"id": "u", "bot": False,
                    "member_openid": "member", "member_role": "member"},
        )
        result = SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content='{"reply":"吓我一跳喵","sticker":"surprised"}'))])
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(
                create=AsyncMock(return_value=result))),
            close=AsyncMock(),
        )
        order = []

        async def send_image(_, segment):
            order.append(("image", segment))

        async def finish_text(text):
            order.append(("text", text))

        qq_bot = SimpleNamespace(send=AsyncMock(side_effect=send_image))
        with patch.object(nailong_ai, "AsyncOpenAI", return_value=client), \
             patch.object(nailong_ai, "select_meme", AsyncMock(return_value=(None, {}, ""))), \
             patch.object(nailong_ai.chat, "finish", AsyncMock(side_effect=finish_text)):
            await nailong_ai.handle_chat(qq_bot, event)
        self.assertEqual([kind for kind, _ in order], ["image", "text"])
        self.assertEqual(order[0][1].type, "file_image")
        self.assertEqual(order[0][1].data["content"],
                         (nailong_ai.STICKER_DIR / "surprised.png").read_bytes())
        self.assertEqual(order[1][1], "吓我一跳喵")
        self.assertEqual(nailong_ai.history[event.get_session_id()][-1]["content"],
                         "吓我一跳喵")
        prompt = client.chat.completions.create.await_args.kwargs["messages"][1]["content"]
        self.assertIn('"sticker":"表情编号"', prompt)
        self.assertIn("surprised", prompt)
        client.close.assert_awaited_once()

    async def test_group_at_still_sends_text_if_sticker_upload_fails(self):
        from nonebot.adapters.qq.event import GroupAtMessageCreateEvent

        event = GroupAtMessageCreateEvent(
            id="at2", content="你好", timestamp="2026-09-25T10:00:00+08:00",
            group_id="g", group_openid="test_group",
            author={"id": "u", "bot": False,
                    "member_openid": "member", "member_role": "member"},
        )
        qq_bot = SimpleNamespace(send=AsyncMock(side_effect=RuntimeError("upload failed")))
        with patch.object(nailong_ai.chat, "finish", AsyncMock()) as finish:
            await nailong_ai.finish_reply(qq_bot, event, "文字继续喵")
        qq_bot.send.assert_awaited_once()
        finish.assert_awaited_once_with("文字继续喵")

    async def test_content_rejection_skips_active_group_reply(self):
        event = message("普通群消息", "blocked1")
        key = ("test_group", "member")
        active_chat.pending[key] = ["普通群消息"]
        active_chat.group_context["test_group"] = deque(["群友：之前的话题"])
        request = HTTPXRequest("POST", "https://example.com")
        rejection = BadRequestError(
            "Input text data may contain inappropriate content",
            response=HTTPXResponse(400, request=request),
            body={"code": "data_inspection_failed"},
        )
        qq_bot = SimpleNamespace(send=AsyncMock())
        with patch.object(active_chat, "decide_reply", AsyncMock(side_effect=rejection)):
            await active_chat.process_pending(qq_bot, event, key)
        qq_bot.send.assert_not_awaited()
        self.assertNotIn("test_group", active_chat.group_context)


if __name__ == "__main__":
    unittest.main()
