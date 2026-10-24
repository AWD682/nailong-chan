"""别猜奶块 H5：奶龙版别踩白块，全部逻辑在浏览器本地运行。

与喵话真假共用同一个 H5 服务（由 h5_quiz.make_app 挂载路由）。
奶龙块的两张图片在 web/tiles 里；点块音效走 audio_clips 的 /audio/ 路由。
"""

from pathlib import Path

from aiohttp import web


ROOT = Path(__file__).parent
ASSETS = ROOT / "web" / "tiles"
IMAGES = {
    "nailong-laugh.png": ASSETS / "nailong-laugh.png",
    "nailong-arms.jpg": ASSETS / "nailong-arms.jpg",
}


async def page(_: web.Request) -> web.FileResponse:
    return web.FileResponse(ASSETS / "index.html",
                            headers={"Cache-Control": "no-store"})


async def stylesheet(_: web.Request) -> web.FileResponse:
    return web.FileResponse(ASSETS / "app.css")


async def javascript(_: web.Request) -> web.FileResponse:
    return web.FileResponse(ASSETS / "app.js",
                            headers={"Cache-Control": "no-cache"})


async def tile_image(request: web.Request) -> web.FileResponse:
    image = IMAGES.get(request.match_info["name"])
    if image is None or not image.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(image,
                            headers={"Cache-Control": "public, max-age=86400"})


def add_routes(app: web.Application) -> None:
    """由 h5_quiz.make_app 调用，与喵话真假共用同一个端口。"""
    app.router.add_get("/tiles/", page)
    app.router.add_get("/tiles/app.css", stylesheet)
    app.router.add_get("/tiles/app.js", javascript)
    app.router.add_get("/tiles/img/{name}", tile_image)
