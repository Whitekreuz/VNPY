# -*- coding: utf-8 -*-
import os
import sys
import time
import json
import asyncio
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv

# Ensure stdout uses UTF-8 and line buffering
sys.stdout.reconfigure(line_buffering=True, encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.trading_engine import TradingEngine, Event
from core.models import TickData, BarData, Direction, Offset, OrderData, Status
from gateway.ctp_gateway import CtpGateway
from strategy.strategies.double_ma_strategy import DoubleMaStrategy
from tqsdk import TqApi, TqAuth

class LiveCtaEngine:
    """
    轻量实盘/仿真策略运行引擎
    负责双热路切换、策略生命周期管理、时区校准与报单信号拦截。
    """
    def __init__(self, main_engine: TradingEngine, db_manager=None):
        self.main_engine = main_engine
        self.event_engine = main_engine.event_engine
        self.db_manager = db_manager
        
        self.strategies = {}
        self.active_contracts = {}      # vt_symbol -> main_contract_code (如 RB88 -> rb2610)
        self.reverse_contract_map = {}   # ctp_code -> vt_symbol (如 rb2610 -> RB88)
        
        # 行情监控
        self.last_tick_time = time.time()
        self.use_backup_source = False
        self.volume_multiples = {}  # vt_symbol -> 合约乘数 (如 RB88 -> 10)
        
        # 注册事件监听
        self.event_engine.register("eTick.", self.process_tick)

    def add_strategy(self, strategy_class, strategy_name: str, vt_symbol: str, setting: dict):
        """添加并实例化策略"""
        strategy = strategy_class(self, strategy_name, vt_symbol, setting)
        self.strategies[strategy_name] = strategy
        print(f"✅ 载入实盘策略: {strategy_name} | 监控品种: {vt_symbol}")
        return strategy

    def send_order(self, strategy, direction: Direction, offset: Offset, price: float, volume: float, stop: bool = False):
        """策略发送委托请求（转发给主引擎以支持 Dry-Run 拦截）"""
        symbol, exchange = strategy.vt_symbol.split('.')
        # 创建标准订单请求
        req = OrderData(
            symbol=symbol,
            exchange=exchange,
            orderid=f"live_{int(time.time() * 1000)}",
            type="LIMIT",
            direction=direction,
            offset=offset,
            price=price,
            volume=volume,
            status=Status.SUBMITTING,
            datetime=datetime.now()
        )
        return self.main_engine.send_order(req, gateway_name="CTP")

    def process_tick(self, event: Event):
        """处理底层 Gateway 派发的 TickData"""
        tick: TickData = event.data
        
        # 检查是否为我们监控的实际主力合约的 Tick 行情
        vt_symbol = self.reverse_contract_map.get(tick.symbol.lower())
        if not vt_symbol:
            return
            
        # 更新 CTP 活跃心跳时间
        self.last_tick_time = time.time()
        
        # 如果当前正处于天勤备份模式，且 CTP 恢复了，自动切回 CTP
        if self.use_backup_source:
            print(f"📡 [双路灾备] 检测到 CTP MD 行情已恢复，正在切回主源 (CTP)...")
            self.use_backup_source = False
            
        # 将 Tick 的 symbol 重命名为连续合约符号 (例如 rb2610 -> RB88)，以保证策略和 K 线聚合器指标计算无偏差
        tick.symbol = vt_symbol.split('.')[0]
        
        # 喂给绑定了该合约的策略
        for strategy in self.strategies.values():
            if strategy.vt_symbol == vt_symbol:
                # 使用策略的 K 线聚合器合成 live K 线
                strategy.bg.update_tick(tick)

    def write_log(self, msg: str, strategy=None):
        """记录日志"""
        prefix = f"[{strategy.strategy_name}]" if strategy else "[系统]"
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {prefix} {msg}")


async def failover_monitor(cta_engine: LiveCtaEngine, tq_api: TqApi, tq_klines_dict: dict):
    """
    后台守护任务：监测 CTP 主路行情是否中断。
    如果中断（超过 15 秒无 Tick 推送），自动启动天勤（TqSdk）备源拉取 1m K线闭合以维持策略运转。
    """
    print("🚦 [灾备监控] 双热路灾备监控协程已启动...")
    while True:
        await asyncio.sleep(2)
        
        # 判断当前是否为交易时间段（排除周六、周日以及非交易时段）
        now = datetime.now()
        is_trading_hour = False
        
        # 周一至周五且在主力行情交易时段内
        if now.weekday() < 5:
            hour = now.hour
            minute = now.minute
            if (9 <= hour < 11) or (11 == hour and minute <= 30) or (13 <= hour < 15) or (21 <= hour < 23):
                is_trading_hour = True
            
        # 仅在交易时间内进行无 Tick 丢单检测
        if is_trading_hour and (time.time() - cta_engine.last_tick_time > 15):
            if not cta_engine.use_backup_source:
                print(f"🚨 [灾备警报] CTP 行情中断超过 15 秒！正在紧急降级启动天勤 (TqSdk) 备份源...")
                cta_engine.use_backup_source = True
            
            # 使用天勤数据驱动策略
            tq_api.wait_update(deadline=time.time() + 0.1)
            for vt_symbol, tq_klines in tq_klines_dict.items():
                if tq_api.is_changing(tq_klines.iloc[-1], "datetime"):
                    # 抓取刚刚闭合的 1m K线
                    closed_row = tq_klines.iloc[-2]
                    
                    symbol, exchange = vt_symbol.split('.')
                    
                    # 获取该合约动态乘数
                    multiplier = cta_engine.volume_multiples.get(vt_symbol, 10)
                    
                    # 组装 BarData 并加 8 小时和 1 分钟对齐
                    dt = pd.to_datetime(closed_row['datetime']) + pd.Timedelta(hours=8) + pd.Timedelta(minutes=1)
                    
                    bar = BarData(
                        symbol=symbol,
                        exchange=exchange,
                        datetime=dt.to_pydatetime(),
                        interval="1m",
                        volume=closed_row['volume'],
                        turnover=closed_row['volume'] * closed_row['close'] * multiplier,
                        open_interest=closed_row.get('close_oi', 0.0),
                        open_price=closed_row['open'],
                        high_price=closed_row['high'],
                        low_price=closed_row['low'],
                        close_price=closed_row['close']
                    )
                    
                    # 将备用 K 线输入策略
                    print(f"📡 [双路灾备] 使用天勤备源推送新闭合 K线: {bar.datetime.strftime('%H:%M:%S')} Close: {bar.close_price}")
                    for strategy in cta_engine.strategies.values():
                        if strategy.vt_symbol == vt_symbol:
                            strategy.on_bar(bar)


def prewarm_strategy_with_tq(tq_api: TqApi, strategy, tq_symbol: str):
    """
    使用天勤历史 1m 数据对策略的双均线进行启动前冷热数据预热
    下载最近 1500 根 1m K线并以 Bar 事件逐根推送，瞬间算满 Moving Average
    """
    print(f"🔥 [系统预热] 正在从天勤下载 {tq_symbol} 最近 1500 根 1m K线预热策略指标...")
    klines = tq_api.get_kline_serial(tq_symbol, 60, data_length=1500)
    tq_api.wait_update(deadline=time.time() + 5)
    
    if klines is not None and len(klines) > 0:
        # 添加时区校准
        klines['db_datetime'] = pd.to_datetime(klines['datetime']) + pd.Timedelta(hours=8) + pd.Timedelta(minutes=1)
        
        symbol, exchange = strategy.vt_symbol.split('.')
        prewarm_bars = []
        
        for _, row in klines.iterrows():
            bar = BarData(
                symbol=symbol,
                exchange=exchange,
                datetime=row['db_datetime'].to_pydatetime(),
                interval="1m",
                volume=row['volume'],
                turnover=row['volume'] * row['close'] * 10,
                open_interest=row.get('close_oi', 0.0),
                open_price=row['open'],
                high_price=row['high'],
                low_price=row['low'],
                close_price=row['close']
            )
            prewarm_bars.append(bar)
            
        print(f"🔥 [系统预热] 正在喂入 {len(prewarm_bars)} 根历史 K线以构建均线底座...")
        for bar in prewarm_bars:
            # 喂给策略以激活 MA 数组缓存
            strategy.on_bar(bar)
            
        # 预热完毕后打印当前指标状态
        print(f"🔥 [系统预热] 策略预热完毕！"
              f"当前快轨 MA0: {strategy.fast_ma0:.2f} | 慢轨 MA0: {strategy.slow_ma0:.2f} | "
              f"持仓状态pos: {strategy.pos}")


async def main():
    load_dotenv()
    
    # 账户配置读取
    tq_username = os.environ.get("TQ_USERNAME")
    tq_password = os.environ.get("TQ_PASSWORD")
    
    simnow_investor = os.environ.get("SIMNOW_INVESTOR_ID")
    simnow_password = os.environ.get("SIMNOW_PASSWORD")
    
    if not tq_username or not tq_password:
        print("❌ 未在 .env 中检测到 TqSdk 账号或密码！")
        return
        
    print("==================================================")
    print("🤖 启动 Unified Daemon Engine (常驻守护进程)")
    print(f"北京时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("==================================================")

    # 1. 实例化主引擎与对齐引擎
    main_engine = TradingEngine()
    
    # 强制将主引擎设置为预警 Dry-Run 模式 (不真下单，仅输出并写入 trading_signals.log)
    main_engine.dry_run = True
    
    # 载入并实例化 CTP 仿真网关
    main_engine.add_gateway(CtpGateway, "CTP")
    
    cta_engine = LiveCtaEngine(main_engine)
    
    # 2. 建立天勤连接并解析主力合约
    print("🔑 正在连接天勤 API 并解析映射...")
    tq_api = TqApi(auth=TqAuth(tq_username, tq_password))
    
    # 我们要运行的策略监控品种为螺纹钢指数/主力连续 (RB88)
    vt_symbol = "RB88.SHF"
    
    # 动态利用天勤解析主力合约的具体代码 (例如 RB88 -> SHFE.rb2610)
    quote_sample = tq_api.get_quote("KQ.m@SHFE.rb")
    tq_api.wait_update(deadline=time.time() + 5)
    
    main_contract = quote_sample.underlying_symbol  # 例如 "SHFE.rb2610"
    print(f"🎯 映射对齐成功: {vt_symbol} -> 当前实际主力合约为: {main_contract}")
    
    # 绑定双向映射缓存与合约乘数
    clean_main_code = main_contract.split('.')[1] # e.g. rb2610
    cta_engine.active_contracts[vt_symbol] = clean_main_code
    cta_engine.reverse_contract_map[clean_main_code] = vt_symbol
    cta_engine.volume_multiples[vt_symbol] = quote_sample.volume_multiple
    print(f"💰 合约乘数加载成功: {vt_symbol} -> {quote_sample.volume_multiple}")

    # 3. 实例化策略
    strategy_name = "DoubleMa_Live"
    setting = {"fast_window": 10, "slow_window": 20}
    strategy = cta_engine.add_strategy(DoubleMaStrategy, strategy_name, vt_symbol, setting)

    # 4. 执行数据预热 (用天勤拉 1500 根 1m K线)
    prewarm_strategy_with_tq(tq_api, strategy, "KQ.m@SHFE.rb")

    # 5. 订阅天勤实时行情流（用作备用通道）
    tq_klines_dict = {
        vt_symbol: tq_api.get_kline_serial("KQ.m@SHFE.rb", 60)
    }

    # 6. 启动主引擎事件循环
    main_engine.start()

    # 7. 连接 CTP 仿真前置机并订阅主力合约行情
    print("🔑 正在连接 CTP 仿真柜台 (SimNow)...")
    ctp_gateway = main_engine.gateways.get("CTP")
    if ctp_gateway and simnow_investor and simnow_password:
        ctp_gateway.connect()
        # 订阅 CTP 上对应的实际主力合约代码行情
        ctp_gateway.subscribe(clean_main_code, "SHF")
    else:
        print("⚠️ 未检测到 SimNow 账户配置，无法接入 CTP 主路，降级为天勤单路运行。")
        cta_engine.use_backup_source = True

    # 8. 挂载灾备监控后台协程
    failover_task = asyncio.create_task(failover_monitor(cta_engine, tq_api, tq_klines_dict))

    # 守护主循环
    try:
        print("\n🚀 系统已常驻启动并进入监听状态，预警信号将直接拦截并记入 logs/trading_signals.log。")
        print("按 Ctrl+C 安全停止程序...\n")
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        print("\n🔌 正在安全关闭主引擎...")
    finally:
        # 释放资源
        failover_task.cancel()
        if ctp_gateway:
            ctp_gateway.close()
        await main_engine.stop()
        tq_api.close()
        print("✅ 常驻进程安全退出。")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
