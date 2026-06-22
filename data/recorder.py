from core.event_engine import EventEngine, Event
from core.models import BarData
from data.db_manager import DBManager

class DataRecorder:
    """实时数据落盘记录器：订阅事件总线中的实时 K线，定期批量入库"""
    def __init__(self, event_engine: EventEngine, db_manager: DBManager):
        self.event_engine = event_engine
        self.db_manager = db_manager
        self.app_name = "DataRecorder"
        
        self.bar_buffer = []
        
        # 订阅系统中产生的 Bar 事件
        self.event_engine.register("eBar.", self.process_bar_event)
        
    def process_bar_event(self, event: Event):
        bar: BarData = event.data
        self.bar_buffer.append(bar)
        
        # 缓存满 10 根写入一次，减少数据库 I/O 压力
        if len(self.bar_buffer) >= 10:
            self.db_manager.save_bar_data(self.bar_buffer)
            self.bar_buffer.clear()
            
    def force_flush(self):
        """强制清空缓存并写入"""
        if self.bar_buffer:
            self.db_manager.save_bar_data(self.bar_buffer)
            self.bar_buffer.clear()
