import asyncio
import unittest
import sys
import os

# 将项目根目录加入路径以便导入
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.event_engine import Event, EventEngine

class TestEventEngine(unittest.IsolatedAsyncioTestCase):
    async def test_event_dispatch(self):
        engine = EventEngine()
        engine.start()
        
        result = []
        
        # 同步回调函数
        def handler(event: Event):
            result.append(event.data)
            
        # 异步回调函数
        async def async_handler(event: Event):
            await asyncio.sleep(0.1)
            result.append("async_" + event.data)

        # 注册事件
        engine.register("TEST", handler)
        engine.register("TEST", async_handler)
        
        # 发送事件
        engine.put(Event("TEST", "hello"))
        
        # 给予事件循环足够的时间来处理队列及异步回调
        await asyncio.sleep(0.2)
        await engine.stop()
        
        # 验证结果
        self.assertIn("hello", result)
        self.assertIn("async_hello", result)

if __name__ == "__main__":
    unittest.main()
