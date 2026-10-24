"""用 OpenAI 兼容接口为喵话真假批量实时出题。

接口与密钥放 .env（QUIZ_API_BASE_URL / QUIZ_API_KEY / QUIZ_MODEL）；
未配置或调用失败时，调用方退回 quiz_bank 的备用题库。
"""

import json
import re

from nonebot import get_plugin_config, logger
from openai import AsyncOpenAI
from pydantic import BaseModel

from quiz_bank import QUIZ_CATEGORIES, combined_category_label


DEFAULT_QUIZ_MODEL = "deepseek-chat"
MIN_QUESTION_CHARS = 6
MAX_QUESTION_CHARS = 80
MAX_EXPLANATION_CHARS = 160


class QuizGenConfig(BaseModel):
    quiz_api_key: str = ""
    quiz_api_base_url: str = ""
    quiz_model: str = DEFAULT_QUIZ_MODEL


_config: QuizGenConfig | None = None


def gen_config() -> QuizGenConfig:
    """h5_quiz 可脱离 NoneBot 单独预览，这里按需读取配置。"""
    global _config
    if _config is None:
        _config = get_plugin_config(QuizGenConfig)
    return _config


def available() -> bool:
    cfg = gen_config()
    return bool(cfg.quiz_api_key and cfg.quiz_api_base_url)


def parse_quiz_batch(raw: str, recent=()) -> list[tuple[str, bool, str]]:
    """只接受 {"questions":[...]} 里合法且没出过的题目，坏题直接丢弃。"""
    content = (raw or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content,
                         flags=re.IGNORECASE).strip()
    try:
        data = json.loads(content)
    except ValueError:
        return []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and isinstance(data.get("questions"), list):
        items = data["questions"]
    else:
        return []
    parsed: list[tuple[str, bool, str]] = []
    seen = set(recent)
    for item in items:
        if not isinstance(item, dict) or type(item.get("answer")) is not bool:
            continue
        question = item.get("question")
        explanation = item.get("explanation")
        if not isinstance(question, str) or not isinstance(explanation, str):
            continue
        question = " ".join(question.split())
        explanation = " ".join(explanation.split())
        if not (MIN_QUESTION_CHARS <= len(question) <= MAX_QUESTION_CHARS
                and 6 <= len(explanation) <= MAX_EXPLANATION_CHARS):
            continue
        if question.endswith(("?", "？")) or question in seen:
            continue
        seen.add(question)
        parsed.append((question, item["answer"], explanation))
    return parsed


def build_messages(count: int, categories: tuple[str, ...], recent) -> list[dict]:
    labels = "、".join(
        combined_category_label((key,)) if key in QUIZ_CATEGORIES else str(key)
        for key in categories
    ) or "、".join(QUIZ_CATEGORIES.values())
    return [
        {"role": "system", "content": (
            "你是 QQ 群小游戏‘喵话真假’的命题员。请围绕给定分类出 "
            f"{count} 道客观可核实的中文真假判断题，组成一个 JSON 对象。"
            "难度定位：有一定迷惑性、能考验爱好者水平，"
            "容易凭印象答错的冷知识或易混事实；"
            "绝不出主观评价、时效性新闻、冷僻争议、成人内容和无根据的角色设定。"
            "每题写成陈述句（以句号结尾），答案必须明确为真或假，"
            "解释简短且能说明理由。只输出 JSON 对象，不要 Markdown 或额外文字，"
            '格式为 {"questions":[{"question":"陈述句。","answer":true,'
            '"explanation":"理由。"}]}。'
        )},
        {"role": "user", "content": (
            f"分类：{labels}。题目数量：{count}。"
            "这些题最近出过，请全部避开："
            + json.dumps(list(recent), ensure_ascii=False)
        )},
    ]


async def generate_quiz_batch(count: int, categories: tuple[str, ...] = (),
                              recent=(), *, timeout: float = 40.0
                              ) -> list[tuple[str, bool, str]]:
    """失败时返回空列表，由调用方退回备用题库，游戏不中断。"""
    cfg = gen_config()
    if not available():
        return []
    try:
        async with AsyncOpenAI(
            api_key=cfg.quiz_api_key,
            base_url=cfg.quiz_api_base_url,
            timeout=timeout,
            max_retries=0,
        ) as client:
            result = await client.chat.completions.create(
                model=cfg.quiz_model,
                messages=build_messages(count, categories, recent),
                response_format={"type": "json_object"},
                temperature=1.1,
                max_tokens=min(4000, 300 + 200 * count),
            )
        questions = parse_quiz_batch(
            result.choices[0].message.content or "", recent)
        if len(questions) < count:
            logger.warning("实时出题只拿到 {}/{} 道可用题，不足部分用备用题补齐",
                           len(questions), count)
        return questions[:count]
    except Exception:
        logger.exception("喵话真假实时出题失败，退回备用题库")
        return []
