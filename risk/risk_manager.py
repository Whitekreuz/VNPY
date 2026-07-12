from core.models import OrderData, TradeData, Direction
from typing import Callable, Any

class RiskManager:
    """事前风控管理器，在交易网关发出委托之前拦截过滤非法请求"""
    
    def __init__(self, trading_engine: Any):
        self.trading_engine = trading_engine
        
        self.active = True
        
        # 风控限制阈值
        self.order_flow_count = 0
        self.order_flow_limit = 50      # 每秒最大报单次数
        self._last_second = 0           # 缓存上一次报单秒数，用以自适应秒级流控清零
        
        self.trade_count = 0
        self.trade_limit = 1000         # 每日最大成交笔数
        
        self.cancel_count = {}          # dict[vt_symbol, int]
        self.cancel_limit = 500         # 单合约每日最大撤单次数
        
    def check_order(self, order_req: OrderData) -> bool:
        """检查委托单是否合法"""
        if not self.active:
            return True
            
        # 1. 自适应秒级流控重置 (若进入了新的一秒则自动将计数清零，不需要依赖外部定时器)
        import time
        now_sec = int(time.time())
        if self._last_second != now_sec:
            self._last_second = now_sec
            self.order_flow_count = 0
            
        # 2. 检查流控规则
        if self.order_flow_count >= self.order_flow_limit:
            self.trading_engine.write_log("风控拦截：超过每秒最大报单限制！")
            return False
            
        # 3. 检查单合约撤单次数
        cancel_c = self.cancel_count.get(order_req.vt_symbol, 0)
        if cancel_c >= self.cancel_limit:
            self.trading_engine.write_log(f"风控拦截：{order_req.vt_symbol} 超过每日最大撤单次数限制！")
            return False
            
        # 4. 检查总成交笔数
        if self.trade_count >= self.trade_limit:
            self.trading_engine.write_log("风控拦截：超过每日最大成交笔数限制！")
            return False
            
        # 通过验证，流控计数+1
        self.order_flow_count += 1
        return True

        
    def on_trade(self, trade: TradeData):
        """记录成交更新"""
        self.trade_count += 1
        
    def on_cancel(self, order: OrderData):
        """记录撤单更新"""
        vt_symbol = order.vt_symbol
        self.cancel_count[vt_symbol] = self.cancel_count.get(vt_symbol, 0) + 1
        
    def reset_flow_count(self):
        """通常由定时器每秒调用一次重置"""
        self.order_flow_count = 0
