"""你画我猜 H5：玩家在网页上画画，奶龙酱看图猜。

与喵话真假共用同一个 H5 服务（由 h5_quiz.make_app 挂载路由）。
看图模型走现有 AI 接口：默认直接用聊天模型（qwen3.8-omni-flash 自带看图），
账号有 qwen-vl 权限时可在 .env 配 DRAW_VISION_MODEL 优先使用；
密钥沿用 AI_API_KEY，也可用 DRAW_API_KEY/DRAW_API_URL 覆盖。
"""

import base64
import json
import re
import secrets
from pathlib import Path

from aiohttp import web
from nonebot import get_plugin_config, logger
from openai import AsyncOpenAI
from pydantic import BaseModel


ROOT = Path(__file__).parent
ASSETS = ROOT / "web" / "draw"
MEMES = ROOT / "assets" / "memes"
MAX_IMAGE_BYTES = 6 * 1024 * 1024
# 留空表示直接用现有聊天模型看图；有 qwen-vl 权限时可配置成 qwen-vl-max 等。
DEFAULT_VISION_MODEL = ""
DATA_URL_RE = re.compile(
    r"^data:image/(?:png|jpeg|webp);base64,([A-Za-z0-9+/=]+)$")


class DrawConfig(BaseModel):
    draw_vision_model: str = DEFAULT_VISION_MODEL
    draw_api_key: str = ""
    draw_api_url: str = ""


_config: DrawConfig | None = None


def gen_config() -> DrawConfig:
    """与 quiz_api 相同的按需读取，保证脱离 NoneBot 也能单独预览。"""
    global _config
    if _config is None:
        _config = get_plugin_config(DrawConfig)
    return _config


def api_settings() -> tuple[str, str]:
    # 模块级 import nailong_ai 会在 NoneBot 初始化前读配置，放到运行时。
    import nailong_ai
    cfg = gen_config()
    return (cfg.draw_api_key or nailong_ai.config.ai_api_key,
            cfg.draw_api_url or nailong_ai.config.ai_base_url)


def available() -> bool:
    return bool(all(api_settings()))


# 题目全部是画面感强、几笔就能画出来的词；按难度再细分交给未来扩展。
WORD_BANK: dict[str, tuple[str, ...]] = {
    "动物": ("企鹅", "章鱼", "长颈鹿", "大熊猫", "螃蟹", "蜗牛", "猫头鹰",
             "恐龙", "刺猬", "孔雀", "乌龟", "鲨鱼"),
    "食物": ("冰淇淋", "汉堡包", "西瓜", "烤串", "寿司", "棒棒糖", "火锅",
             "煎蛋", "粽子", "菠萝"),
    "物品": ("雨伞", "火箭", "吉他", "灯塔", "望远镜", "机器人", "闹钟",
             "风筝", "眼镜", "滑板", "灯泡", "拖把"),
    "角色": ("宇航员", "超人", "僵尸", "美人鱼", "忍者", "小丑", "海盗",
             "魔法师", "吸血鬼", "外星人"),
    "动作": ("拔河", "游泳", "跳绳", "钓鱼", "滑雪", "荡秋千", "倒立",
             "打太极"),
}


def random_word() -> tuple[str, str]:
    category = secrets.choice(tuple(WORD_BANK))
    return secrets.choice(WORD_BANK[category]), category


def parse_guess(raw: str) -> dict | None:
    """只接受 {"guess":..., "alternatives":[...], "comment":..., "hit":...} 结构。"""
    content = (raw or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content,
                         flags=re.IGNORECASE).strip()
    try:
        data = json.loads(content)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    guess = data.get("guess")
    if not isinstance(guess, str) or not 1 <= len(guess.strip()) <= 40:
        return None
    alternatives = [item.strip() for item in data.get("alternatives", [])
                    if isinstance(item, str) and item.strip()
                    and len(item.strip()) <= 40][:2]
    comment = data.get("comment")
    comment = comment.strip() if isinstance(comment, str) else ""
    if len(comment) > 100:
        comment = comment[:100]
    hit = data.get("hit")
    return {"guess": guess.strip(), "alternatives": alternatives,
            "comment": comment, "hit": hit if type(hit) is bool else None}


def build_guess_messages(image_url: str) -> list[dict]:
    """盲猜提示词：只给画，绝不告诉模型题目，保证猜测是真的猜。"""
    return [
        {"role": "system", "content": (
            "你是 QQ 群机器人奶龙酱（奶龙女仆猫娘），正在和主人玩「你画我猜」。"
            "主人会在网页画板上画一幅简笔画，你要看图猜出画的是什么。"
            "画得再抽象也要大胆给出最可能的答案，猜测用简短的中文词。"
            "只输出一个 JSON 对象，不要 Markdown 或额外文字，格式为 "
            '{"guess":"最可能的答案","alternatives":["其他猜测"],'
            '"comment":"一句话奶龙式点评（带喵）"}。'
            "alternatives 最多再给 2 个猜测，实在没把握就留空数组。")},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": image_url}},
            {"type": "text", "text": "这就是主人画的画，奶龙酱仔细看看喵。"},
        ]},
    ]


def build_judge_messages(image_url: str, word: str, guess: str) -> list[dict]:
    """命中判定：拿着题目和盲猜答案对照看，只判断中不中。"""
    return [
        {"role": "system", "content": (
            "你是 QQ 群机器人奶龙酱（奶龙女仆猫娘），在「你画我猜」里当裁判。"
            "主人抽到的题目和奶龙酱的盲猜答案都会给你，请对照这幅画判断："
            "画的内容是不是题目（意思对、特征对就算中，画得丑不算错）。"
            "只输出一个 JSON 对象，不要 Markdown 或额外文字，格式为 "
            '{"hit":true,"comment":"一句话奶龙式点评（带喵）"}。'
            "hit 只能是 true 或 false；猜错了也要在点评里给主人留面子。")},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": image_url}},
            {"type": "text",
             "text": f"题目：「{word}」。奶龙酱盲猜的答案是「{guess}」。"},
        ]},
    ]


async def _chat(messages: list[dict]) -> str | None:
    """依次试配置的视觉模型和聊天模型，返回第一条文本；全失败返回 None。"""
    import nailong_ai
    api_key, base_url = api_settings()
    if not (api_key and base_url):
        logger.warning("你画我猜未配置 AI 接口")
        return None
    vision_model = gen_config().draw_vision_model.strip()
    models = [vision_model, nailong_ai.config.ai_model] if vision_model \
        else [nailong_ai.config.ai_model]
    for model in models:
        if not model:
            continue
        try:
            async with AsyncOpenAI(api_key=api_key, base_url=base_url,
                                   timeout=45.0, max_retries=0) as client:
                result = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    **({"modalities": ["text"]} if "omni" in model else {}),
                )
            content = result.choices[0].message.content
            if content:
                return content
            logger.warning("你画我猜模型返回空内容（model={}）", model)
        except Exception:
            logger.exception("你画我猜调用失败（model={}）", model)
    return None


def parse_judgement(raw: str) -> dict | None:
    """只接受 {"hit": 布尔, "comment": 可选点评} 的裁判结果。"""
    content = (raw or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content,
                         flags=re.IGNORECASE).strip()
    try:
        data = json.loads(content)
    except ValueError:
        return None
    if not isinstance(data, dict) or type(data.get("hit")) is not bool:
        return None
    comment = data.get("comment")
    comment = comment.strip() if isinstance(comment, str) else ""
    return {"hit": data["hit"], "comment": comment[:100]}


async def guess_drawing(image_url: str, word: str | None = None) -> dict | None:
    """先盲猜（看不到题目），有题目时再单独判命中；失败返回 None。"""
    blind_raw = await _chat(build_guess_messages(image_url))
    blind = parse_guess(blind_raw or "")
    if blind is None:
        return None
    result = {**blind, "hit": None}
    if word is None:
        return result
    try:
        judge_raw = await _chat(build_judge_messages(image_url, word, result["guess"]))
        judgement = parse_judgement(judge_raw or "")
    except Exception:
        logger.exception("你画我猜命中判定失败")
        judgement = None
    if judgement is not None:
        result["hit"] = judgement["hit"]
        if judgement["comment"]:
            result["comment"] = judgement["comment"]
    return result


async def page(_: web.Request) -> web.FileResponse:
    return web.FileResponse(ASSETS / "index.html",
                            headers={"Cache-Control": "no-store"})


async def stylesheet(_: web.Request) -> web.FileResponse:
    return web.FileResponse(ASSETS / "app.css")


async def javascript(_: web.Request) -> web.FileResponse:
    return web.FileResponse(ASSETS / "app.js")


async def mascot(request: web.Request) -> web.FileResponse:
    name = request.match_info["name"]
    allowed = {"wave": "wave.png", "happy": "happy.png", "sad": "sad.png"}
    if name not in allowed:
        raise web.HTTPNotFound()
    return web.FileResponse(MEMES / allowed[name])


async def json_body(request: web.Request) -> dict:
    if request.content_type != "application/json":
        raise web.HTTPUnsupportedMediaType(text="请发送 JSON")
    try:
        data = await request.json()
    except ValueError:
        raise web.HTTPBadRequest(text="JSON 格式不正确") from None
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text="请求内容不正确")
    return data


async def word(_: web.Request) -> web.Response:
    picked, category = random_word()
    return web.json_response({"word": picked, "category": category},
                             headers={"Cache-Control": "no-store"})


async def guess(request: web.Request) -> web.Response:
    data = await json_body(request)
    image = data.get("image")
    if not isinstance(image, str):
        raise web.HTTPBadRequest(text="没有收到画")
    matched = DATA_URL_RE.match(image)
    if matched is None:
        raise web.HTTPBadRequest(text="画的数据格式不对")
    if len(matched.group(1)) * 3 // 4 > MAX_IMAGE_BYTES:
        raise web.HTTPBadRequest(text="画太大啦，奶龙酱看不过来")
    word = data.get("word")
    word = word.strip() if isinstance(word, str) and word.strip() else None
    if word is not None and len(word) > 40:
        raise web.HTTPBadRequest(text="题目不对劲")
    result = await guess_drawing(image, word)
    if result is None:
        return web.json_response(
            {"error": "奶龙酱没能看出这幅画，稍等一下再让奶龙酱猜一次喵"},
            status=502, headers={"Cache-Control": "no-store"})
    return web.json_response(result, headers={"Cache-Control": "no-store"})


def add_routes(app: web.Application) -> None:
    """由 h5_quiz.make_app 调用，与喵话真假共用同一个端口。"""
    app.router.add_get("/draw/", page)
    app.router.add_get("/draw/app.css", stylesheet)
    app.router.add_get("/draw/app.js", javascript)
    app.router.add_get("/draw/mascot/{name}.png", mascot)
    app.router.add_post("/draw/api/word", word)
    app.router.add_post("/draw/api/guess", guess)
