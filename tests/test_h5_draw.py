import base64
import struct
import unittest
import zlib
from unittest.mock import AsyncMock, patch

from aiohttp.test_utils import TestClient, TestServer

import h5_draw
from h5_draw import WORD_BANK


def tiny_png() -> str:
    """手工拼一个 1x1 白色 PNG，只用来验证请求链路。"""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload)))

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\xff\xff")
    raw = (chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b""))
    return "data:image/png;base64," + base64.b64encode(raw).decode()


class H5DrawTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from h5_quiz import make_app
        self.server = TestServer(make_app())
        self.client = TestClient(self.server)
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    def test_parse_guess_accepts_valid_and_drops_invalid(self):
        parsed = h5_draw.parse_guess(
            '```json\n{"guess":" 企鹅 ","alternatives":["天鹅","鸭子","外星人"],'
            '"comment":"这脖子也太长了吧喵。","hit":true}\n```')
        self.assertEqual(parsed, {"guess": "企鹅", "alternatives": ["天鹅", "鸭子"],
                                  "comment": "这脖子也太长了吧喵。", "hit": True})
        self.assertIsNone(h5_draw.parse_guess("不是 JSON"))
        self.assertIsNone(h5_draw.parse_guess('{"guess":"  ","comment":"空的"}'))
        self.assertIsNone(h5_draw.parse_guess('{"comment":"没有答案"}'))
        loose = h5_draw.parse_guess('{"guess":"机器人"}')
        self.assertEqual(loose, {"guess": "机器人", "alternatives": [],
                                 "comment": "", "hit": None})

    def test_parse_guess_only_accepts_boolean_hit(self):
        parsed = h5_draw.parse_guess(
            '{"guess":"企鹅","hit":"true","comment":"字符串不算数"}')
        self.assertIsNone(parsed["hit"])

    def test_blind_guess_prompt_never_contains_the_word(self):
        messages = h5_draw.build_guess_messages("data:image/png;base64,eA==")
        for message in messages:
            self.assertNotIn("雨伞", str(message["content"]))
        # 命中判定是独立的第二步，此时才拿得到题目。
        judge = h5_draw.build_judge_messages(
            "data:image/png;base64,eA==", "雨伞", "蘑菇")
        self.assertIn("雨伞", str(judge[1]["content"]))
        self.assertIn("蘑菇", str(judge[1]["content"]))

    def test_parse_judgement_requires_boolean_hit(self):
        self.assertEqual(
            h5_draw.parse_judgement('{"hit":true,"comment":"中啦喵"}'),
            {"hit": True, "comment": "中啦喵"})
        self.assertIsNone(h5_draw.parse_judgement('{"hit":"true"}'))
        self.assertIsNone(h5_draw.parse_judgement('{"guess":"没有hit"}'))
        self.assertEqual(h5_draw.parse_judgement('{"hit":false}'),
                         {"hit": False, "comment": ""})

    async def test_pages_are_served(self):
        for path in ("/draw/", "/draw/app.css", "/draw/app.js",
                     "/draw/mascot/wave.png"):
            with self.subTest(path=path):
                response = await self.client.get(path)
                self.assertEqual(response.status, 200)
                self.assertTrue(await response.read())
        self.assertEqual((await self.client.get("/draw/mascot/other.png")).status, 404)

    async def test_word_endpoint_draws_from_bank(self):
        response = await self.client.post("/draw/api/word")
        self.assertEqual(response.status, 200)
        data = await response.json()
        self.assertIn(data["word"], WORD_BANK[data["category"]])
        self.assertIn(data["category"], WORD_BANK)

    async def test_guess_requires_a_data_url_image(self):
        for payload in ({}, {"image": "hello"}, {"image": "data:text/html;base64,eA=="}):
            with self.subTest(payload=payload):
                response = await self.client.post("/draw/api/guess", json=payload)
                self.assertEqual(response.status, 400)

    async def test_guess_returns_ai_result(self):
        result = {"guess": "企鹅", "alternatives": ["天鹅"], "comment": "可爱喵", "hit": True}
        with patch.object(h5_draw, "guess_drawing", AsyncMock(return_value=result)) as guess:
            response = await self.client.post("/draw/api/guess", json={
                "image": tiny_png(), "word": "企鹅"})
        self.assertEqual(response.status, 200)
        self.assertEqual(await response.json(), result)
        image = guess.await_args.args[0]
        self.assertTrue(image.startswith("data:image/png;base64,"))
        self.assertEqual(guess.await_args.args[1], "企鹅")

    async def test_guess_rejects_oversized_image(self):
        with patch.object(h5_draw, "MAX_IMAGE_BYTES", 16):
            response = await self.client.post("/draw/api/guess", json={
                "image": tiny_png()})
        self.assertEqual(response.status, 400)

    async def test_guess_reports_service_failure(self):
        with patch.object(h5_draw, "guess_drawing", AsyncMock(return_value=None)):
            response = await self.client.post("/draw/api/guess", json={
                "image": tiny_png()})
        self.assertEqual(response.status, 502)
        self.assertIn("error", await response.json())

    async def test_guess_works_without_a_word(self):
        result = {"guess": "房子", "alternatives": [], "comment": "", "hit": None}
        with patch.object(h5_draw, "guess_drawing", AsyncMock(return_value=result)) as guess:
            response = await self.client.post("/draw/api/guess", json={
                "image": tiny_png(), "word": "   "})
        self.assertEqual(response.status, 200)
        self.assertIsNone(guess.await_args.args[1])


if __name__ == "__main__":
    unittest.main()
