"""奶龙快跑 H5:3D 跑酷小游戏,全部逻辑在浏览器本地运行。

与喵话真假共用同一个 H5 服务(由 h5_quiz.make_app 挂载路由)。
Three.js 已下载到 web/run/three.min.js,不依赖外网 CDN。
"""

from pathlib import Path

from aiohttp import web


ROOT = Path(__file__).parent
ASSETS = ROOT / "web" / "run"


async def page(_: web.Request) -> web.FileResponse:
    return web.FileResponse(ASSETS / "index.html",
                            headers={"Cache-Control": "no-store"})


async def stylesheet(_: web.Request) -> web.FileResponse:
    return web.FileResponse(ASSETS / "app.css")


async def javascript(_: web.Request) -> web.FileResponse:
    return web.FileResponse(ASSETS / "app.js",
                            headers={"Cache-Control": "no-cache"})


async def three_library(_: web.Request) -> web.FileResponse:
    return web.FileResponse(ASSETS / "three.min.js",
                            headers={"Cache-Control": "public, max-age=86400"})


async def module_asset(request: web.Request) -> web.FileResponse:
    asset = request.match_info["asset"]
    allowed = {
        "boot.js": ASSETS / "boot.js",
        "three.module.js": ASSETS / "three.module.js",
        "loaders/GLTFLoader.js": ASSETS / "loaders" / "GLTFLoader.js",
        "utils/BufferGeometryUtils.js": ASSETS / "utils" / "BufferGeometryUtils.js",
        "nailong.glb": ASSETS / "nailong.glb",
        "gameover-laugh.png": ROOT / "assets" / "memes" / "nailongchan-belly-laugh.png",
        "standees/crossed-arms.png": ASSETS / "standees" / "crossed-arms.png",
        "standees/belly-laugh.png": ASSETS / "standees" / "belly-laugh.png",
        "standees/side-view.png": ASSETS / "standees" / "side-view.png",
    }
    path = allowed.get(asset)
    if path is None or not path.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(path, headers={"Cache-Control": "no-cache"})


def add_routes(app: web.Application) -> None:
    """由 h5_quiz.make_app 调用，与喵话真假共用同一个端口。"""
    app.router.add_get("/run/", page)
    app.router.add_get("/run/app.css", stylesheet)
    app.router.add_get("/run/app.js", javascript)
    app.router.add_get("/run/three.min.js", three_library)
    app.router.add_get("/run/{asset:.*}", module_asset)
