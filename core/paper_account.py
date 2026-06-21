from typing import Dict
from core.event_engine import EventEngine, Event
from core.models import OrderData, TradeData, TickData, Status, Direction, Offset

class PaperAccount:
    """本地仿真账户模块，订阅 ORDER 并根据 TICK 模拟撮合成交"""
    def __init__(self, event_engine: EventEngine):
        self.event_engine = event_engine
        
        self.active_orders: Dict[str, OrderData] = {}
        self.ticks: Dict[str, TickData] = {}
        
        self.trade_count = 0
        
        # 订阅事件
        self.event_engine.register("eTick.", self.process_tick_event)
        self.event_engine.register("eOrder.", self.process_order_event)

    def process_tick_event(self, event: Event):
        """收到最新 Tick，更新本地缓存并检查是否能撮合活跃订单"""
        tick: TickData = event.data
        self.ticks[tick.vt_symbol] = tick
        
        # 交叉撮合
        self.cross_orders(tick)
        
    def process_order_event(self, event: Event):
        """收到策略发出的订单，将其加入活跃队列"""
        order: OrderData = event.data
        if order.status == Status.SUBMITTING:
            order.status = Status.NOTTRADED
            self.active_orders[order.vt_orderid] = order
            # 推送订单状态更新事件
            self.event_engine.put(Event("eOrderUpdate.", order))

    def cross_orders(self, tick: TickData):
        """基于最新盘口简单撮合（达到盘口价即算全部成交）"""
        completed_order_ids = []
        for orderid, order in self.active_orders.items():
            if order.vt_symbol != tick.vt_symbol:
                continue
                
            is_traded = False
            trade_price = 0.0
            
            if order.direction == Direction.LONG:
                # 买单，必须 >= 卖一价才能成交
                if order.price >= tick.ask_price_1 and tick.ask_price_1 > 0:
                    is_traded = True
                    trade_price = tick.ask_price_1
            else:
                # 卖单，必须 <= 买一价才能成交
                if order.price <= tick.bid_price_1 and tick.bid_price_1 > 0:
                    is_traded = True
                    trade_price = tick.bid_price_1
                    
            if is_traded:
                order.traded = order.volume
                order.status = Status.ALLTRADED
                completed_order_ids.append(orderid)
                
                self.trade_count += 1
                
                trade = TradeData(
                    symbol=order.symbol,
                    exchange=order.exchange,
                    orderid=order.orderid,
                    tradeid=str(self.trade_count),
                    direction=order.direction,
                    offset=order.offset,
                    price=trade_price,
                    volume=order.volume,
                    datetime=tick.datetime
                )
                
                self.event_engine.put(Event("eTrade.", trade))
                self.event_engine.put(Event("eOrderUpdate.", order))

        # 移除已完成的订单
        for oid in completed_order_ids:
            self.active_orders.pop(oid)
