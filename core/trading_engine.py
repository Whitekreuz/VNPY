import os
from datetime import datetime
from core.event_engine import EventEngine, Event

class TradingEngine:
    """主交易引擎，负责统筹底层的事件引擎、各个 Gateway 网关及上层 App"""
    def __init__(self):
        self.event_engine = EventEngine()
        self.gateways = {}
        self.apps = {}
        self.dry_run = True  # 默认开启预警拦截模式 (Dry-Run)
        
    def start(self):
        """启动整个交易系统"""
        print("启动事件引擎...")
        self.event_engine.start()
        print("交易系统主引擎启动完毕")
        
    async def stop(self):
        """安全停止系统"""
        print("停止事件引擎...")
        await self.event_engine.stop()
        print("交易系统主引擎已安全停止")

    def send_order(self, req, gateway_name: str = "CTP") -> str:
        """投递交易报单。若处于 dry_run 模式，则强力拦截并只输出警报日志"""
        if self.dry_run:
            print("\n" + "="*50)
            print(f"⚠️  [DRY-RUN 信号拦截] 合约: {req.symbol}.{req.exchange} | "
                  f"方向: {req.direction.value} | 偏移: {req.offset.value} | "
                  f"价格: {req.price} | 数量: {req.volume}")
            print("="*50 + "\n")
            
            # 记录交易信号日志
            log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, 'trading_signals.log')
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] DRY-RUN SIGNAL - "
                        f"合约: {req.symbol}.{req.exchange} | 方向: {req.direction.value} | "
                        f"价格: {req.price} | 数量: {req.volume}\n")
            return "DRY_RUN_ORDER_ID"
            
        # 非 dry_run 模式下分发至底层网关
        gateway = self.gateways.get(gateway_name)
        if gateway:
            # 仿真状态下可以投递至柜台或者本地
            return getattr(gateway, 'send_order', lambda x: "")(req)
        return ""

    def add_gateway(self, gateway_class, gateway_name: str = ""):
        """添加并初始化底层网关接口"""
        gateway = gateway_class(self.event_engine)
        name = gateway_name if gateway_name else getattr(gateway, 'gateway_name', gateway_class.__name__)
        self.gateways[name] = gateway
        print(f"载入网关: {name}")

    def add_app(self, app_class):
        """添加上层应用模块 (如 CTA策略引擎，数据记录器等)"""
        app = app_class(self, self.event_engine)
        self.apps[app.app_name] = app
        print(f"载入应用模块: {app.app_name}")
