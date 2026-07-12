import sys
import os
import unittest
from datetime import datetime

# 将项目根目录加入路径以便导入模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.models import TickData, BarData, OrderData
from strategy.bar_generator import BarGenerator
from risk.risk_manager import RiskManager

class DummyEngine:
    def write_log(self, msg):
        pass # print(msg)

class TestStrategyRisk(unittest.TestCase):
    def test_bar_generator(self):
        """测试 BarGenerator 是否能正确地从 Tick 聚合出 1 分钟 Bar 和 5 分钟 Bar"""
        bars_1m = []
        bars_5m = []
        
        def on_bar(bar: BarData):
            bars_1m.append(bar)
            bg.update_bar(bar)
            
        def on_5m_bar(bar: BarData):
            bars_5m.append(bar)
            
        bg = BarGenerator(on_bar, window=5, on_window_bar=on_5m_bar)
        
        # 模拟产生一系列 tick，从 0 分钟到 5 分钟 (共 6 分钟数据)
        for minute in range(0, 6):
            for second in [0, 30]:
                tick = TickData(
                    symbol="IF2401", exchange="CFFEX",
                    datetime=datetime(2024, 1, 1, 9, minute, second),
                    last_price=4000.0 + minute,
                    volume=10,
                    turnover=40000.0,
                    open_interest=100
                )
                bg.update_tick(tick)
                
        # 强制结束当前分钟 (产生一个不同分钟的 tick 触发最后一条1分钟线的生成)
        final_tick = TickData(
            symbol="IF2401", exchange="CFFEX",
            datetime=datetime(2024, 1, 1, 9, 6, 0),
            last_price=4006.0
        )
        bg.update_tick(final_tick)
        
        # 检查是否生成了 6 根 1 分钟线 (00, 01, 02, 03, 04, 05)
        self.assertEqual(len(bars_1m), 6)
        
        # 由于我们设置 window=5，前 5 根 1 分钟线 (00, 01, 02, 03, 04) 应该合成出 1 根 5 分钟线
        # 第 6 根 (05) 还在缓存中，尚未到 09 边界，因而只生成 1 根 5 分钟线
        self.assertEqual(len(bars_5m), 1)
        self.assertEqual(bars_5m[0].interval, "5m")
        self.assertEqual(bars_5m[0].volume, 100) # (1分钟线每根20volume, 5根=100)


    def test_risk_manager(self):
        """测试事前风控能否正确拦截非法报单"""
        engine = DummyEngine()
        rm = RiskManager(engine)
        
        # 创建一个测试订单
        order = OrderData(symbol="IF2401", exchange="CFFEX", orderid="1")
        
        # 测试正常报单
        self.assertTrue(rm.check_order(order))
        
        # 测试流控拦截 (将流控限制设为1)
        rm.order_flow_limit = 1
        # 第二次报单将被拦截，因为在同一秒内第一笔已经占用了1次流控
        self.assertFalse(rm.check_order(order))
        
        # 重置流控，再次报单可以成功
        rm.reset_flow_count()
        self.assertTrue(rm.check_order(order))
        
        # 测试撤单超限拦截
        rm.cancel_limit = 2
        rm.on_cancel(order)
        rm.on_cancel(order)
        # 第3次由于撤单次数已满2次，该品种再报单将被拦截
        self.assertFalse(rm.check_order(order))
        
        # 测试成交笔数超限拦截
        order2 = OrderData(symbol="IC2401", exchange="CFFEX", orderid="2")
        rm.reset_flow_count()
        self.assertTrue(rm.check_order(order2))
        
        rm.trade_limit = 1
        rm.on_trade(None) # 加1
        # 再次报单失败
        self.assertFalse(rm.check_order(order2))

    def test_risk_manager_auto_reset(self):
        """测试事前风控是否能够在一秒后自适应解锁流控限制"""
        engine = DummyEngine()
        rm = RiskManager(engine)
        order = OrderData(symbol="IF2401", exchange="CFFEX", orderid="1")
        
        rm.order_flow_limit = 1
        self.assertTrue(rm.check_order(order))
        # 第二次在同秒内必定被拦截
        self.assertFalse(rm.check_order(order))
        
        # 模拟时间流逝（直接修改内部缓存的时间戳为未来的某一秒）
        rm._last_second -= 2
        
        # 此时应该能够自动重置并报单成功
        self.assertTrue(rm.check_order(order))

    def test_bar_generator_missing_minutes(self):
        """测试 BarGenerator 在有分钟缺失时，是否仍能根据时间边界准确聚合，不出现数据错位"""
        bars_5m = []
        def on_bar(bar: BarData):
            bg.update_bar(bar)
        def on_5m_bar(bar: BarData):
            bars_5m.append(bar)
            
        bg = BarGenerator(on_bar, window=5, on_window_bar=on_5m_bar)
        
        # 喂入 09:00:00 的一分钟 bar
        bar0 = BarData(symbol="IF2401", exchange="CFFEX", datetime=datetime(2024, 1, 1, 9, 0), volume=10, interval="1m")
        # 喂入 09:01:00 的一分钟 bar
        bar1 = BarData(symbol="IF2401", exchange="CFFEX", datetime=datetime(2024, 1, 1, 9, 1), volume=10, interval="1m")
        # 09:02:00 和 09:03:00 缺失
        # 喂入 09:04:00 的一分钟 bar，它是这个 5m 窗口的边界 (04)
        bar4 = BarData(symbol="IF2401", exchange="CFFEX", datetime=datetime(2024, 1, 1, 9, 4), volume=10, interval="1m")
        
        bg.update_bar(bar0)
        bg.update_bar(bar1)
        bg.update_bar(bar4)
        
        # 检查是否成功输出了一根 5 分钟 bar（因为 9:04 是边界）
        self.assertEqual(len(bars_5m), 1)
        # 它的量应该是 30（10 * 3 根 K 线，缺了 2 根）
        self.assertEqual(bars_5m[0].volume, 30)
        
        # 喂入 09:05:00 属于下一根 5m bar 的开头，应该不会混入上一根
        bar5 = BarData(symbol="IF2401", exchange="CFFEX", datetime=datetime(2024, 1, 1, 9, 5), volume=10, interval="1m")
        bg.update_bar(bar5)
        self.assertEqual(len(bars_5m), 1)

        # 喂入 09:12:00，发生大空缺跨窗口，应该触发对 09:05 那根 bar 的自动结算推送
        bar12 = BarData(symbol="IF2401", exchange="CFFEX", datetime=datetime(2024, 1, 1, 9, 12), volume=10, interval="1m")
        bg.update_bar(bar12)
        # 此时应该推送了 09:05 区间的 bar，总数变为 2
        self.assertEqual(len(bars_5m), 2)
        self.assertEqual(bars_5m[1].volume, 10)
        self.assertEqual(bars_5m[1].datetime, datetime(2024, 1, 1, 9, 5))

if __name__ == '__main__':
    unittest.main()

