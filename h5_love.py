"""心动选修课 H5：校园恋爱互动故事，纯前端游戏，由 h5_quiz.make_app 挂载。

游戏本体在 web/love/，全部逻辑在浏览器本地运行，服务端只提供静态文件。
来自队友的原版接入，未改动游戏内容。
"""

from pathlib import Path

from aiohttp import web


ROOT = Path(__file__).parent
ASSETS = ROOT / "web" / "love"


async def root(_: web.Request) -> web.Response:
    raise web.HTTPPermanentRedirect("/love/")


async def page(_: web.Request) -> web.FileResponse:
    return web.FileResponse(ASSETS / "index.html",
                            headers={"Cache-Control": "no-store"})


def add_routes(app: web.Application) -> None:
    """由 h5_quiz.make_app 调用，与喵话真假共用同一个端口。"""
    app.router.add_get("/love", root)
    app.router.add_get("/love/", page)
    app.router.add_static("/love/", ASSETS, name="love")
