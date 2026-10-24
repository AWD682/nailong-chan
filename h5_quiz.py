"""喵话真假 H5：与 QQ 机器人同进程运行的轻量网页和答题 API。"""

from collections import deque
from dataclasses import dataclass
import random
import secrets
import time
from pathlib import Path

from aiohttp import web
from nonebot import get_plugin_config, logger
from pydantic import BaseModel, Field

import audio_clips
import quiz_api
import h5_draw
import h5_love
import h5_run
import h5_tiles
from quiz_bank import QUIZ_CATEGORIES, combined_category_label, questions_for_categories


ROOT = Path(__file__).parent
ASSETS = ROOT / "web" / "quiz"
MEMES = ROOT / "assets" / "memes"
ROUND_COUNT = 10
MAX_CATEGORIES = 3
SESSION_SECONDS = 30 * 60
MAX_SESSIONS = 512


class H5QuizConfig(BaseModel):
    h5_host: str = "127.0.0.1"
    h5_port: int = Field(default=8765, ge=1, le=65535)


@dataclass
class QuizSession:
    questions: tuple[tuple[str, bool, str], ...]
    expires_at: float
    categories: tuple[str, ...]
    index: int = 0
    score: int = 0
    streak: int = 0
    answered: bool = False


sessions: dict[str, QuizSession] = {}
runner: web.AppRunner | None = None
# 网页局没有群身份，用全局队列记住最近出过的题，避免连续开局重复。
recent_questions: deque[str] = deque(maxlen=40)


def clean_sessions() -> None:
    now = time.monotonic()
    for token, session in list(sessions.items()):
        if session.expires_at <= now:
            sessions.pop(token, None)
    while len(sessions) >= MAX_SESSIONS:
        sessions.pop(next(iter(sessions)))


def question_payload(session: QuizSession) -> dict:
    return {
        "number": session.index + 1,
        "total": len(session.questions),
        "question": session.questions[session.index][0],
        "score": session.score,
        "streak": session.streak,
        "categories": list(session.categories),
        "category_label": combined_category_label(session.categories),
    }


async def page(_: web.Request) -> web.FileResponse:
    return web.FileResponse(ASSETS / "index.html", headers={"Cache-Control": "no-store"})


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


def get_session(request: web.Request, data: dict) -> QuizSession:
    token = data.get("session_id")
    if not isinstance(token, str) or not token:
        raise web.HTTPBadRequest(text="缺少游戏编号")
    session = sessions.get(token)
    if session is None or session.expires_at <= time.monotonic():
        sessions.pop(token, None)
        raise web.HTTPNotFound(text="本局已过期，请重新开始")
    return session


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


async def start(request: web.Request) -> web.Response:
    data = await json_body(request)
    clean_sessions()
    categories = pick_categories(data)
    questions = await build_round_questions(categories)
    token = secrets.token_urlsafe(24)
    while token in sessions:
        token = secrets.token_urlsafe(24)
    session = QuizSession(questions, time.monotonic() + SESSION_SECONDS, categories)
    sessions[token] = session
    recent_questions.extend(item[0] for item in questions)
    return web.json_response({"session_id": token, **question_payload(session)},
                             headers={"Cache-Control": "no-store"})


async def build_round_questions(categories: tuple[str, ...]
                                ) -> tuple[tuple[str, bool, str], ...]:
    """优先实时出题；不够或失败时从备用题库补齐，保证每局足 10 题。"""
    rng = random.SystemRandom()
    questions: list[tuple[str, bool, str]] = []
    if quiz_api.available():
        try:
            questions = list(await quiz_api.generate_quiz_batch(
                ROUND_COUNT, categories, recent_questions))
        except Exception:
            # 实时出题出错时退回备用题库，开局不失败。
            logger.exception("实时出题接口异常，本局使用备用题库")
            questions = []
    if len(questions) < ROUND_COUNT:
        pool = [item for item in questions_for_categories(categories)
                if item[0] not in {q[0] for q in questions}
                and item[0] not in recent_questions]
        pool = pool or [item for item in questions_for_categories(categories)
                        if item[0] not in {q[0] for q in questions}]
        if len(pool) >= ROUND_COUNT - len(questions):
            questions.extend(rng.sample(pool, ROUND_COUNT - len(questions)))
        else:
            questions.extend(rng.choices(pool, k=ROUND_COUNT - len(questions)))
    return tuple(questions[:ROUND_COUNT])


def pick_categories(data: dict) -> tuple[str, ...]:
    """接受 categories 列表（1-3 个）；兼容旧的单分类 category 字段。"""
    if "categories" in data:
        raw = data["categories"]
        if not isinstance(raw, list) or not (1 <= len(raw) <= MAX_CATEGORIES):
            raise web.HTTPBadRequest(text=f"请选择 1-{MAX_CATEGORIES} 个分类喵")
        categories: list[str] = []
        for item in raw:
            if not isinstance(item, str) or item not in QUIZ_CATEGORIES:
                raise web.HTTPBadRequest(text="没有这个分类喵")
            if item not in categories:
                categories.append(item)
        return tuple(categories)
    if "category" in data:
        return pick_categories({"categories": [data["category"]]})
    # 老客户端什么都没传时随机抽一个，保持向后兼容。
    return (random.SystemRandom().choice(tuple(QUIZ_CATEGORIES)),)


async def answer(request: web.Request) -> web.Response:
    data = await json_body(request)
    session = get_session(request, data)
    if session.answered:
        raise web.HTTPConflict(text="这题已经回答过啦")
    if type(data.get("number")) is not int or data["number"] != session.index + 1:
        raise web.HTTPConflict(text="题目编号不匹配")
    if type(data.get("choice")) is not bool:
        raise web.HTTPBadRequest(text="答案必须是真的或假的")
    question, correct_answer, explanation = session.questions[session.index]
    correct = data["choice"] == correct_answer
    session.answered = True
    session.score += int(correct)
    session.streak = session.streak + 1 if correct else 0
    return web.json_response({
        "question": question,
        "correct": correct,
        "answer": correct_answer,
        "explanation": explanation,
        "score": session.score,
        "streak": session.streak,
        "finished": session.index + 1 == len(session.questions),
        "total": len(session.questions),
    }, headers={"Cache-Control": "no-store"})


async def next_question(request: web.Request) -> web.Response:
    data = await json_body(request)
    session = get_session(request, data)
    if not session.answered or session.index + 1 >= len(session.questions):
        raise web.HTTPConflict(text="现在还不能进入下一题")
    session.index += 1
    session.answered = False
    return web.json_response(question_payload(session),
                             headers={"Cache-Control": "no-store"})


async def categories(_: web.Request) -> web.Response:
    return web.json_response(
        {"categories": list(QUIZ_CATEGORIES.items())},
        headers={"Cache-Control": "no-store"},
    )


def make_app() -> web.Application:
    # 你画我猜要上传整幅画的 PNG，比普通接口的包大得多。
    app = web.Application(client_max_size=8 * 1024 * 1024)
    app.router.add_get("/quiz/", page)
    app.router.add_get("/quiz/app.css", stylesheet)
    app.router.add_get("/quiz/app.js", javascript)
    app.router.add_get("/quiz/mascot/{name}.png", mascot)
    app.router.add_get("/quiz/api/categories", categories)
    app.router.add_post("/quiz/api/start", start)
    app.router.add_post("/quiz/api/answer", answer)
    app.router.add_post("/quiz/api/next", next_question)
    h5_draw.add_routes(app)
    h5_love.add_routes(app)
    h5_run.add_routes(app)
    h5_tiles.add_routes(app)
    audio_clips.add_routes(app)
    return app


async def start_h5_server() -> None:
    global runner
    config = get_plugin_config(H5QuizConfig)
    runner = web.AppRunner(make_app(), access_log=None)
    await runner.setup()
    try:
        site = web.TCPSite(runner, config.h5_host, config.h5_port)
        await site.start()
    except Exception:
        await runner.cleanup()
        runner = None
        raise
    logger.info("喵话真假 H5 已启动：http://{}:{}/quiz/", config.h5_host, config.h5_port)


async def stop_h5_server() -> None:
    global runner
    if runner is not None:
        await runner.cleanup()
        runner = None


if __name__ == "__main__":
    # 只预览网页，不连接 QQ；正式运行时由 bot.py 启动同一个服务。
    web.run_app(make_app(), host="127.0.0.1", port=8765)
