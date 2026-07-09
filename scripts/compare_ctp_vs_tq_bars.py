#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CTP Tick → Bar 与天勤 Bar 对比验证脚本

功能：
1. 从 CTP 订阅实时 Tick，用 BarGenerator 合成 1m Bar
2. 同步从天勤获取相同时间段的 1m Bar
3. 对比两路数据的 OHLCV 差异

运行时间要求：在夜盘交易时段内运行（21:00-22:55）
"""

import os, sys, time, asyncio, threading
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv()

# 强制使用 7x24 SimNow 环境（夜盘可用）
os.environ.setdefault('SIMNOW_TRADE_FRONT', 'tcp://182.254.243.31:40001')
os.environ.setdefault('SIMNOW_MD_FRONT',   'tcp://182.254.243.31:40011')

from tqsdk import TqApi, TqAuth
from core.event_engine import EventEngine, Event
from gateway.ctp_gateway import CtpGateway
from strategy.bar_generator import BarGenerator
from core.models import TickData

# ─── 参数配置 ───────────────────────────────────────────────────
TQ_SYMBOL  = "KQ.m@SHFE.rb"   # 天勤主力连续
CTP_SYMBOL = "rb2610"          # CTP 合约（需与天勤主力对应，可按实际修改）
EXCHANGE   = "SHF"
COLLECT_MINUTES = 3            # 收集分钟数，至少等待完整一根 Bar 闭合
# ────────────────────────────────────────────────────────────────

ctp_bars   = []   # CTP 合成的 Bar 列表
tq_bars    = {}   # 天勤 Bar 字典  {HH:MM -> row}
tick_count = 0

def on_ctp_bar(bar):
    ctp_bars.append(bar)
    print(f"  📊 [CTP Bar闭合] {bar.datetime.strftime('%H:%M')} | "
          f"O:{bar.open_price:.0f} H:{bar.high_price:.0f} "
          f"L:{bar.low_price:.0f} C:{bar.close_price:.0f} "
          f"Vol:{bar.volume:.0f}")


def run_ctp(loop, ready_event):
    """在独立线程中运行 CTP 行情（CTP 回调是同步多线程）"""
    global tick_count

    async def _main():
        engine = EventEngine()
        engine.start()
        bg = BarGenerator(on_bar=on_ctp_bar)

        def on_tick(event):
            global tick_count
            tick: TickData = event.data
            tick_count += 1
            bg.update_tick(tick)

        engine.register("eTick.", on_tick)
        gw = CtpGateway(engine)
        gw.connect()

        # 等待登录完成（最多 8 秒）
        for _ in range(40):
            await asyncio.sleep(0.2)
            if gw.md_logged_in:
                break

        if not gw.md_logged_in:
            print("❌ CTP 行情登录失败，退出")
            ready_event.set()
            return

        # 动态解析当前主力合约
        main_contract = CTP_SYMBOL
        gw.subscribe(main_contract, EXCHANGE)
        print(f"✅ CTP 已订阅 {main_contract}.{EXCHANGE}，开始收集 Tick...")
        ready_event.set()

        # 等待收集指定分钟数
        await asyncio.sleep(COLLECT_MINUTES * 60 + 5)

        # 强制推送最后一根未闭合的 Bar
        if bg.bar:
            ctp_bars.append(bg.bar)
            print(f"  📊 [CTP 末尾Bar] {bg.bar.datetime.strftime('%H:%M')} | "
                  f"O:{bg.bar.open_price:.0f} C:{bg.bar.close_price:.0f}")

        gw.close()
        await engine.stop()

    asyncio.run(_main())


def run_tq(start_dt: datetime):
    """从天勤拉取对应时间段的 1m Bar"""
    tq_username = os.getenv("TQ_USERNAME", "")
    tq_password = os.getenv("TQ_PASSWORD", "")
    api = TqApi(auth=TqAuth(tq_username, tq_password))

    # 解析主力合约
    quote = api.get_quote(TQ_SYMBOL)
    while not quote.underlying_symbol:
        api.wait_update()
    main_symbol = quote.underlying_symbol  # e.g. SHFE.rb2610
    print(f"🎯 天勤主力合约: {main_symbol}")

    # 拉取最近 10 根 1m K线
    klines = api.get_kline_serial(main_symbol, 60, data_length=10)
    api.wait_update()

    for i in range(len(klines) - 1, max(len(klines) - 1 - COLLECT_MINUTES - 2, -1), -1):
        row = klines.iloc[i]
        import pandas as pd
        dt = (pd.to_datetime(row['datetime']) +
              pd.Timedelta(hours=8) + pd.Timedelta(minutes=1))
        key = dt.strftime('%H:%M')
        tq_bars[key] = row
        print(f"  📈 [TQ Bar] {key} | "
              f"O:{row['open']:.0f} H:{row['high']:.0f} "
              f"L:{row['low']:.0f} C:{row['close']:.0f} "
              f"Vol:{row['volume']:.0f}")

    api.close()


def compare():
    """打印对比表格"""
    print()
    # 7x24 环境检测
    md_front = os.environ.get('SIMNOW_MD_FRONT', '')
    if '182.254.243.31' in md_front:
        print("⚠️  [注意] 当前使用的是 7x24 测试环境（182.254.243.31）。")
        print("    该环境推送延迟/回放数据，价格与时间均与实时市场不符。")
        print("    如需验证 CTP Bar 与天勤完全一致，请在第一套环境（180.168.146.187）")
        print("    的交易时段（09:00-15:30 或 21:00-23:00）内重新运行本脚本。")
        print()

    print("="*72)
    print(f"  {'时间':^6}  {'来源':^6}  {'开盘':>8}  {'最高':>8}  {'最低':>8}  {'收盘':>8}  {'成交量':>8}")
    print("-"*72)

    # CTP Bar 使用分钟开始时间；TQ Bar 经+1min变换为分钟结束时间
    # 对齐规则：CTP_bar.datetime + 1min = TQ_bar.key
    from datetime import timedelta
    all_keys = sorted(set(
        [(b.datetime + timedelta(minutes=1)).strftime('%H:%M') for b in ctp_bars]
        + list(tq_bars.keys())
    ))

    for key in all_keys:
        ctp_bar = next(
            (b for b in ctp_bars if (b.datetime + timedelta(minutes=1)).strftime('%H:%M') == key),
            None
        )
        tq_row = tq_bars.get(key)

        if ctp_bar:
            print(f"  {key}    CTP  {ctp_bar.open_price:>8.0f}  {ctp_bar.high_price:>8.0f}  "
                  f"{ctp_bar.low_price:>8.0f}  {ctp_bar.close_price:>8.0f}  {ctp_bar.volume:>8.0f}")
        if tq_row is not None:
            print(f"  {key}    TQ   {tq_row['open']:>8.0f}  {tq_row['high']:>8.0f}  "
                  f"{tq_row['low']:>8.0f}  {tq_row['close']:>8.0f}  {tq_row['volume']:>8.0f}")

        if ctp_bar and tq_row is not None:
            diff_c = abs(ctp_bar.close_price - tq_row['close'])
            diff_v = abs(ctp_bar.volume - tq_row['volume'])
            match = "✅ 吻合" if diff_c < 2 else "⚠️  偏差"
            print(f"  {key}    DIFF  收盘价差:{diff_c:.1f}  成交量差:{diff_v:.0f}  {match}")
        print()

    print("="*72)
    print(f"CTP 共收到 Tick: {tick_count} 笔  |  合成 Bar: {len(ctp_bars)} 根")
    print(f"天勤拉取 Bar:    {len(tq_bars)} 根")



if __name__ == "__main__":
    print("="*50)
    print("CTP Tick→Bar vs 天勤 Bar 对比验证")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"预计收集 {COLLECT_MINUTES} 分钟数据...")
    print("="*50)

    ready = threading.Event()
    ctp_thread = threading.Thread(target=run_ctp, args=(None, ready), daemon=True)
    ctp_thread.start()

    ready.wait(timeout=15)
    if not ready.is_set():
        print("❌ CTP 启动超时")
        sys.exit(1)

    # CTP 收集结束后再拉天勤（确保时间段对齐）
    ctp_thread.join()

    print("\n🔄 正在从天勤拉取对应历史 Bar 进行比对...")
    run_tq(datetime.now())

    compare()
