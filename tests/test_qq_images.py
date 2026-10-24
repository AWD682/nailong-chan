import base64
from io import BytesIO
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from nonebot.adapters.qq.event import C2CMessageCreateEvent, GroupAtMessageCreateEvent, GroupMessageCreateEvent
from PIL import Image

import bot  # noqa: F401 - 先初始化 NoneBot
import nailong_ai
import qq_images
from qq_images import ImageLoadError, _image_mime, _safe_image_url, image_attachments


IMAGE = {"content_type": "image/png", "url": "https://gchat.qpic.cn/test.png"}


def private_image(text: str = ""):
    return C2CMessageCreateEvent(
        id="private-image", content=text, timestamp="2026-10-17T19:00:00+08:00",
        author={"id": "u", "user_openid": "u"}, attachments=[IMAGE],
    )


class QQImageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        nailong_ai.history.clear()
        nailong_ai.group_context.clear()

    def test_only_image_attachments_and_safe_urls_are_accepted(self):
        event = SimpleNamespace(attachments=[
            SimpleNamespace(content_type="image/png", url="https://gchat.qpic.cn/a"),
            SimpleNamespace(content_type="video/mp4", url="https://gchat.qpic.cn/b"),
        ])
        self.assertEqual(len(image_attachments(event)), 1)
        quoted = SimpleNamespace(
            attachments=None,
            reply=SimpleNamespace(attachments=[SimpleNamespace(
                content_type="image/jpeg", url="https://gchat.qpic.cn/quoted"
            )]),
        )
        self.assertEqual(len(image_attachments(quoted)), 1)
        self.assertTrue(_safe_image_url("https://gchat.qpic.cn/a"))
        self.assertTrue(_safe_image_url("http://gchat.qpic.cn/a"))
        for url in ("http://untrusted.example/a", "https://127.0.0.1/a",
                    "https://localhost/a", "https://user@host.example/a"):
            self.assertFalse(_safe_image_url(url))
        self.assertEqual(_image_mime(b"\x89PNG\r\n\x1a\nmore"), "image/png")
        self.assertIsNone(_image_mime(b"not an image"))

    async def test_private_image_only_reaches_vision_model(self):
        event = private_image()
        result = SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="我看到一只猫喵"))])
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(
                create=AsyncMock(return_value=result))),
            close=AsyncMock(),
        )
        data_url = "data:image/png;base64,aGVsbG8="
        prepared = qq_images.PreparedImage((data_url,), (1,), 1)
        with patch.object(nailong_ai, "load_image_inputs", AsyncMock(return_value=[prepared])), \
             patch.object(nailong_ai, "AsyncOpenAI", return_value=client), \
             patch.object(nailong_ai, "select_meme", AsyncMock()) as select, \
             patch.object(nailong_ai.chat, "finish", AsyncMock()) as finish:
            await nailong_ai.handle_chat(SimpleNamespace(send=AsyncMock()), event)
        content = client.chat.completions.create.await_args.kwargs["messages"][-1]["content"]
        self.assertEqual(content[0]["type"], "text")
        self.assertEqual(content[1], {"type": "image_url", "image_url": {"url": data_url}})
        finish.assert_awaited_once_with("我看到一只猫喵")
        select.assert_not_awaited()
        self.assertNotIn("base64", str(nailong_ai.history[event.get_session_id()]))

    async def test_downloaded_image_is_checked_and_encoded_without_saving(self):
        png = b"\x89PNG\r\n\x1a\n" + b"example"

        class Body:
            async def iter_chunked(self, _):
                yield png

        class Response:
            status = 200
            content_length = len(png)
            content = Body()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

        class Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                pass

            def get(self, url, *, allow_redirects):
                self_url = "https://gchat.qpic.cn/test.png"
                assert url == self_url and not allow_redirects
                return Response()

        with patch.object(qq_images.aiohttp, "ClientSession", return_value=Session()):
            pictures = await qq_images.load_image_inputs(private_image())
        self.assertEqual(pictures[0].frames[0], "data:image/png;base64,iVBORw0KGgpleGFtcGxl")

    def test_animated_gif_produces_ordered_distinct_frames(self):
        frames = [Image.new("RGB", (80, 80), (index * 25, 0, 0)) for index in range(9)]
        output = BytesIO()
        frames[0].save(output, format="GIF", save_all=True,
                       append_images=frames[1:], duration=80, loop=0)
        prepared = qq_images._prepare_image(output.getvalue(), "image/gif")
        self.assertTrue(prepared.animated)
        self.assertEqual(prepared.total_frames, 9)
        self.assertEqual(len(prepared.frames), qq_images.MAX_GIF_FRAMES)
        self.assertEqual(prepared.frame_numbers[0], 1)
        self.assertEqual(prepared.frame_numbers[-1], 9)
        first = Image.open(BytesIO(base64.b64decode(prepared.frames[0].split(",", 1)[1])))
        last = Image.open(BytesIO(base64.b64decode(prepared.frames[-1].split(",", 1)[1])))
        self.assertLess(first.getpixel((0, 0))[0], last.getpixel((0, 0))[0])

    async def test_gif_frames_are_labeled_in_model_input(self):
        event = private_image("这动图在做什么？")
        prepared = qq_images.PreparedImage(
            ("data:image/jpeg;base64,aaa", "data:image/jpeg;base64,bbb"),
            (1, 9), 9,
        )
        result = SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="角色先站着，然后跳了起来喵"))])
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(
                create=AsyncMock(return_value=result))),
            close=AsyncMock(),
        )
        with patch.object(nailong_ai, "load_image_inputs", AsyncMock(return_value=[prepared])), \
             patch.object(nailong_ai, "AsyncOpenAI", return_value=client), \
             patch.object(nailong_ai.chat, "finish", AsyncMock()):
            await nailong_ai.handle_chat(SimpleNamespace(send=AsyncMock()), event)
        request = client.chat.completions.create.await_args.kwargs["messages"]
        content = request[-1]["content"]
        self.assertIn("动作和变化", request[1]["content"])
        self.assertEqual([item["type"] for item in content],
                         ["text", "text", "text", "image_url", "text", "image_url"])
        self.assertIn("第 1 帧", content[2]["text"])
        self.assertIn("第 9 帧", content[4]["text"])

    async def test_group_image_addressed_by_name_routes_to_direct_chat(self):
        event = GroupMessageCreateEvent(
            id="group-image", content="奶龙酱看看这张图", timestamp="2026-10-17T19:00:00+08:00",
            group_id="g", group_openid="group-a", attachments=[IMAGE],
            author={"id": "u", "bot": False,
                    "member_openid": "member", "member_role": "member"},
        )
        self.assertTrue(nailong_ai.is_direct_chat(event, SimpleNamespace(self_id="robot")))

    async def test_group_at_image_is_sent_to_model_and_unreadable_image_is_reported(self):
        event = GroupAtMessageCreateEvent(
            id="at-image", content="这是什么", timestamp="2026-10-17T19:00:00+08:00",
            group_id="g", group_openid="group-a", attachments=[IMAGE],
            author={"id": "u", "bot": False,
                    "member_openid": "member", "member_role": "member"},
        )
        result = SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content='{"reply":"这是一只猫喵","sticker":"happy"}'))])
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(
                create=AsyncMock(return_value=result))),
            close=AsyncMock(),
        )
        qq_bot = SimpleNamespace(self_id="robot", send=AsyncMock())
        prepared = qq_images.PreparedImage(("data:image/png;base64,abc",), (1,), 1)
        with patch.object(nailong_ai, "load_image_inputs", AsyncMock(return_value=[prepared])), \
             patch.object(nailong_ai, "AsyncOpenAI", return_value=client), \
             patch.object(nailong_ai.chat, "finish", AsyncMock()) as finish:
            await nailong_ai.handle_chat(qq_bot, event)
        content = client.chat.completions.create.await_args.kwargs["messages"][-1]["content"]
        self.assertEqual(content[1]["type"], "image_url")
        finish.assert_awaited_once_with("这是一只猫喵")

        with patch.object(nailong_ai, "load_image_inputs", AsyncMock(side_effect=ImageLoadError("bad"))), \
             patch.object(nailong_ai, "AsyncOpenAI") as model, \
             patch.object(nailong_ai, "finish_reply", AsyncMock()) as send:
            await nailong_ai.handle_chat(qq_bot, event)
        model.assert_not_called()
        self.assertIn("没加载出来", send.await_args.args[2])

    async def test_quoted_group_image_in_msg_elements_reaches_vision_model(self):
        event = GroupAtMessageCreateEvent(
            id="quote-image", content="赏析图片", timestamp="2026-10-17T19:00:00+08:00",
            group_id="g", group_openid="group-a", message_type=103,
            message_scene={"ext": ["ref_msg_idx=quoted-id"], "source": "default"},
            msg_elements=[{
                "content": "", "message_type": 0, "msg_idx": "quoted-id",
                "attachments": [IMAGE],
            }],
            author={"id": "u", "bot": False,
                    "member_openid": "member", "member_role": "member"},
        )
        self.assertIsNone(event.reply)
        self.assertEqual(len(image_attachments(event)), 1)
        result = SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content='{"reply":"图里是两个玩偶喵","sticker":"happy"}'))])
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(
                create=AsyncMock(return_value=result))),
            close=AsyncMock(),
        )
        qq_bot = SimpleNamespace(self_id="robot", send=AsyncMock())
        prepared = qq_images.PreparedImage(("data:image/png;base64,abc",), (1,), 1)
        with patch.object(nailong_ai, "load_image_inputs", AsyncMock(return_value=[prepared])), \
             patch.object(nailong_ai, "AsyncOpenAI", return_value=client), \
             patch.object(nailong_ai.chat, "finish", AsyncMock()) as finish:
            await nailong_ai.handle_chat(qq_bot, event)
        content = client.chat.completions.create.await_args.kwargs["messages"][-1]["content"]
        self.assertEqual(content[1]["type"], "image_url")
        finish.assert_awaited_once_with("图里是两个玩偶喵")

    async def test_quote_without_image_gives_clear_retry_instruction(self):
        event = GroupAtMessageCreateEvent(
            id="quote-missing", content="赏析图片", timestamp="2026-10-17T19:00:00+08:00",
            group_id="g", group_openid="group-a", message_type=103,
            author={"id": "u", "bot": False,
                    "member_openid": "member", "member_role": "member"},
        )
        with patch.object(nailong_ai, "AsyncOpenAI") as model, \
             patch.object(nailong_ai, "finish_reply", AsyncMock()) as send:
            await nailong_ai.handle_chat(SimpleNamespace(self_id="robot"), event)
        model.assert_not_called()
        self.assertIn("引用没有把原图传给我", send.await_args.args[2])
