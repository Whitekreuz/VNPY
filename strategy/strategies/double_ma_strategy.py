from core.models import BarData
from strategy.template import CtaTemplate
from strategy.bar_generator import BarGenerator

class DoubleMaStrategy(CtaTemplate):
    """
    双均线交叉策略（用于功能验证）
    """
    author = "Antigravity"
    
    # 策略参数
    fast_window = 10
    slow_window = 20
    
    parameters = ["fast_window", "slow_window"]
    
    # 策略变量
    fast_ma0 = 0.0
    fast_ma1 = 0.0
    slow_ma0 = 0.0
    slow_ma1 = 0.0
    
    variables = ["fast_ma0", "fast_ma1", "slow_ma0", "slow_ma1"]
    
    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.close_array = []
        self.pos = 0 # 当前持仓
        self.history_bars = []  # 保存合成后的 60m K 线历史以供绘图分析
        
        # 核心：使用 K 线合成引擎将 1m 转化为 60m (1小时)
        self.bg = BarGenerator(
            on_bar=self.on_1m_bar, 
            window=60, 
            on_window_bar=self.on_60m_bar
        )

        
    def on_init(self):
        self.write_log("策略初始化")
        
    def on_start(self):
        self.write_log("策略启动")
        
    def on_stop(self):
        self.write_log("策略停止")
        
    def on_bar(self, bar: BarData):
        """回测引擎推送 1m K线到这里"""
        # 喂给合成器
        self.bg.update_bar(bar)
        
    def on_1m_bar(self, bar: BarData):
        """1分钟线生成回调，这里不需要处理因为我们打1小时线"""
        pass
        
    def on_60m_bar(self, bar: BarData):
        """60分钟(1小时) K线生成回调，在此执行主要策略逻辑"""
        self.history_bars.append(bar)
        self.close_array.append(bar.close_price)

        
        # 缓存长度控制
        if len(self.close_array) > self.slow_window + 1:
            self.close_array.pop(0)
            
        # 等待缓存满
        if len(self.close_array) <= self.slow_window:
            return
            
        # 计算上一根K线的均线和当前K线的均线，用来判断交叉
        # fast_ma0 为最新，fast_ma1 为上一根
        self.fast_ma0 = sum(self.close_array[-self.fast_window:]) / self.fast_window
        self.fast_ma1 = sum(self.close_array[-self.fast_window-1:-1]) / self.fast_window
        
        self.slow_ma0 = sum(self.close_array[-self.slow_window:]) / self.slow_window
        self.slow_ma1 = sum(self.close_array[-self.slow_window-1:-1]) / self.slow_window
        
        # 判断金叉死叉
        cross_over = self.fast_ma0 > self.slow_ma0 and self.fast_ma1 <= self.slow_ma1
        cross_below = self.fast_ma0 < self.slow_ma0 and self.fast_ma1 >= self.slow_ma1
        
        # 交易逻辑
        if cross_over:
            if self.pos == 0:
                self.buy(bar.close_price, 1)
            elif self.pos < 0:
                self.cover(bar.close_price, 1)
                self.buy(bar.close_price, 1)
                
        elif cross_below:
            if self.pos == 0:
                self.short(bar.close_price, 1)
            elif self.pos > 0:
                self.sell(bar.close_price, 1)
                self.short(bar.close_price, 1)
                
    def on_trade(self, trade):
        # 根据成交回报更新持仓
        if trade.direction.value == "多" and trade.offset.value == "开":
            self.pos += trade.volume
        elif trade.direction.value == "空" and trade.offset.value == "平":
            self.pos -= trade.volume
        elif trade.direction.value == "空" and trade.offset.value == "开":
            self.pos -= trade.volume
        elif trade.direction.value == "多" and trade.offset.value == "平":
            self.pos += trade.volume
            
        self.write_log(f"成交回报: {trade.direction.value} {trade.offset.value} {trade.volume}手 @ {trade.price}。当前持仓：{self.pos}")
