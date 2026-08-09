"""地磅重量模擬產生器"""
import asyncio
import random


async def weight_generator():
    """模擬從 RS232 讀取的地磅重量跳動（每 0.5 秒更新一次）"""
    base = 2000.0
    while True:
        yield round(base + random.uniform(-8.0, 8.0), 2)
        await asyncio.sleep(0.5)
