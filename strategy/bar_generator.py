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
            
        # 如果当前没有 window_bar，直接创建
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
            return

        # 检查是否跨越了时间窗口边界
        # 算法：计算两个 Bar 的分钟区间起始点是否一致
        # 为了应对跨小时的情况，使用当天总分钟数来进行计算
        t1 = self.window_bar.datetime.hour * 60 + self.window_bar.datetime.minute
        t2 = bar.datetime.hour * 60 + bar.datetime.minute
        
        # 边界计算
        start1 = t1 - (t1 % self.window)
        start2 = t2 - (t2 % self.window)
        
        # 如果区间起始点不一致，说明跨越了窗口，需要推送旧的并开辟新的
        if start1 != start2:
            self.on_window_bar(self.window_bar)
            
            # 创建新的 window_bar
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
            # 在同一个区间内，累加更新
            self.window_bar.high_price = max(self.window_bar.high_price, bar.high_price)
            self.window_bar.low_price = min(self.window_bar.low_price, bar.low_price)
            self.window_bar.close_price = bar.close_price
            self.window_bar.volume += bar.volume
            self.window_bar.turnover += bar.turnover
            self.window_bar.open_interest = bar.open_interest

        # 再次检查：如果是窗口边界的最后一根（例如 04, 09, 14 分），则在此刻直接推送，避免延迟
        t_curr = bar.datetime.hour * 60 + bar.datetime.minute
        if (t_curr + 1) % self.window == 0:
            self.on_window_bar(self.window_bar)
            self.window_bar = None

