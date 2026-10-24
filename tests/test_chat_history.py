from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from nonebot.adapters.qq.event import GroupAtMessageCreateEvent

import bot  # noqa: F401 - 初始化 NoneBot 后再导入插件
import chat_history
import nailong_ai


def fake_event(message_id: str, text: str, group: str = "group-a"):
    return SimpleNamespace(
        id=message_id, group_openid=group,
        author=SimpleNamespace(bot=False, username="小明"),
        get_plaintext=lambda: text,
    )


class ChatHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = TemporaryDirectory()
        self.db_patch = patch.object(
            chat_history, "DB_PATH", Path(self.folder.name) / "history.sqlite3"
        )
        self.db_patch.start()
        nailong_ai.history.clear()
        nailong_ai.group_context.clear()

    async def asyncTearDown(self):
        self.db_patch.stop()
        self.folder.cleanup()

    def test_records_once_separates_groups_and_expires_old_messages(self):
        start = 1_800_000_000.0
        self.assertTrue(chat_history.record_message(fake_event("one", "先讨论作业"), now=start))
        self.assertFalse(chat_history.record_message(fake_event("one", "重复事件"), now=start))
        self.assertTrue(chat_history.record_message(fake_event("two", "另一个群", "group-b"), now=start))
        with patch.object(chat_history.time, "time", return_value=start + 1):
            rows = chat_history.get_messages("group-a")
        self.assertEqual([row.content for row in rows], ["先讨论作业"])
        with patch.object(chat_history.time, "time", return_value=start + 1):
            self.assertEqual([row.content for row in chat_history.get_messages("group-b")],
                             ["另一个群"])
        with patch.object(chat_history.time, "time", return_value=start + 86401):
            self.assertEqual(chat_history.get_messages("group-a"), [])
        conn = chat_history._connect()
        try:
            count = conn.execute("SELECT COUNT(*) FROM group_messages").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 0)
        later = start + (chat_history.RETENTION_DAYS + 1) * 86400
        self.assertTrue(chat_history.record_message(fake_event("three", "新消息"), now=later))
        with patch.object(chat_history.time, "time", return_value=later + 1):
            self.assertEqual([row.content for row in chat_history.get_messages("group-a")],
                             ["新消息"])

    def test_summary_request_respects_china_calendar_and_message_limit(self):
        china = timezone(timedelta(hours=8))
        now = datetime(2026, 10, 17, 12, 0, tzinfo=china).timestamp()
        request = chat_history.parse_summary_request("整理一下昨天的群聊记录", now)
        self.assertEqual(request.since,
                         datetime(2026, 10, 16, tzinfo=china).timestamp())
        self.assertEqual(request.until,
                         datetime(2026, 10, 17, tzinfo=china).timestamp())
        self.assertEqual(chat_history.parse_summary_request(
            "总结最近300条聊天记录", now
        ).limit, chat_history.MAX_SUMMARY_MESSAGES)
        self.assertIsNone(chat_history.parse_summary_request("今天吃什么", now))

    async def test_group_summary_uses_saved_messages_instead_of_normal_chat(self):
        event = GroupAtMessageCreateEvent(
            id="request", content="整理今天的聊天记录",
            timestamp="2026-10-17T12:00:00+08:00",
            group_id="g", group_openid="group-a",
            author={"id": "u", "bot": False,
                    "member_openid": "member", "member_role": "member"},
        )
        qq_bot = SimpleNamespace(self_id="robot")
        rows = [chat_history.ChatLine("earlier", 1_800_000_000.0,
                                      "小明", "明天交作业")]
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(
                content="喵～小明说了明天交作业，大家可别忘啦！"))]
        )
        with patch.object(nailong_ai, "get_messages", return_value=rows) as read, \
             patch.object(nailong_ai, "AsyncOpenAI", return_value=client), \
             patch.object(nailong_ai, "finish_reply", AsyncMock()) as send, \
             patch.object(nailong_ai, "select_meme", AsyncMock()) as select:
            await nailong_ai.handle_chat(qq_bot, event)
        self.assertEqual(read.call_args.kwargs["exclude_id"], "request")
        self.assertEqual(send.await_args.args[2], "喵～小明说了明天交作业，大家可别忘啦！")
        prompt = client.chat.completions.create.await_args.kwargs["messages"][0]["content"]
        self.assertIn("像在群里给熟人讲", prompt)
        self.assertIn("不要写成会议纪要", prompt)
        select.assert_not_awaited()
