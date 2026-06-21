from core.event_engine import EventEngine

class TradingEngine:
    """主交易引擎，负责统筹底层的事件引擎、各个 Gateway 网关及上层 App"""
    def __init__(self):
        self.event_engine = EventEngine()
        self.gateways = {}
        self.apps = {}
        
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
