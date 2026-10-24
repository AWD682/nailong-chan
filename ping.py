from nonebot import on_fullmatch

ping = on_fullmatch("测试", priority=1, block=True)

@ping.handle()
async def handle_ping():
    await ping.finish("奶龙酱收到啦喵！")