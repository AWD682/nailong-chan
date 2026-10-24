"""按明确请求把文字回复合成为 QQ 语音。"""

import asyncio
import re
from urllib.parse import urlparse

import aiohttp
from nonebot.adapters.qq import Bot, MessageSegment
from nonebot.adapters.qq.event import C2CMessageCreateEvent, GroupMessageCreateEvent


DEFAULT_MODEL = "qwen-audio-3.1-tts-flash"
DEFAULT_VOICE = "longpaopao_v3.1"
TTS_PATH = "/api/v1/services/audio/tts/SpeechSynthesizer"
MUSIC_PATH = "/api/v1/services/audio/music/generation"
DEFAULT_SONG_MODEL = "qwen-audio-3.1-tts-next"
MAX_AUDIO_BYTES = 8 * 1024 * 1024
MAX_SPEECH_CHARS = 180


class VoiceReplyError(Exception):
    """语音合成或下载失败；调用方应改用文字回复。"""


def voice_request_kind(question: str) -> str | None:
    """只处理明确要求奶龙酱开口的消息。"""
    text = question.strip()
    if re.search(r"(?:别|不要|不用|禁止|停止).{0,8}(?:发语音|语音回复|唱|哼|用嘴说)", text):
        return None
    if re.search(r"(?:你|她)?(?:会不会|会|能不能).{0,3}唱.{0,12}[吗么呀?？]$", text):
        return None
    if (re.search(r"(?:用语音|语音|用嘴|请|给我|帮我|来|快|现在).{0,10}(?:清唱|唱|哼唱)", text)
            or re.search(r"(?:清唱|唱)(?:一首|首|一段|两句|几句|歌|给我|给大家|《)|来首歌", text)
            or re.search(r"哼(?:一段|两句|几句|唱)", text)
            or re.fullmatch(r"(?:@?奶龙酱[，,\s]*)?(?:清唱|唱)[^，。！？?!\s]{1,24}[吧呗呀喵]?", text)):
        return "song"
    if re.search(r"发.{0,3}语音|语音(?:回复|回答|说|讲|念)|用语音|用嘴说|开口说|说出来|念出来|读出来", text):
        return "speech"
    return None


def requested_song_title(question: str) -> str | None:
    """识别要求唱现成歌名的指令，避免把歌名误当原创主题。"""
    if voice_request_kind(question) != "song":
        return None
    quoted = re.search(r"[《「『]([^》」』]{1,40})[》」』]", question)
    if quoted:
        return quoted.group(1).strip()
    match = re.search(r"(?:清唱|唱)(.+)$", question.strip())
    if not match:
        return None
    title = re.sub(r"^(?:一首|首)", "", match.group(1)).strip(" ，。！？!?：: \n\t")
    title = re.sub(r"(?:给我听|给大家听|给我们听|吧|呗|呀|喵)+$", "", title).strip()
    if (not title or len(title) > 30
            or title.startswith(("关于", "一段", "两句", "几句", "歌", "给我", "给大家"))
            or title in {"什么", "点什么", "一首歌"}):
        return None
    return title


def tts_endpoint(ai_base_url: str, override: str = "") -> str:
    """沿用现有千问 API 主机；其他服务需显式配置兼容的合成端点。"""
    if override:
        parsed = urlparse(override)
        if parsed.scheme != "https" or not parsed.netloc:
            raise VoiceReplyError("VOICE_API_URL 必须是 HTTPS 地址")
        return override.rstrip("/")
    parsed = urlparse(ai_base_url)
    if parsed.scheme != "https" or parsed.hostname != "maas.qianwenaiapi.com":
        raise VoiceReplyError("当前模型地址不是已配置的语音平台")
    return f"https://{parsed.hostname}{TTS_PATH}"


def music_endpoint(ai_base_url: str, override: str = "") -> str:
    """使用已有千问平台的音乐生成接口。"""
    if override:
        parsed = urlparse(override)
        if parsed.scheme != "https" or not parsed.netloc:
            raise VoiceReplyError("SONG_API_URL 必须是 HTTPS 地址")
        return override.rstrip("/")
    parsed = urlparse(ai_base_url)
    if parsed.scheme != "https" or parsed.hostname != "maas.qianwenaiapi.com":
        raise VoiceReplyError("当前模型地址不是已配置的音乐生成平台")
    return f"https://{parsed.hostname}{MUSIC_PATH}"


def _allowed_audio_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    allowed_host = (host == "aliyuncs.com" or host.endswith(".aliyuncs.com")
                    or host == "qianwenaiapi.com" or host.endswith(".qianwenaiapi.com"))
    return (parsed.scheme == "https" or (parsed.scheme == "http" and host.endswith(".aliyuncs.com"))) \
        and allowed_host and not parsed.username and not parsed.password


async def synthesize_speech(text: str, *, api_key: str, ai_base_url: str,
                            model: str = DEFAULT_MODEL, voice: str = DEFAULT_VOICE,
                            endpoint_override: str = "",
                            audio_format: str = "mp3") -> bytes:
    if not api_key:
        raise VoiceReplyError("没有配置语音服务密钥")
    endpoint = tts_endpoint(ai_base_url, endpoint_override)
    spoken = text.strip()[:MAX_SPEECH_CHARS]
    if not spoken:
        raise VoiceReplyError("没有可合成的文字")
    payload = {
        "model": model,
        "input": {
            "text": spoken,
            "voice": voice,
            "format": audio_format,
            "sample_rate": 24000,
            "instruction": "用活泼、稚气、亲切的语气自然说话，别把标点念出来。",
        },
    }
    timeout = aiohttp.ClientTimeout(total=90)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            ) as response:
                if response.status != 200:
                    raise VoiceReplyError(f"语音服务返回 HTTP {response.status}")
                result = await response.json()
            return await _download_audio(session, result, "语音")
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        raise VoiceReplyError("语音服务连接失败或超时") from exc


async def _download_audio(session: aiohttp.ClientSession, result: dict,
                          kind: str) -> bytes:
    output = result.get("output") if isinstance(result, dict) else None
    audio_info = output.get("audio") if isinstance(output, dict) else None
    audio_url = audio_info.get("url") if isinstance(audio_info, dict) else None
    if not isinstance(audio_url, str) or not _allowed_audio_url(audio_url):
        raise VoiceReplyError(f"{kind}服务没有返回可下载的音频")
    async with session.get(audio_url) as response:
        if response.status != 200:
            raise VoiceReplyError(f"下载{kind}返回 HTTP {response.status}")
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.content.iter_chunked(65536):
            size += len(chunk)
            if size > MAX_AUDIO_BYTES:
                raise VoiceReplyError(f"生成的{kind}超过大小限制")
            chunks.append(chunk)
        audio = b"".join(chunks)
        if not audio:
            raise VoiceReplyError(f"{kind}服务返回空音频")
        return audio


def song_prompt(question: str, *, model: str = DEFAULT_SONG_MODEL) -> str:
    topic = re.sub(r"@?奶龙酱|给我|请|用语音|用嘴|唱一首|唱首|唱歌|唱两句|唱几句|来首歌|清唱|哼唱|唱", " ", question)
    topic = re.sub(r"\s+", " ", topic).strip(" ，。！？!?：:")[:100]
    if not topic:
        topic = "奶龙酱和群友的快乐日常"
    if model.startswith("fun-music"):
        return (
            "原创中文迷你歌曲，由一个稚气、软萌、俏皮的女声无伴奏清唱。"
            "只有人声，没有乐器、鼓点、背景音乐、音效或和声，旋律自然连贯。"
            f"歌曲主题：{topic}。不要翻唱现成歌曲，也不要复用现成歌词。"
        )
    return (
        "创作一段十秒左右的原创中文儿歌清唱。"
        f"主题是：{topic}。"
        "只有一位稚气俏皮的年轻女声，像面对面轻声唱歌，用清晰、自然、连贯的旋律"
        "唱出两句短小的原创中文歌词。要有音高和节奏，不要只唱‘啦’，"
        "纯人声、无伴奏清唱；不要背景音乐、乐器、鼓点、音效或其他人声。"
        "不要朗读、旁白或解释，也不要翻唱现成歌曲。"
    )


async def generate_song(question: str, *, api_key: str, ai_base_url: str,
                        model: str = DEFAULT_SONG_MODEL,
                        endpoint_override: str = "") -> bytes:
    if not api_key:
        raise VoiceReplyError("没有配置音乐生成服务密钥")
    if model == "qwen-audio-3.1-tts-next":
        endpoint = tts_endpoint(ai_base_url, endpoint_override)
        payload = {
            "model": model,
            "input": {
                "text_prompt": song_prompt(question, model=model),
                "format": "mp3",
                "sample_rate": 24000,
                "channels": 1,
            },
        }
    elif model in ("fun-music-v1", "fun-music-preview"):
        endpoint = music_endpoint(ai_base_url, endpoint_override)
        payload = {
            "model": model,
            "input": {
                "prompt": song_prompt(question, model=model),
                "is_instrumental": False,
                "format": "mp3",
                **({"gender": "female"} if model == "fun-music-v1" else {}),
            },
        }
    else:
        raise VoiceReplyError("不支持的歌曲模型，请检查 SONG_MODEL")
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
            async with session.post(
                endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            ) as response:
                if response.status != 200:
                    raise VoiceReplyError(f"音乐生成服务返回 HTTP {response.status}")
                result = await response.json()
            return await _download_audio(session, result, "歌曲")
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        raise VoiceReplyError("音乐生成服务连接失败或超时") from exc


async def send_voice_reply(bot: Bot,
                           event: GroupMessageCreateEvent | C2CMessageCreateEvent,
                           text: str, *, api_key: str, ai_base_url: str,
                           model: str = DEFAULT_MODEL, voice: str = DEFAULT_VOICE,
                           endpoint_override: str = "") -> None:
    audio = await synthesize_speech(
        text, api_key=api_key, ai_base_url=ai_base_url,
        model=model, voice=voice, endpoint_override=endpoint_override,
    )
    await bot.send(event, MessageSegment.file_audio(audio, file_name="nailong.mp3"))


async def send_song_reply(bot: Bot,
                          event: GroupMessageCreateEvent | C2CMessageCreateEvent,
                          question: str, *, api_key: str, ai_base_url: str,
                          model: str = DEFAULT_SONG_MODEL,
                          endpoint_override: str = "") -> None:
    audio = await generate_song(
        question, api_key=api_key, ai_base_url=ai_base_url,
        model=model, endpoint_override=endpoint_override,
    )
    await bot.send(event, MessageSegment.file_audio(audio, file_name="nailong-song.mp3"))
