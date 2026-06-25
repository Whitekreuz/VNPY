from typing import Callable, Optional
from core.models import TickData, BarData

class BarGenerator:
    """
    K线生成器：
    1. 基于 Tick 数据合成 1 分钟 Bar。
    2. 基于 1 分钟 Bar 合成 x 分钟 Bar (Window Bar)。
    """
    
    def __init__(self, on_bar: Callable, window: int = 0, on_window_bar: Callable = None):
        self.bar: Optional[BarData] = None
        self.on_bar = on_bar
        
        self.window = window
        self.window_bar: Optional[BarData] = None
        self.on_window_bar = on_window_bar
        
        self.interval_count = 0
        
    def update_tick(self, tick: TickData):
        """处理新的Tick数据"""
        new_minute = False
        
        if not self.bar:
            new_minute = True
        elif self.bar.datetime.minute != tick.datetime.minute:
            # 分钟发生改变，推送旧的bar
            self.on_bar(self.bar)
            new_minute = True
            
        if new_minute:
            # 创建新的1分钟bar
            self.bar = BarData(
                symbol=tick.symbol,
                exchange=tick.exchange,
                datetime=tick.datetime.replace(second=0, microsecond=0),
                open_price=tick.last_price,
                high_price=tick.last_price,
                low_price=tick.last_price,
                close_price=tick.last_price,
                volume=tick.volume,
                turnover=tick.turnover,
                open_interest=tick.open_interest,
                interval="1m"
            )
        else:
            # 更新当前的bar
            self.bar.high_price = max(self.bar.high_price, tick.last_price)
            self.bar.low_price = min(self.bar.low_price, tick.last_price)
            self.bar.close_price = tick.last_price
            self.bar.volume += tick.volume
            self.bar.turnover += tick.turnover
            self.bar.open_interest = tick.open_interest
            
    def update_bar(self, bar: BarData):
        """处理1分钟Bar数据，合成为X分钟Bar"""
        if not self.window or not self.on_window_bar:
            return
            
        if not self.window_bar:
            self.window_bar = BarData(
                symbol=bar.symbol,
                exchange=bar.exchange,
                datetime=bar.datetime,
                open_price=bar.open_price,
                high_price=bar.high_price,
                low_price=bar.low_price,
                close_price=bar.close_price,
                volume=bar.volume,
                turnover=bar.turnover,
                open_interest=bar.open_interest,
                interval=f"{self.window}m"
            )
        else:
            self.window_bar.high_price = max(self.window_bar.high_price, bar.high_price)
            self.window_bar.low_price = min(self.window_bar.low_price, bar.low_price)
            self.window_bar.close_price = bar.close_price
            self.window_bar.volume += bar.volume
            self.window_bar.turnover += bar.turnover
            self.window_bar.open_interest = bar.open_interest
            
        self.interval_count += 1
        if self.interval_count >= self.window:
            self.on_window_bar(self.window_bar)
            self.window_bar = None
            self.interval_count = 0
