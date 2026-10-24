from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from nonebot.adapters.qq import MessageSegment
from nonebot.adapters.qq.event import C2CMessageCreateEvent

import bot  # noqa: F401 - 先初始化 NoneBot
import nailong_ai
import voice_reply


def private_message(content: str) -> C2CMessageCreateEvent:
    return C2CMessageCreateEvent(
        id="voice-test", content=content, timestamp="2026-10-17T23:00:00+08:00",
        author={"id": "u", "user_openid": "u"},
    )


class VoiceReplyTests(unittest.IsolatedAsyncioTestCase):
    def test_explicit_requests_only(self):
        for text in ("给我发条语音吧", "用语音回复我", "用嘴说出来", "把这句话念出来"):
            self.assertEqual(voice_reply.voice_request_kind(text), "speech")
        for text in ("给我唱首歌", "唱两句吧", "来首歌喵", "用语音唱雨爱",
                     "唱《雨爱》", "给我清唱雨爱", "唱雨爱"):
            self.assertEqual(voice_reply.voice_request_kind(text), "song")
        for text in ("你会唱歌吗？", "你会唱雨爱吗？", "别发语音", "别唱雨爱",
                     "帮我写一首歌", "谁唱的雨爱", "早上好"):
            self.assertIsNone(voice_reply.voice_request_kind(text))

    def test_current_provider_has_tts_endpoint(self):
        self.assertEqual(
            voice_reply.tts_endpoint("https://maas.qianwenaiapi.com/compatible-mode/v1"),
            "https://maas.qianwenaiapi.com/api/v1/services/audio/tts/SpeechSynthesizer",
        )
        with self.assertRaises(voice_reply.VoiceReplyError):
            voice_reply.tts_endpoint("https://unrelated.example/v1")
        self.assertTrue(voice_reply._allowed_audio_url(
            "http://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/example.mp3"
        ))
        self.assertFalse(voice_reply._allowed_audio_url("http://127.0.0.1/private"))
        self.assertEqual(
            voice_reply.music_endpoint("https://maas.qianwenaiapi.com/compatible-mode/v1"),
            "https://maas.qianwenaiapi.com/api/v1/services/audio/music/generation",
        )
        self.assertEqual(voice_reply.DEFAULT_VOICE, "longpaopao_v3.1")
        self.assertEqual(voice_reply.DEFAULT_SONG_MODEL, "qwen-audio-3.1-tts-next")
        self.assertIn("两句短小的原创中文歌词", voice_reply.song_prompt("给我唱首歌"))
        self.assertIn("无伴奏清唱", voice_reply.song_prompt("给我唱首歌"))
        self.assertNotIn("音乐盒", voice_reply.song_prompt("给我唱首歌"))
        self.assertIn("月亮", voice_reply.song_prompt("唱首关于月亮的歌"))
        self.assertIn("雨爱", voice_reply.song_prompt("用语音唱雨爱"))
        self.assertNotIn("用语音唱", voice_reply.song_prompt("用语音唱雨爱"))

    def test_existing_song_title_is_not_an_original_song_topic(self):
        for request in ("用语音唱雨爱", "唱《雨爱》", "给我唱首雨爱"):
            self.assertEqual(voice_reply.requested_song_title(request), "雨爱")
        for request in ("唱两句吧", "唱一首关于月亮的歌", "给我唱首歌"):
            self.assertIsNone(voice_reply.requested_song_title(request))

    async def test_audio_segment_is_sent_to_qq(self):
        event = private_message("发条语音")
        qq_bot = SimpleNamespace(send=AsyncMock())
        with patch.object(voice_reply, "synthesize_speech", AsyncMock(return_value=b"ID3test")):
            await voice_reply.send_voice_reply(
                qq_bot, event, "你好喵", api_key="fake", ai_base_url="https://maas.qianwenaiapi.com/compatible-mode/v1"
            )
        segment = qq_bot.send.await_args.args[1]
        self.assertIsInstance(segment, MessageSegment)
        self.assertEqual(segment.type, "file_audio")
        self.assertEqual(segment.data["content"], b"ID3test")

    async def test_song_segment_is_sent_to_qq(self):
        qq_bot = SimpleNamespace(send=AsyncMock())
        with patch.object(voice_reply, "generate_song", AsyncMock(return_value=b"ID3song")):
            await voice_reply.send_song_reply(
                qq_bot, private_message("唱首歌"), "唱首歌",
                api_key="fake", ai_base_url="https://maas.qianwenaiapi.com/compatible-mode/v1",
            )
        segment = qq_bot.send.await_args.args[1]
        self.assertEqual(segment.type, "file_audio")
        self.assertEqual(segment.data["content"], b"ID3song")

    async def test_song_rejects_unsupported_model(self):
        with self.assertRaises(voice_reply.VoiceReplyError):
            await voice_reply.generate_song(
                "唱首歌", api_key="fake", ai_base_url="https://maas.qianwenaiapi.com/compatible-mode/v1",
                model="unavailable-model",
            )

    async def test_direct_request_uses_voice_and_falls_back_to_text(self):
        answer = SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="来啦喵！")
        )])
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=answer))),
            close=AsyncMock(),
        )
        nailong_ai.history.clear()
        with patch.object(nailong_ai, "AsyncOpenAI", return_value=client), \
             patch.object(nailong_ai, "select_meme", AsyncMock(return_value=(None, {}, ""))), \
             patch.object(nailong_ai, "send_voice_reply", AsyncMock()) as send_voice, \
             patch.object(nailong_ai, "finish_reply", AsyncMock()) as finish:
            await nailong_ai.handle_chat(SimpleNamespace(), private_message("给我发条语音"))
        send_voice.assert_awaited_once()
        self.assertEqual(send_voice.await_args.kwargs["voice"], "longpaopao_v3.1")
        finish.assert_not_awaited()

        nailong_ai.history.clear()
        qq_bot = SimpleNamespace(send=AsyncMock())
        with patch.object(nailong_ai, "AsyncOpenAI", return_value=client) as ai_client, \
             patch.object(nailong_ai, "send_song_reply", AsyncMock()) as send_song, \
             patch.object(nailong_ai, "send_voice_reply", AsyncMock()) as send_voice:
            await nailong_ai.handle_chat(qq_bot, private_message("唱一首关于月亮的歌"))
        send_song.assert_awaited_once()
        self.assertEqual(send_song.await_args.args[2], "唱一首关于月亮的歌")
        send_voice.assert_not_awaited()
        ai_client.assert_not_called()
        self.assertEqual(qq_bot.send.await_count, 1)

        qq_bot = SimpleNamespace(send=AsyncMock())
        with patch.object(nailong_ai, "send_song_reply", AsyncMock(
            side_effect=voice_reply.VoiceReplyError("HTTP 403"))), \
             patch.object(nailong_ai, "send_voice_reply", AsyncMock()) as send_voice:
            await nailong_ai.handle_chat(qq_bot, private_message("唱两句吧"))
        send_voice.assert_not_awaited()
        self.assertIn("没生成出来", qq_bot.send.await_args.args[1])

    async def test_named_song_does_not_generate_unrelated_song(self):
        qq_bot = SimpleNamespace(send=AsyncMock())
        with patch.object(nailong_ai, "send_song_reply", AsyncMock()) as send_song:
            await nailong_ai.handle_chat(qq_bot, private_message("用语音唱雨爱"))
        send_song.assert_not_awaited()
        self.assertIn("原词原调", qq_bot.send.await_args.args[1])


if __name__ == "__main__":
    unittest.main()
