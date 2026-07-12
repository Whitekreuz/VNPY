from datetime import datetime
from typing import List
from core.models import BarData, Direction, Offset, TradeData
from data.db_manager import DBManager

class CtaBacktester:
    """本地脱机 CTA 策略回测引擎，通过历史 Bar 数据驱动策略执行"""
    def __init__(self, db_manager: DBManager):
        self.db_manager = db_manager
        self.strategy = None
        self.bars: List[BarData] = []
        
        # 回测基础统计
        self.datetime = None
        self.capital = 1000000.0
        self.positions = 0
        self.trades = []
        
    def load_data(self, symbol: str, exchange: str, interval: str, start: datetime, end: datetime):
        print(f"开始从数据库加载历史数据: {symbol}.{exchange} [{start} 到 {end}]")
        self.bars = self.db_manager.load_bar_data(symbol, exchange, interval, start, end)
        print(f"数据加载完成，共计 {len(self.bars)} 根 K 线")
        
    def set_strategy(self, strategy_class, strategy_name: str, vt_symbol: str, setting: dict):
        self.strategy = strategy_class(self, strategy_name, vt_symbol, setting)
        print(f"策略 {strategy_class.__name__} 已加载")
        
    def run_backtest(self):
        if not self.strategy:
            print("错误: 请先调用 set_strategy() 设置策略")
            return
        if not self.bars:
            print("错误: 请先调用 load_data() 加载回测数据")
            return
            
        print("开始回测...")
        self.strategy.inited = True
        self.strategy.trading = True
        
        # 触发策略的初始化逻辑
        if hasattr(self.strategy, 'on_init'):
            self.strategy.on_init()
        if hasattr(self.strategy, 'on_start'):
            self.strategy.on_start()
        
        # 逐根 K 线推送驱动策略
        for bar in self.bars:
            self.datetime = bar.datetime
            self.strategy.on_bar(bar)
            
        print("回测数据遍历结束。等待后期生成资金曲线与报告...")

    def send_order(self, strategy, direction: Direction, offset: Offset, price: float, volume: float, stop: bool = False):
        """模拟撮合：使用当前K线收盘价或者指定的限价立刻成交（简化模型）"""
        trade = TradeData(
            symbol=strategy.vt_symbol.split('.')[0],
            exchange=strategy.vt_symbol.split('.')[1],
            orderid=f"TEST_{len(self.trades)+1}",
            tradeid=f"TEST_{len(self.trades)+1}",
            direction=direction,
            offset=offset,
            price=price,
            volume=volume,
            datetime=self.datetime
        )
        self.trades.append(trade)
        
        # 计算虚拟持仓
        if direction == Direction.LONG and offset == Offset.OPEN:
            self.positions += volume
        elif direction == Direction.SHORT and offset == Offset.CLOSE:
            self.positions -= volume
        elif direction == Direction.SHORT and offset == Offset.OPEN:
            self.positions -= volume
        elif direction == Direction.LONG and offset == Offset.CLOSE:
            self.positions += volume
            
        # 回调策略
        if hasattr(strategy, 'on_trade'):
            strategy.on_trade(trade)
            
        return trade.orderid
        
    def cancel_order(self, strategy, vt_orderid: str):
        """模拟撤单（回测中已即时成交，此处仅记录状态）"""
        self.write_log(f"策略 {strategy.strategy_name} 请求撤单: {vt_orderid}")
        
    def write_log(self, msg: str):
        print(f"[{self.datetime}] {msg}")

