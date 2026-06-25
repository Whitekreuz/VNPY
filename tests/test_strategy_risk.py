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
        
        # 模拟产生一系列 tick，跨越 6 分钟
        for minute in range(1, 7):
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
            datetime=datetime(2024, 1, 1, 9, 7, 0),
            last_price=4007.0
        )
        bg.update_tick(final_tick)
        
        # 检查是否生成了 6 根 1 分钟线
        self.assertEqual(len(bars_1m), 6)
        
        # 由于我们设置 window=5，前 5 根 1 分钟线应该合成出 1 根 5 分钟线
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

if __name__ == '__main__':
    unittest.main()
