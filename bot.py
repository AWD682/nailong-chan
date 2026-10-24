import nonebot

from h5_quiz import start_h5_server, stop_h5_server
from qq_adapter import StableQQAdapter

nonebot.init(driver="~aiohttp")
nonebot.get_driver().register_adapter(StableQQAdapter)
nonebot.get_driver().on_startup(start_h5_server)
nonebot.get_driver().on_shutdown(stop_h5_server)
nonebot.load_plugin("ping")
if nonebot.load_plugin("chat_history") is None:
    raise RuntimeError("Failed to load chat_history; check the plugin file and startup log")
if nonebot.load_plugin("nailong_ai") is None:
    raise RuntimeError("Failed to load nailong_ai; check the plugin file and startup log")
if nonebot.load_plugin("mini_games") is None:
    raise RuntimeError("Failed to load mini_games; check the plugin file and startup log")
if nonebot.load_plugin("active_chat") is None:
    raise RuntimeError("Failed to load active_chat; check the plugin file and startup log")

if __name__ == "__main__":
    nonebot.run()
