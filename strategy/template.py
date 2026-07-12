from typing import Any
from core.models import TickData, BarData, OrderData, TradeData, Direction, Offset

class CtaTemplate:
    """CTA策略基础模板"""
    author: str = ""
    parameters: list = []
    variables: list = []

    def __init__(self, cta_engine: Any, strategy_name: str, vt_symbol: str, setting: dict):
        self.cta_engine = cta_engine
        self.strategy_name = strategy_name
        self.vt_symbol = vt_symbol
        
        self.trading = False
        self.inited = False
        
        # 将配置设置应用到策略变量
        self.update_setting(setting)
        
    def update_setting(self, setting: dict):
        """更新策略参数"""
        for name in self.parameters:
            if name in setting:
                setattr(self, name, setting[name])
                
    def on_init(self):
        """策略初始化"""
        pass
        
    def on_start(self):
        """策略启动"""
        pass
        
    def on_stop(self):
        """策略停止"""
        pass
        
    def on_tick(self, tick: TickData):
        """收到Tick推送"""
        pass
        
    def on_bar(self, bar: BarData):
        """收到K线推送"""
        pass
        
    def on_order(self, order: OrderData):
        """收到报单回报"""
        pass
        
    def on_trade(self, trade: TradeData):
        """收到成交回报"""
        pass
        
    def buy(self, price: float, volume: float, stop: bool = False):
        """买开"""
        return self.send_order(Direction.LONG, Offset.OPEN, price, volume, stop)
        
    def sell(self, price: float, volume: float, stop: bool = False):
        """卖平"""
        return self.send_order(Direction.SHORT, Offset.CLOSE, price, volume, stop)
        
    def short(self, price: float, volume: float, stop: bool = False):
        """卖开"""
        return self.send_order(Direction.SHORT, Offset.OPEN, price, volume, stop)
        
    def cover(self, price: float, volume: float, stop: bool = False):
        """买平"""
        return self.send_order(Direction.LONG, Offset.CLOSE, price, volume, stop)
        
    def send_order(self, direction: Direction, offset: Offset, price: float, volume: float, stop: bool = False):
        if self.trading:
            return self.cta_engine.send_order(self, direction, offset, price, volume, stop)
        return ""
        
    def cancel_order(self, vt_orderid: str):
        """撤销报单"""
        if self.trading:
            self.cta_engine.cancel_order(self, vt_orderid)
            
    def write_log(self, msg: str):
        """记录日志"""
        self.cta_engine.write_log(f"{self.strategy_name}: {msg}")

