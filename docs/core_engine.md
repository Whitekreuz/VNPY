# Core Engine 核心引擎模块说明

本模块是整个完全自主化量化交易系统的最底层基座。所有的市场行情（Tick/Bar）、交易反馈（Order/Trade）、系统日志（Log）都在这里以事件的形式流转。

## 架构设计理念

基于我们在前期规划中的原则，我们**没有使用**原生的 `threading` 多线程与阻塞队列（那是 VNPY 原生的方式），而是全面采用了现代 Python 的 **`asyncio` 异步协程模型**。

这种设计的巨大优势在于：
1. **消除了多线程带来的上下文切换开销和死锁风险**，在处理密集型 I/O 推送时更轻量。
2. **极佳的可扩展性**：方便未来与高性能 Web 框架（如基于 ASGI 的 FastAPI）无缝对接，从而直接利用同一套事件循环（Event Loop）推送 WebSocket 实时数据给我们的 Web 监控大屏。

## 文件与功能结构

1. **`models.py` (数据模型层)**：
   - 定义了所有的底层数据结构基类。
   - 彻底脱离第三方重型库，只使用原生的 `@dataclass` 保证纯净性。
   - 借鉴了 VNPY 经过千万次实盘验证的标准字段，如 `TickData`、`BarData`、`OrderData`，保证后续策略计算无缝兼容。

2. **`event_engine.py` (事件分发层)**：
   - 核心事件驱动中心。
   - 负责接收各种 Gateway (网关) 推入的 `Event`，并以非阻塞的方式将它们派发给所有注册订阅了该事件的策略、模块或 UI 客户端。
   - **支持混合回调**：在处理函数的分发上，同时兼容普通的同步函数 `def handler()` 和异步协程函数 `async def handler()`。

## 使用示例

```python
import asyncio
from core.event_engine import EventEngine, Event

async def main():
    # 实例化引擎
    engine = EventEngine()
    engine.start()
    
    # 1. 定义处理函数
    def my_handler(event: Event):
        print("收到最新行情事件：", event.data)
        
    # 2. 注册订阅 "TICK" 类型的事件
    engine.register("TICK", my_handler)
    
    # 3. 模拟发送事件（真实场景中由 Gateway 推送）
    engine.put(Event("TICK", data="AAPL $150"))
    
    # 保持运行
    await asyncio.sleep(1)
    
    # 优雅停止
    await engine.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

## 测试方式
我们为该模块编写了标准的 `unittest` 隔离异步测试用例。
进入项目根目录，运行以下命令即可测试：
```bash
python -m unittest tests.test_event_engine
```
