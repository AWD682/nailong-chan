"""保存机器人实际收到的群文字消息，供回看和整理使用。"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sqlite3
import time

from nonebot import logger, on_message
from nonebot.adapters.qq.event import GroupMessageCreateEvent
from nonebot.rule import is_type


DB_PATH = Path(__file__).parent / "data" / "chat_history.sqlite3"
RETENTION_DAYS = 1
MAX_TEXT_LENGTH = 1200
MAX_SUMMARY_MESSAGES = 120
CHINA_TIME = timezone(timedelta(hours=8))


@dataclass(frozen=True)
class ChatLine:
    message_id: str
    received_at: float
    author_name: str
    content: str


@dataclass(frozen=True)
class SummaryRequest:
    label: str
    since: float
    until: float
    limit: int = MAX_SUMMARY_MESSAGES


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.execute("""CREATE TABLE IF NOT EXISTS group_messages (
        group_openid TEXT NOT NULL,
        message_id TEXT NOT NULL,
        received_at REAL NOT NULL,
        author_name TEXT NOT NULL,
        content TEXT NOT NULL,
        PRIMARY KEY (group_openid, message_id)
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS group_messages_time
        ON group_messages (group_openid, received_at)""")
    return conn


def record_message(event: GroupMessageCreateEvent, now: float | None = None) -> bool:
    """同一条 QQ 消息只记录一次；只保存文字，不保存图片或附件。"""
    if event.author.bot:
        return False
    content = event.get_plaintext().strip()[:MAX_TEXT_LENGTH]
    if not content:
        return False
    received_at = time.time() if now is None else now
    name = (event.author.username or "群友").replace("\n", " ")[:30]
    conn = _connect()
    try:
        with conn:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO group_messages
                (group_openid, message_id, received_at, author_name, content)
                VALUES (?, ?, ?, ?, ?)""",
                (event.group_openid, event.id, received_at, name, content),
            )
            conn.execute(
                "DELETE FROM group_messages WHERE received_at < ?",
                (received_at - RETENTION_DAYS * 86400,),
            )
            return cursor.rowcount == 1
    finally:
        conn.close()


def get_messages(group_openid: str, *, since: float | None = None,
                 until: float | None = None, limit: int = MAX_SUMMARY_MESSAGES,
                 exclude_id: str | None = None) -> list[ChatLine]:
    now = time.time()
    since = max(now - RETENTION_DAYS * 86400, since or 0)
    until = now if until is None else until
    limit = max(1, min(limit, MAX_SUMMARY_MESSAGES))
    conn = _connect()
    try:
        with conn:
            conn.execute(
                "DELETE FROM group_messages WHERE received_at < ?",
                (now - RETENTION_DAYS * 86400,),
            )
        rows = conn.execute(
            """SELECT message_id, received_at, author_name, content
            FROM group_messages
            WHERE group_openid = ? AND received_at >= ? AND received_at < ?
              AND message_id != ?
            ORDER BY received_at DESC, message_id DESC LIMIT ?""",
            (group_openid, since, until, exclude_id or "", limit),
        ).fetchall()
    finally:
        conn.close()
    return [ChatLine(*row) for row in reversed(rows)]


def parse_summary_request(question: str, now: float | None = None
                          ) -> SummaryRequest | None:
    """识别常见的群聊整理请求与时间范围。"""
    if not re.search(r"聊天记录|聊天内容|群聊|群里.*聊|大家.*聊", question):
        return None
    if not re.search(r"整理|总结|概括|梳理|回顾|说了什么|聊了什么|聊了啥", question):
        return None

    current = time.time() if now is None else now
    local = datetime.fromtimestamp(current, CHINA_TIME)
    today = local.replace(hour=0, minute=0, second=0, microsecond=0)
    until = current + 1
    limit = MAX_SUMMARY_MESSAGES

    if "前天" in question:
        return SummaryRequest("前天", (today - timedelta(days=2)).timestamp(),
                              (today - timedelta(days=1)).timestamp())
    if "昨天" in question:
        return SummaryRequest("昨天", (today - timedelta(days=1)).timestamp(),
                              today.timestamp())
    if "今天" in question:
        return SummaryRequest("今天", today.timestamp(), until)

    count_match = re.search(r"最近\s*(\d{1,3})\s*条", question)
    if count_match:
        limit = min(int(count_match.group(1)), MAX_SUMMARY_MESSAGES)
        return SummaryRequest(f"最近 {limit} 条", current - RETENTION_DAYS * 86400,
                              until, limit)

    time_match = re.search(r"(?:最近|近)\s*(\d{1,3})\s*(小时|天)", question)
    if time_match:
        amount = int(time_match.group(1))
        seconds = amount * (3600 if time_match.group(2) == "小时" else 86400)
        seconds = min(seconds, RETENTION_DAYS * 86400)
        return SummaryRequest(f"最近 {amount} {time_match.group(2)}",
                              current - seconds, until)
    if "一周" in question or "7天" in question:
        return SummaryRequest("最近一周", current - 7 * 86400, until)
    return SummaryRequest("最近 24 小时", current - 86400, until)


def format_messages(messages: list[ChatLine], max_chars: int = 300) -> str:
    return "\n".join(
        f"{datetime.fromtimestamp(item.received_at, CHINA_TIME):%m-%d %H:%M} "
        f"{item.author_name}：{item.content.replace(chr(10), ' ')[:max_chars]}"
        for item in messages
    )


recorder = on_message(rule=is_type(GroupMessageCreateEvent), priority=1, block=False)


@recorder.handle()
async def record_group_message(event: GroupMessageCreateEvent) -> None:
    try:
        record_message(event)
    except (sqlite3.Error, OSError):
        logger.exception("保存群聊天记录失败；本条消息将无法用于后续整理")
