# -*- coding: utf-8 -*-
import os
import sys
import io
import json
import time
from datetime import datetime, timedelta
import argparse
import pandas as pd
from dotenv import load_dotenv

# Reconfigure stdout to use UTF-8 and line buffering
sys.stdout.reconfigure(line_buffering=True, encoding='utf-8')
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.db_manager import DBManager
from core.models import BarData
from tqsdk import TqApi, TqAuth

def get_tq_exchange(vn_exchange: str) -> str:
    """将 VN.py 交易所代码映射为 TqSdk 交易所代码"""
    mapping = {
        "SHF": "SHFE",
        "DCE": "DCE",
        "CZC": "CZCE",
        "CFE": "CFFEX",
        "GFE": "GFEX"
    }
    return mapping.get(vn_exchange.upper(), vn_exchange.upper())

def resolve_secondary_dominant(api: TqApi, exchange: str, symbol: str) -> str:
    """动态解析当前品种的次主力合约代码 (成交量/持仓量第二大的活跃合约)"""
    try:
        # 获取所有未到期的活跃合约列表
        conts = api.query_quotes(ins_class="FUTURE", exchange_id=exchange, product_id=symbol, expired=False)
        if not conts or len(conts) < 2:
            return None
        
        # 获取各合约的行情快照以对比持仓量
        quotes = {}
        for c in conts:
            quotes[c] = api.get_quote(c)
            
        # 驱动一次更新事件同步行情
        api.wait_update(deadline=time.time() + 2)
        
        # 按持仓量 (open_interest) 降序排列
        valid_quotes = []
        for c, q in quotes.items():
            oi = getattr(q, 'open_interest', 0)
            if oi is not None and not pd.isna(oi):
                valid_quotes.append((c, oi))
                
        valid_quotes.sort(key=lambda x: x[1], reverse=True)
        
        # 返回持仓量第二大的合约代码作为次主力
        if len(valid_quotes) >= 2:
            return valid_quotes[1][0]
    except Exception as e:
        print(f"      ⚠️ 解析次主力合约失败 ({symbol}): {e}")
    return None

def download_tq_data():
    parser = argparse.ArgumentParser(description="TqSdk 期货历史 1min K线增量维护脚本")
    parser.add_argument('--category', type=str, default=None, help="只拉取指定板块 (例如: oils_and_oilseeds)")
    parser.add_argument('--exchange', type=str, default=None, help="只拉取指定交易所 (例如: DCE)")
    args = parser.parse_args()

    load_dotenv()
    
    # 1. 初始化账号信息与数据库连接
    tq_username = os.environ.get("TQ_USERNAME")
    tq_password = os.environ.get("TQ_PASSWORD")
    
    db_name = os.getenv("PG_DBNAME_PROD", "quant_db_prod")
    db_user = os.getenv("PG_USER", "postgres")
    db_pass = os.getenv("PG_PASSWORD", "")
    db_host = os.getenv("PG_HOST", "localhost")
    db_port = os.getenv("PG_PORT", "5432")
    
    if not tq_username or not tq_password:
        print("❌ 未在 .env 文件中找到 TQ_USERNAME 和 TQ_PASSWORD！")
        return
        
    print("==================================================")
    print(f"🚀 初始化 TqSdk 数据扫盘任务 (支持单合约 & 连续/指数)")
    print(f"📦 目标生产数据库: {db_name}@{db_host}")
    print("==================================================")
    
    try:
        db = DBManager(dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port)
        print("✅ 本地数据库连接成功！")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return

    # 2. 启动天勤 API
    print("🔑 正在建立天勤 API 连接...")
    api = TqApi(auth=TqAuth(tq_username, tq_password))
    print("✅ 天勤 API 连接成功！")

    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'futures_symbols.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    start_year = 2018
    end_year = 2026
    continuous_start = datetime(2018, 1, 1)
    
    interval = "1m"
    total_contracts = 0

    try:
        for category, cat_data in config.items():
            if args.category and category != args.category:
                continue
                
            print(f"\n📂 处理板块: {category} - {cat_data.get('description', '')}")
            
            for symbol_raw, sym_info in cat_data['symbols'].items():
                base_sym, exchange = symbol_raw.split('.')
                if args.exchange and exchange.upper() != args.exchange.upper():
                    continue

                tq_exchange = get_tq_exchange(exchange)
                months = sym_info['months']
                name = sym_info['name']
                continuous_suffixes = sym_info.get('continuous', [])
                
                print(f"\n✨ 开始拉取品种: [{name}] {symbol_raw}")
                
                # 获取该品种合约乘数，用于估算成交额 (turnover)
                quote_sample = api.get_quote(f"KQ.m@{tq_exchange}.{base_sym}")
                api.wait_update(deadline=time.time() + 2)
                volume_multiple = getattr(quote_sample, 'volume_multiple', 10)
                if not volume_multiple:
                    volume_multiple = 10
                
                # --- 1. 下载连续合约 (88/888/99) ---
                if continuous_suffixes:
                    print(f"    📥 [连续合约] 检测到需要拉取连续属性: {continuous_suffixes}")
                    for suffix in continuous_suffixes:
                        tq_symbol = None
                        db_symbol = None
                        
                        if suffix == "88":
                            tq_symbol = f"KQ.m@{tq_exchange}.{base_sym}"
                            db_symbol = f"{base_sym.upper()}88"
                        elif suffix == "888":
                            tq_symbol = f"KQ.i@{tq_exchange}.{base_sym}"
                            db_symbol = f"{base_sym.upper()}888"
                        elif suffix == "99":
                            # 动态获取次主力合约代码
                            resolved_code = resolve_secondary_dominant(api, tq_exchange, base_sym)
                            if resolved_code:
                                tq_symbol = resolved_code
                                db_symbol = f"{base_sym.upper()}99"
                                print(f"      🎯 动态解析 {base_sym.upper()}99 指向实际合约: {resolved_code}")
                            else:
                                print(f"      ⏭️ 未找到合适的次主力合约，跳过 {base_sym.upper()}99")
                                continue
                        
                        if not tq_symbol:
                            continue
                            
                        # 获取库中最大时间作为断点
                        max_dt = db.get_max_datetime(db_symbol, exchange, interval)
                        
                        # 确定本次拉取长度：
                        # 如果没有历史数据，免费版单次请求限制最大拉取 8000 根 (约 23 个交易日)
                        # 如果有历史数据，则拉取 1500 根（约 4 个交易日，足够补齐前日/周末数据）
                        data_length = 8000 if not max_dt else 1500
                        
                        print(f"      📥 正在拉取连续合约: {tq_symbol} (上限 {data_length} 根)...")
                        klines = api.get_kline_serial(tq_symbol, 60, data_length=data_length)
                        api.wait_update(deadline=time.time() + 5)
                        
                        if klines is not None and len(klines) > 0:
                            # TqSdk 的 datetime 列是 K 线开始时间，它表示 UTC 纳秒时间戳。
                            # 对齐到 CST (UTC+8) 需要加 8 小时，并加 1 分钟对齐到 VN.py / 米筐 的结束时间
                            klines['db_datetime'] = pd.to_datetime(klines['datetime']) + pd.Timedelta(hours=8) + pd.Timedelta(minutes=1)
                            
                            # 过滤出大于数据库最大时间的新 Bar
                            if max_dt:
                                df_new = klines[klines['db_datetime'] > pd.to_datetime(max_dt)]
                            else:
                                df_new = klines[klines['db_datetime'] >= pd.to_datetime(continuous_start)]
                                
                            if df_new.empty:
                                print(f"      ⏭️ 连续合约 {db_symbol} 已是最新，跳过...")
                                continue
                                
                            bars = []
                            for _, row in df_new.iterrows():
                                # 天勤 K线无成交额 amount 字段，通过 成交量 * 收盘价 * 合约乘数 估算
                                est_turnover = row['volume'] * row['close'] * volume_multiple
                                bar = BarData(
                                    symbol=db_symbol,
                                    exchange=exchange,
                                    datetime=row['db_datetime'].to_pydatetime(),
                                    interval=interval,
                                    volume=row['volume'],
                                    turnover=est_turnover,
                                    open_interest=row.get('close_oi', 0.0), # 用收盘持仓量填充
                                    open_price=row['open'],
                                    high_price=row['high'],
                                    low_price=row['low'],
                                    close_price=row['close']
                                )
                                bars.append(bar)
                                
                            if bars:
                                db.save_bar_data(bars)
                                print(f"        ✅ 连续合约 {db_symbol} 入库成功: 新增 {len(bars)} 根 1m K线。")
                                total_contracts += 1
                                
                # --- 2. 下载单合约历史数据 ---
                print(f"    📥 [单合约] 正在检索历史单月合约列表...")
                conts = api.query_quotes(ins_class="FUTURE", exchange_id=tq_exchange, product_id=base_sym, expired=True)
                if not conts:
                    continue
                    
                # 获取各个单月合约的静态信息
                info = api.query_symbol_info(conts)
                
                contracts_to_fetch = []
                for _, row in info.iterrows():
                    inst_id = row['instrument_id']
                    
                    # 过滤上市年份与目标月份
                    deliv_year = int(row['delivery_year'])
                    deliv_month = int(row['delivery_month'])
                    month_str = str(deliv_month).zfill(2)
                    
                    if start_year <= deliv_year <= end_year and month_str in months:
                        # 计算默认的断点（退市前1年）
                        expire_dt = datetime.fromtimestamp(row['expire_datetime'])
                        start_fetch_date = expire_dt - timedelta(days=365)
                        
                        # 格式化数据库的 symbol 代码 (例如: RB2310)
                        db_symbol = f"{base_sym.upper()}{str(deliv_year)[2:]}{month_str}"
                        
                        contracts_to_fetch.append({
                            'tq_symbol': inst_id,
                            'db_symbol': db_symbol,
                            'default_start': start_fetch_date,
                            'expire_dt': expire_dt
                        })
                        
                print(f"      🔍 筛选出符合月份规则的单月合约共 {len(contracts_to_fetch)} 个。")
                
                for item in contracts_to_fetch:
                    tq_sym = item['tq_symbol']
                    db_sym = item['db_symbol']
                    default_start = item['default_start']
                    expire_dt = item['expire_dt']
                    
                    max_dt = db.get_max_datetime(db_sym, exchange, interval)
                    
                    # 如果已经超出退市时间，且库里已有最新数据，直接跳过
                    if max_dt and max_dt >= expire_dt:
                        print(f"      ⏭️ 单合约 {db_sym} 已经过期退市并已同步完毕，跳过...")
                        continue
                        
                    fetch_start = max_dt if max_dt else default_start
                    
                    if fetch_start >= expire_dt:
                        print(f"      ⏭️ 单合约 {db_sym} 已是最新 ({fetch_start})，跳过...")
                        continue
                        
                    data_length = 8000 if not max_dt else 1500
                    print(f"      📥 正在拉取单合约: {tq_sym} -> {db_sym} ({fetch_start.strftime('%Y-%m-%d')} ~ {expire_dt.strftime('%Y-%m-%d')})...")
                    
                    klines = api.get_kline_serial(tq_sym, 60, data_length=data_length)
                    api.wait_update(deadline=time.time() + 5)
                    if klines is not None and len(klines) > 0:
                        # 对齐到 CST (UTC+8) 需要加 8 小时，并加 1 分钟对齐到 VN.py / 米筐 的结束时间
                        klines['db_datetime'] = pd.to_datetime(klines['datetime']) + pd.Timedelta(hours=8) + pd.Timedelta(minutes=1)
                        
                        # 过滤出新 Bar
                        df_new = klines[klines['db_datetime'] > pd.to_datetime(fetch_start)]
                        # 确保不超出退市时间
                        df_new = df_new[df_new['db_datetime'] <= pd.to_datetime(expire_dt)]
                        
                        if df_new.empty:
                            continue
                            
                        bars = []
                        for _, row in df_new.iterrows():
                            est_turnover = row['volume'] * row['close'] * volume_multiple
                            bar = BarData(
                                symbol=db_sym,
                                exchange=exchange,
                                datetime=row['db_datetime'].to_pydatetime(),
                                interval=interval,
                                volume=row['volume'],
                                turnover=est_turnover,
                                open_interest=row.get('close_oi', 0.0),
                                open_price=row['open'],
                                high_price=row['high'],
                                low_price=row['low'],
                                close_price=row['close']
                            )
                            bars.append(bar)
                            
                        if bars:
                            db.save_bar_data(bars)
                            print(f"        ✅ 单合约 {db_sym} 入库成功: 新增 {len(bars)} 根 1m K线。")
                            total_contracts += 1
                            
                    time.sleep(0.05)
    finally:
        print("\n🔌 正在断开天勤 API...")
        api.close()
        print("✅ 天勤 API 关闭成功。")
        
    print("==================================================")
    print(f"🏁 任务完成！本次共成功下载并导入 {total_contracts} 个合约/连续品种的数据。")
    print("==================================================")

if __name__ == "__main__":
    download_tq_data()
