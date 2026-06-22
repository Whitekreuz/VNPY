from datetime import datetime
from typing import List
from core.models import BarData
from data.db_manager import DBManager

class CtaBacktester:
    """本地脱机 CTA 策略回测引擎，通过历史 Bar 数据驱动策略执行"""
    def __init__(self, db_manager: DBManager):
        self.db_manager = db_manager
        self.strategy = None
        self.bars: List[BarData] = []
        
        # 回测基础统计
        self.capital = 1000000.0
        self.positions = 0
        self.trades = []
        
    def load_data(self, symbol: str, exchange: str, interval: str, start: datetime, end: datetime):
        print(f"开始从数据库加载历史数据: {symbol}.{exchange} [{start} 到 {end}]")
        self.bars = self.db_manager.load_bar_data(symbol, exchange, interval, start, end)
        print(f"数据加载完成，共计 {len(self.bars)} 根 K 线")
        
    def set_strategy(self, strategy_class):
        self.strategy = strategy_class(self)
        print(f"策略 {strategy_class.__name__} 已加载")
        
    def run_backtest(self):
        if not self.strategy:
            print("错误: 请先调用 set_strategy() 设置策略")
            return
        if not self.bars:
            print("错误: 请先调用 load_data() 加载回测数据")
            return
            
        print("开始回测...")
        # 触发策略的初始化逻辑
        if hasattr(self.strategy, 'on_init'):
            self.strategy.on_init()
        
        # 逐根 K 线推送驱动策略
        for bar in self.bars:
            self.strategy.on_bar(bar)
            
        print("回测数据遍历结束。等待后期生成资金曲线与报告...")
