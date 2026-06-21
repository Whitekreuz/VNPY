import asyncio
from collections import defaultdict
from typing import Any, Callable, Dict, List

class Event:
    """事件对象"""
    def __init__(self, type_: str, data: Any = None):
        self.type = type_
        self.data = data

class EventEngine:
    """基于 asyncio 的异步事件驱动引擎"""
    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._queue = asyncio.Queue()
        self._active = False
        self._task = None

    def register(self, type_: str, handler: Callable):
        """注册事件处理函数"""
        if handler not in self._handlers[type_]:
            self._handlers[type_].append(handler)

    def unregister(self, type_: str, handler: Callable):
        """注销事件处理函数"""
        if handler in self._handlers[type_]:
            self._handlers[type_].remove(handler)

    def put(self, event: Event):
        """发送事件。如果在其他线程调用，需小心跨线程循环，可使用 call_soon_threadsafe"""
        if self._active:
            try:
                self._queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def _run(self):
        """引擎主循环，持续从队列中获取事件并处理"""
        while self._active:
            try:
                event = await self._queue.get()
                self._process(event)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"EventEngine run error: {e}")

    def _process(self, event: Event):
        """处理事件，触发回调（支持同步和异步回调函数）"""
        if event.type in self._handlers:
            for handler in self._handlers[event.type]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        asyncio.create_task(handler(event))
                    else:
                        handler(event)
                except Exception as e:
                    print(f"Handler error for {event.type}: {e}")

    def start(self):
        """启动事件引擎（必须在运行的 asyncio loop 中调用）"""
        self._active = True
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        """停止事件引擎"""
        self._active = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
