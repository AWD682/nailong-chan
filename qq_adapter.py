"""QQ 适配器的本地连接设置。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from nonebot.adapters.qq import Adapter as QQAdapter
from nonebot.drivers import Request, Timeout, WebSocket


class StableQQAdapter(QQAdapter):
    @asynccontextmanager
    async def websocket(self, setup: Request) -> AsyncIterator[WebSocket]:
        # 上游适配器固定传入 30 秒；群聊空闲时不应因此反复断线。
        if setup.timeout == 30.0:
            setup.timeout = Timeout(read=120.0, close=10.0)
        async with super().websocket(setup) as websocket:
            yield websocket
