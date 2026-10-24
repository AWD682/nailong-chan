"""游戏音效：通过 QQ 语音或 H5 网页播放 audio 文件夹里的片段。

QQ 按钮局通过语音消息发进群；H5 网页局由前端从 /audio/ 路由取音频播放。
"""

from pathlib import Path
import re

from aiohttp import web
from nonebot import logger
from nonebot.adapters.qq import Bot, MessageSegment
from nonebot.adapters.qq.event import (
    GroupMessageCreateEvent,
    InteractionCreateEvent,
)


ROOT = Path(__file__).parent
CLIP_DIR = ROOT / "audio"

# 对外只用 ASCII 名字（helium），实际指向 audio 文件夹里的中文文件。
CLIPS: dict[str, str] = {
    "helium": "氦气大笑.m4a",
    "hurt": "嘎嘎滴辣虾.m4a",
    "jump": "安迪.m4a",
    "heal": "猴辣，干巴爹.m4a",
}

# 群友点名要听奶龙大笑；泛指「大笑」「笑声」时要搭配明确的请求词才触发。
_LAUGH_NEGATION_RE = re.compile(r"(?:别|不要|不用|禁止|停止).{0,6}笑")
_LAUGH_NAMED_RE = re.compile(r"奶龙大笑|氦气大笑")
_LAUGH_GENERIC_RE = re.compile(r"大笑|笑声|笑一[个下]")
_LAUGH_ASK_RE = re.compile(r"放|播放|来|发|听|整|要|给我|有没有|能不能|可以")


def laugh_request_clip(question: str) -> str | None:
    """只认 @ 奶龙酱后明确要求听奶龙大笑（氦气大笑音频）的消息。"""
    text = question.strip()
    if not text or _LAUGH_NEGATION_RE.search(text):
        return None
    if _LAUGH_NAMED_RE.search(text):
        return "helium"
    if _LAUGH_GENERIC_RE.search(text) and _LAUGH_ASK_RE.search(text):
        return "helium"
    return None


def clip_path(name: str) -> Path | None:
    filename = CLIPS.get(name)
    if filename is None:
        return None
    path = CLIP_DIR / filename
    return path if path.is_file() else None


def load_clip(name: str) -> bytes | None:
    path = clip_path(name)
    return path.read_bytes() if path is not None else None


async def send_clip(bot: Bot,
                    event: GroupMessageCreateEvent | InteractionCreateEvent,
                    name: str) -> None:
    """把音效当语音发进群；失败只记日志，不影响游戏流程。"""
    audio = load_clip(name)
    if audio is None:
        logger.warning("游戏音效 {} 没找到，跳过播放", name)
        return
    try:
        await bot.send(event, MessageSegment.file_audio(
            audio, file_name=f"nailong-{name}.mp3"))
    except Exception:
        logger.exception("奶龙酱播放游戏音效 {} 失败", name)


async def clip_file(request: web.Request) -> web.FileResponse:
    path = clip_path(request.match_info["name"])
    if path is None:
        raise web.HTTPNotFound()
    return web.FileResponse(path,
                            headers={"Cache-Control": "public, max-age=86400"})


def add_routes(app: web.Application) -> None:
    """由 h5_quiz.make_app 调用，给网页小游戏提供音效文件。"""
    app.router.add_get("/audio/{name}.m4a", clip_file)
