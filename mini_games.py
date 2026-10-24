"""群聊按钮小游戏：喵话真假（按钮版）+ 网页小游戏入口。"""

from collections import deque
from dataclasses import dataclass, replace
import json
import re
import secrets
import time

from nonebot import get_plugin_config, logger, on_message, on_notice
from nonebot.adapters import Event
from nonebot.adapters.qq import Bot, MessageSegment
from nonebot.adapters.qq.event import (
    GroupAtMessageCreateEvent,
    GroupMessageCreateEvent,
    InteractionCreateEvent,
)
from nonebot.adapters.qq.models import (
    Action,
    Button,
    InlineKeyboard,
    InlineKeyboardRow,
    MessageKeyboard,
    Permission,
    RenderData,
)
from nonebot.rule import Rule
from openai import AsyncOpenAI
from pydantic import BaseModel

import audio_clips
import quiz_api
from nailong_ai import config as ai_config, model_options
from quiz_bank import (
    QUIZ_CATEGORIES,
    combined_category_label,
    questions_for_categories,
)


SESSION_SECONDS = 300
MAX_SESSIONS = 512
QUIZ_ROUNDS = 10
BUTTON_PREFIX = "nlgame"
GAME_COMMAND = re.compile(r"/?(?:游戏|小游戏|玩游戏|来玩游戏|game)", re.IGNORECASE)


@dataclass(frozen=True)
class GameSession:
    kind: str
    group_openid: str
    owner_openid: str | None
    expires_at: float
    question: tuple[str, bool, str] | None = None
    round_number: int = 1
    correct_count: int = 0
    categories: tuple[str, ...] = ()


sessions: dict[str, GameSession] = {}
recent_questions: dict[str, deque[str]] = {}


# 模型不可用时才使用备用题；按钮只携带选项，答案始终留在服务端。
class GameWebConfig(BaseModel):
    h5_public_url: str = ""


web_config = get_plugin_config(GameWebConfig)

# 回调数据只允许一个冒号，分类按钮统一加 cat_ 前缀。
CATEGORY_ACTIONS = {f"cat_{key}": key for key in QUIZ_CATEGORIES}
START_QUIZ_ACTION = "start_quiz"
MAX_QUIZ_CATEGORIES = 3


def parse_generated_quiz(raw: str) -> tuple[str, bool, str] | None:
    """只接受有明确真假答案和简短解释的 JSON 判断题。"""
    content = raw.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content,
                         flags=re.IGNORECASE).strip()
    try:
        data = json.loads(content)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or type(data.get("answer")) is not bool:
        return None
    question = data.get("question")
    explanation = data.get("explanation")
    if not isinstance(question, str) or not isinstance(explanation, str):
        return None
    question = " ".join(question.split())
    explanation = " ".join(explanation.split())
    if not (6 <= len(question) <= 80 and 6 <= len(explanation) <= 160):
        return None
    if question.endswith(("?", "？")):
        return None
    return question, data["answer"], explanation


async def generate_quiz(group_openid: str,
                        categories: tuple[str, ...] = ()) -> tuple[str, bool, str] | None:
    """先试实时出题接口，再退回现有聊天模型，最后由调用方启用备用题。"""
    recent = list(recent_questions.get(group_openid, ()))
    if quiz_api.available():
        batch = await quiz_api.generate_quiz_batch(1, categories, recent)
        if batch:
            recent_questions.setdefault(group_openid, deque(maxlen=8)).append(batch[0][0])
            return batch[0]
    if not ai_config.ai_api_key or not ai_config.ai_model:
        logger.warning("喵话真假未配置模型，使用备用题")
        return None
    pool = tuple(categories) or tuple(QUIZ_CATEGORIES)
    label = combined_category_label(pool)
    topic_pool = "、".join(QUIZ_CATEGORIES.values())
    try:
        async with AsyncOpenAI(
            api_key=ai_config.ai_api_key,
            base_url=ai_config.ai_base_url,
            timeout=15.0,
            max_retries=0,
        ) as client:
            result = await client.chat.completions.create(
                model=ai_config.ai_model,
                **model_options(),
                max_tokens=240,
                messages=[
                    {"role": "system", "content": (
                        "你是 QQ 群小游戏‘喵话真假’的命题员。出一道与"
                        + ("、".join(combined_category_label((key,)) for key in pool))
                        + "相关的、客观可核实的中文真假判断题。"
                        "难度定位：有一定迷惑性、能考验爱好者水平，"
                        "容易凭印象答错的冷知识或易混事实，但绝不出主观评价、"
                        "时效性新闻、冷僻争议、成人内容和无根据的角色设定。"
                        "题目写成陈述句，答案必须明确为真或假；解释简短且能说明理由。"
                        "只输出 JSON 对象，不要 Markdown 或额外文字："
                        '{"question":"陈述句。","answer":true,"explanation":"理由。"}'
                    )},
                    {"role": "user", "content": (
                        f"可选分类有：{topic_pool}。本轮从这些分类里出题：{label}。"
                        "请避开本群最近出过的题："
                        + json.dumps(recent, ensure_ascii=False)
                    )},
                ],
            )
        quiz = parse_generated_quiz(result.choices[0].message.content or "")
        if quiz is None or quiz[0] in recent:
            logger.warning("喵话真假模型返回无效或重复题目，使用备用题")
            return None
        recent_questions.setdefault(group_openid, deque(maxlen=8)).append(quiz[0])
        return quiz
    except Exception:
        logger.exception("喵话真假模型出题失败，使用备用题")
        return None


def fallback_quiz(group_openid: str,
                  categories: tuple[str, ...] = ()) -> tuple[str, bool, str]:
    recent = recent_questions.setdefault(group_openid, deque(maxlen=8))
    pool = questions_for_categories(categories)
    candidates = [item for item in pool if item[0] not in recent]
    quiz = secrets.choice(candidates or pool)
    recent.append(quiz[0])
    return quiz


def is_game_command(event: Event) -> bool:
    """只拦截明确 @ 奶龙酱并要求玩游戏的群消息。"""
    if not isinstance(event, GroupMessageCreateEvent):
        return False
    mentioned = isinstance(event, GroupAtMessageCreateEvent) or any(
        getattr(mention, "is_you", False) for mention in event.mentions or []
    )
    return (mentioned and not event.author.bot
            and GAME_COMMAND.fullmatch(event.get_plaintext().strip()) is not None)


def new_session(kind: str, group_openid: str, owner_openid: str | None = None,
                question: tuple[str, bool, str] | None = None,
                round_number: int = 1, correct_count: int = 0,
                categories: tuple[str, ...] = ()) -> str:
    now = time.monotonic()
    for token, session in list(sessions.items()):
        if session.expires_at <= now:
            sessions.pop(token, None)
    while len(sessions) >= MAX_SESSIONS:
        sessions.pop(next(iter(sessions)))
    token = secrets.token_hex(6)
    while token in sessions:
        token = secrets.token_hex(6)
    sessions[token] = GameSession(
        kind, group_openid, owner_openid, now + SESSION_SECONDS,
        question, round_number, correct_count, categories
    )
    return token


def game_keyboard(token: str, rows: tuple[tuple[tuple[str, str], ...], ...],
                  links: tuple[tuple[str, str], ...] = ()) -> MessageKeyboard:
    def row_buttons(row: tuple[tuple[str, str], ...]) -> list[Button]:
        return [
            Button(
                id=f"{token}_{action}",
                render_data=RenderData(label=label, visited_label="已选择", style=1),
                action=Action(
                    type=1,
                    permission=Permission(type=2),
                    data=f"{BUTTON_PREFIX}:{token}:{action}",
                ),
            )
            for action, label in row
        ]

    buttons_per_row: list[list[Button]] = [row_buttons(row) for row in rows]
    # 网页入口每行放 2 个，避免一行挤太多按钮。
    for index in range(0, len(links), 2):
        buttons_per_row.append([
            Button(
                id=f"{token}_link{offset}",
                render_data=RenderData(label=label, visited_label="继续玩", style=1),
                action=Action(type=0, permission=Permission(type=2), data=url),
            )
            for offset, (label, url) in enumerate(links[index:index + 2],
                                                  start=index)
        ])
    return MessageKeyboard(content=InlineKeyboard(rows=[
        InlineKeyboardRow(buttons=button_row) for button_row in buttons_per_row
    ]))


async def send_card(bot: Bot, event: GroupMessageCreateEvent | InteractionCreateEvent,
                    title: str, token: str,
                    rows: tuple[tuple[tuple[str, str], ...], ...],
                    links: tuple[tuple[str, str], ...] = ()) -> None:
    message = MessageSegment.markdown(title) + MessageSegment.keyboard(
        game_keyboard(token, rows, links)
    )
    await bot.send(event, message)


QUIZ_CATEGORY_ROWS: tuple[tuple[tuple[str, str], ...], ...] = (
    tuple((f"cat_{key}", label) for key, label in list(QUIZ_CATEGORIES.items())[:4]),
    tuple((f"cat_{key}", label) for key, label in list(QUIZ_CATEGORIES.items())[4:]),
) + (((START_QUIZ_ACTION, "开始答题"),),)


def quiz_page_url() -> str:
    """云端配置了公网地址就用它；本机开发时退回本机地址（手机打不开）。"""
    return _web_page_url("quiz")


def draw_page_url() -> str:
    return _web_page_url("draw")


def run_page_url() -> str:
    return _web_page_url("run")


def tiles_page_url() -> str:
    return _web_page_url("tiles")


def love_page_url() -> str:
    return _web_page_url("love")


def _web_page_url(page: str) -> str:
    base = web_config.h5_public_url.strip().rstrip("/")
    if base.startswith("https://"):
        return f"{base}/{page}/"
    from h5_quiz import H5QuizConfig
    h5 = get_plugin_config(H5QuizConfig)
    host = "127.0.0.1" if h5.h5_host in ("", "0.0.0.0") else h5.h5_host
    return f"http://{host}:{h5.h5_port}/{page}/"


async def start_quiz_round(bot: Bot, event: InteractionCreateEvent,
                           group_openid: str, player: str,
                           round_number: int = 1, correct_count: int = 0,
                           categories: tuple[str, ...] = ()) -> None:
    quiz = await generate_quiz(group_openid, categories)
    if quiz is None:
        quiz = fallback_quiz(group_openid, categories)
    token = new_session("quiz", group_openid, player, quiz,
                        round_number, correct_count, categories)
    label = combined_category_label(categories)
    title = (f"## 喵话真假 · {label} · 第 {round_number}/{QUIZ_ROUNDS} 题 ❔\n"
             f"{quiz[0]}\n这句话是真的吗？"
             f"\n目前答对 {correct_count}/{round_number - 1} 题")
    try:
        await send_card(bot, event, title, token,
                        ((("true", "真的"), ("false", "假的")),))
    except Exception:
        sessions.pop(token, None)
        logger.exception("奶龙酱发送游戏题目失败")
        await bot.send(event, "这局没开成，再 @ 奶龙酱说「游戏」试试喵。")


game_menu = on_message(rule=Rule(is_game_command), priority=5, block=True)


@game_menu.handle()
async def open_game_menu(bot: Bot, event: GroupMessageCreateEvent) -> None:
    token = new_session("menu", event.group_openid)
    quiz_url = quiz_page_url()
    draw_url = draw_page_url()
    run_url = run_page_url()
    tiles_url = tiles_page_url()
    love_url = love_page_url()
    links = (("奶龙快跑", run_url), ("你画我猜", draw_url),
             ("喵话真假 H5", quiz_url), ("别猜奶块", tiles_url),
             ("心动选修课", love_url))
    public = web_config.h5_public_url.strip().startswith("https://")
    hint = (f"\n「喵话真假」点按钮直接答；网页版五连：奶龙快跑 {run_url}、"
            f"你画我猜 {draw_url}、喵话真假 {quiz_url}、别猜奶块 {tiles_url}、"
            f"心动选修课 {love_url}")
    if not public:
        hint += "（手机要玩网页版需管理员配置 H5_PUBLIC_URL 喵）"
    rows = ((("quiz", "喵话真假"),),)
    try:
        await send_card(bot, event, "## 奶龙酱的小游戏 🎮\n选一个来玩喵！" + hint,
                        token, rows, links)
    except Exception:
        if links:
            try:
                await send_card(
                    bot, event, "## 奶龙酱的小游戏 🎮\n选一个来玩喵！", token, rows,
                )
                logger.warning("带网页链接的游戏菜单发送失败，已退回纯按钮菜单")
                return
            except Exception:
                pass
        sessions.pop(token, None)
        logger.exception("奶龙酱发送游戏菜单失败")
        await bot.send(event, "游戏菜单暂时打不开，稍后再试试喵。")


def is_game_interaction(event: Event) -> bool:
    return (isinstance(event, InteractionCreateEvent)
            and (event.data.resolved.button_data or "").startswith(f"{BUTTON_PREFIX}:"))


game_click = on_notice(rule=Rule(is_game_interaction), priority=5, block=True)


async def acknowledge(bot: Bot, event: InteractionCreateEvent, code: int) -> None:
    try:
        await bot.put_interaction(interaction_id=event.id, code=code)
    except Exception:
        logger.exception("奶龙酱确认游戏按钮失败")


@game_click.handle()
async def handle_game_click(bot: Bot, event: InteractionCreateEvent) -> None:
    data = event.data.resolved.button_data or ""
    if not data.startswith(f"{BUTTON_PREFIX}:"):
        return
    parts = data.split(":")
    if len(parts) != 3:
        await acknowledge(bot, event, 1)
        return
    _, token, action = parts
    session = sessions.get(token)
    if session is None:
        await acknowledge(bot, event, 3)
        return
    if session.expires_at <= time.monotonic():
        sessions.pop(token, None)
        await acknowledge(bot, event, 3)
        return
    if event.chat_type != 1 or event.group_openid != session.group_openid:
        await acknowledge(bot, event, 4)
        return
    player = event.group_member_openid
    if not player or (session.owner_openid and player != session.owner_openid):
        await acknowledge(bot, event, 4)
        return

    if session.kind == "menu" and action == "quiz":
        sessions.pop(token, None)
        await acknowledge(bot, event, 0)
        next_token = new_session("quiz_category", session.group_openid, player)
        try:
            await send_card(
                bot, event,
                "## 喵话真假 · 选分类 🗂️\n"
                f"点分类挑选（可多选 {MAX_QUIZ_CATEGORIES} 个，再点一次取消），"
                f"选好点「开始答题」，{QUIZ_ROUNDS} 题一决胜负喵！",
                next_token, QUIZ_CATEGORY_ROWS,
            )
        except Exception:
            sessions.pop(next_token, None)
            logger.exception("奶龙酱发送分类菜单失败")
            await bot.send(event, "这局没开成，再 @ 奶龙酱说「游戏」试试喵。")
        return

    if session.kind == "quiz_category" and action in CATEGORY_ACTIONS:
        key = CATEGORY_ACTIONS[action]
        picked = list(session.categories)
        if key in picked:
            picked.remove(key)
        elif len(picked) >= MAX_QUIZ_CATEGORIES:
            await acknowledge(bot, event, 0)
            await bot.send(event, f"最多选 {MAX_QUIZ_CATEGORIES} 个分类喵，先取消一个再换吧。")
            return
        else:
            picked.append(key)
        # 分类选择存进会话；按钮卡不能更新，用文字反馈当前进度。
        sessions[token] = replace(session, categories=tuple(picked))
        await acknowledge(bot, event, 0)
        if picked:
            selection = "、".join(combined_category_label((key,)) for key in picked)
            remaining = MAX_QUIZ_CATEGORIES - len(picked)
            tail = (f"还可以再选 {remaining} 个，或点「开始答题」开局喵。"
                    if remaining else "选满啦，点「开始答题」开局喵！")
            await bot.send(event, f"已选分类：{selection}。{tail}")
        else:
            await bot.send(event, "分类都取消啦，先点亮至少 1 个分类喵。")
        return

    if session.kind == "quiz_category" and action == START_QUIZ_ACTION:
        await acknowledge(bot, event, 0)
        if not session.categories:
            # 保留会话，玩家还能继续挑分类。
            await bot.send(event, "还没选分类喵，先点亮至少 1 个再开始。")
            return
        sessions.pop(token, None)
        await start_quiz_round(
            bot, event, session.group_openid, player,
            categories=session.categories,
        )
        return

    if (session.kind == "quiz" and session.question is not None
            and action in ("true", "false")):
        sessions.pop(token, None)
        await acknowledge(bot, event, 0)
        question, answer, explanation = session.question
        correct = (action == "true") == answer
        verdict = "答对啦，聪明喵！" if correct else "答错啦，奶龙酱偷笑一下喵。"
        correct_count = session.correct_count + int(correct)
        label = combined_category_label(session.categories)
        # 答对答错都放氦气大笑：答对是庆祝，答错是奶龙酱偷笑喵。
        await audio_clips.send_clip(bot, event, "helium")

        if session.round_number >= QUIZ_ROUNDS:
            score_text = (f"喵话真假·{label}收官！{QUIZ_ROUNDS} 题答对 "
                          f"{correct_count}/{QUIZ_ROUNDS} 题喵。")
            if correct_count == QUIZ_ROUNDS:
                score_text += "十题全对，奶龙酱膜拜大佬喵！"
            elif correct_count >= QUIZ_ROUNDS // 2:
                score_text += "成绩不错，换个分类再战一轮？"
            else:
                score_text += "被绕晕也没关系，再挑一个分类玩一局喵。"
            await bot.send(event, score_text)
            return

        next_token = new_session(
            "quiz_result", session.group_openid, player,
            round_number=session.round_number, correct_count=correct_count,
            categories=session.categories,
        )
        title = (f"## {verdict}\n题目：{question}\n"
                 f"答案：{'真的' if answer else '假的'}。{explanation}\n"
                 f"目前答对 {correct_count}/{session.round_number} 题。继续挑战吗？")
        try:
            await send_card(bot, event, title, next_token,
                            ((("next", "下一题"), ("end", "结束游戏")),))
        except Exception:
            sessions.pop(next_token, None)
            logger.exception("奶龙酱发送答题结果失败")
            await bot.send(event, title)
        return

    if session.kind == "quiz_result" and action in ("next", "end"):
        sessions.pop(token, None)
        await acknowledge(bot, event, 0)
        if action == "end":
            label = combined_category_label(session.categories)
            await bot.send(event, (f"喵话真假·{label}结束啦！这次答对 "
                                   f"{session.correct_count}/{session.round_number} 题喵。"))
        else:
            await start_quiz_round(
                bot, event, session.group_openid, player,
                session.round_number + 1, session.correct_count,
                categories=session.categories,
            )
        return

    await acknowledge(bot, event, 1)
