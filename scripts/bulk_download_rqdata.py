import os
import sys
import io
import json
import time
import re
from datetime import datetime, timedelta
import argparse
import pandas as pd
from dotenv import load_dotenv

os.makedirs(os.path.abspath(os.path.join(os.path.dirname(__file__), '../scratch')), exist_ok=True)
class Logger:
    def __init__(self, filename):
        self.log = open(filename, 'w', encoding='utf-8')
    def write(self, message):
        self.log.write(message)
        self.log.flush()
    def flush(self):
        self.log.flush()

sys.stdout = Logger(os.path.abspath(os.path.join(os.path.dirname(__file__), '../scratch/bulk_download_rqdata.log')))
sys.stderr = sys.stdout

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data.db_manager import DBManager
from core.models import BarData

# 延时加载 rqdatac
rq = None

def get_exchange_mapping(vn_exchange: str) -> str:
    mapping = {
        "SHF": "SHFE",
        "DCE": "DCE",
        "CZC": "CZCE",
        "CFE": "CFFEX",
        "GFE": "GFEX"
    }
    return mapping.get(vn_exchange.upper(), vn_exchange.upper())

def generate_chunks(start_date, end_date, chunk_days: int = 180):
    """将总时间段按天数进行切片，防超时和限制"""
    chunks = []
    
    # 统一转换为 datetime.date 进行运算
    if isinstance(start_date, str):
        start_dt = datetime.strptime(start_date[:10], "%Y-%m-%d").date()
    elif isinstance(start_date, datetime):
        start_dt = start_date.date()
    else:
        start_dt = start_date
        
    if isinstance(end_date, str):
        end_dt = datetime.strptime(end_date[:10], "%Y-%m-%d").date()
    elif isinstance(end_date, datetime):
        end_dt = end_date.date()
    else:
        end_dt = end_date

    current_start = start_dt
    while current_start <= end_dt:
        current_end = min(current_start + timedelta(days=chunk_days), end_dt)
        chunks.append((current_start, current_end))
        current_start = current_end + timedelta(days=1)
    return chunks

def fetch_price_chunked(contract_code: str, start_date, end_date, interval: str = "1m"):
    """切片下载行情数据以确保大流量下的稳定性"""
    chunks = generate_chunks(start_date, end_date, chunk_days=180)
    all_dfs = []
    
    for chunk_start, chunk_end in chunks:
        try:
            df = rq.get_price(
                order_book_ids=contract_code,
                start_date=chunk_start,
                end_date=chunk_end,
                frequency=interval,
                fields=['open', 'high', 'low', 'close', 'volume', 'total_turnover', 'open_interest']
            )
            if df is not None and not df.empty:
                all_dfs.append(df.reset_index())
        except Exception as e:
            print(f"        ⚠️ 分片下载失败 ({chunk_start} ~ {chunk_end}): {e}")
        time.sleep(0.05) # 极短间隔
        
    if not all_dfs:
        return pd.DataFrame()
    return pd.concat(all_dfs, ignore_index=True)

def run_rq_download():
    global rq
    try:
        import rqdatac as rq
    except ImportError:
        print("❌ 未安装 rqdatac 库，请先运行: pip install rqdatac")
        return

    parser = argparse.ArgumentParser(description="RQData 期货历史数据拉取脚本")
    parser.add_argument('--category', type=str, default=None, help="只拉取指定板块 (例如: oils_and_oilseeds)")
    parser.add_argument('--exchange', type=str, default=None, help="只拉取指定交易所 (例如: DCE)")
    args = parser.parse_args()

    load_dotenv()
    
    db_name = os.getenv("PG_DBNAME_PROD", "quant_db_prod")
    db_user = os.getenv("PG_USER", "postgres")
    db_pass = os.getenv("PG_PASSWORD", "")
    db_host = os.getenv("PG_HOST", "localhost")
    db_port = os.getenv("PG_PORT", "5432")
    
    print("==================================================")
    print(f"🚀 初始化 RiceQuant 数据扫盘任务 (支持单合约 & 连续/指数)")
    print(f"📦 目标生产数据库: {db_name}@{db_host}")
    print("==================================================")
    
    try:
        db = DBManager(dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port)
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return

    rq_user = os.getenv("RQDATAC_USERNAME")
    rq_pass = os.getenv("RQDATAC_PASSWORD")
    rq_license = os.getenv("RQDATAC_LICENSE")
    
    try:
        if rq_license:
            print("🔑 检测到 RQDATAC_LICENSE，使用 uri 初始化...")
            # 构建 uri (tcp://license:<license_key>@rqdatad-pro.ricequant.com:16011)
            uri = f"tcp://license:{rq_license}@rqdatad-pro.ricequant.com:16011"
            rq.init(uri=uri)
        elif rq_user and rq_pass:
            print("👤 检测到用户名密码，使用用户名密码初始化...")
            rq.init(rq_user, rq_pass)
        else:
            print("💡 尝试读取系统默认缓存凭证初始化...")
            rq.init()
        print("✅ RiceQuant RQData 初始化成功！")
    except Exception as e:
        print(f"❌ RQData 初始化失败: {e}")
        return

    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'futures_symbols.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    print("🔍 正在从 RiceQuant 获取全量期货合约列表...")
    try:
        all_futures = rq.all_instruments(type='Future')
    except Exception as e:
        print(f"获取合约列表失败: {e}")
        return

    start_year = 2015
    end_year = datetime.now().year + 2
    # 连续合约默认下载范围（2015年至今）
    continuous_start = datetime(2015, 1, 1).date()
    continuous_end = datetime.now().date()
    
    interval = "1m"
    total_contracts = 0
    
    for category, cat_data in config.items():
        if args.category and category != args.category:
            continue
            
        print(f"\n📂 处理板块: {category} - {cat_data.get('description', '')}")
        
        for symbol_raw, sym_info in cat_data['symbols'].items():
            base_sym, exchange = symbol_raw.split('.')
            if args.exchange and exchange.upper() != args.exchange.upper():
                continue

            rq_exchange = get_exchange_mapping(exchange)
            months = sym_info['months']
            name = sym_info['name']
            continuous_suffixes = sym_info.get('continuous', [])
            
            print(f"\n✨ 开始拉取品种: [{name}] {symbol_raw}")
            
            # --- 1. 下载连续合约 (88/888/99) ---
            if continuous_suffixes:
                print(f"    📥 [连续合约] 检测到需要拉取连续属性: {continuous_suffixes}")
                for suffix in continuous_suffixes:
                    # 拼接米筐连续合约代码，如 rb88.SHFE, IF99.CFFEX
                    # 注意：有些交易所如上期所 base_sym 是小写（如 rb），中金所是大写（如 IF）
                    # 米筐对于大类通常保持大小写一致性，这里我们直接根据 original 映射
                    # 先看看 all_futures 里的 underlying_symbol 是大写还是小写，保持一致
                    sample_rows = all_futures[all_futures['underlying_symbol'].str.upper() == base_sym.upper()]
                    if not sample_rows.empty:
                        real_base = sample_rows.iloc[0]['underlying_symbol']
                    else:
                        real_base = base_sym
                        
                    contract_code = f"{real_base}{suffix}"
                    
                    max_dt = db.get_max_datetime(f"{real_base}{suffix}", exchange, interval)
                    fetch_start = max_dt.date() if max_dt else continuous_start
                    
                    if fetch_start >= continuous_end:
                        print(f"      ⏭️ 连续代码 {contract_code} 已是最新 ({fetch_start})，跳过...")
                        continue

                    # Try both with and without exchange suffix, as RQData standardizes some with suffix recently, but historically it's without.
                    # Actually, RQData accepts IF88 directly.
                    print(f"      📥 正在分片拉取连续代码: {contract_code} ({fetch_start} ~ {continuous_end})...")
                    
                    df = fetch_price_chunked(contract_code, fetch_start, continuous_end, interval)
                    
                    if df is not None and not df.empty:
                        # 转换有 datetime 列
                        if 'datetime' not in df.columns and 'time' in df.columns:
                            df = df.rename(columns={'time': 'datetime'})
                        elif 'index' in df.columns:
                            df = df.rename(columns={'index': 'datetime'})
                            
                        bars = []
                        for _, row_data in df.iterrows():
                            bar = BarData(
                                symbol=f"{real_base}{suffix}",
                                exchange=exchange,
                                datetime=row_data['datetime'].to_pydatetime() if hasattr(row_data['datetime'], 'to_pydatetime') else pd.to_datetime(row_data['datetime']),
                                interval=interval,
                                volume=row_data['volume'],
                                turnover=row_data.get('total_turnover', 0.0),
                                open_interest=row_data.get('open_interest', 0.0),
                                open_price=row_data['open'],
                                high_price=row_data['high'],
                                low_price=row_data['low'],
                                close_price=row_data['close']
                            )
                            bars.append(bar)
                            
                        if bars:
                            db.save_bar_data(bars)
                            print(f"        ✅ 连续合约 {contract_code} 入库成功: 共 {len(bars)} 根 1m K线。")
                            total_contracts += 1
            
            # --- 2. 下载单合约历史数据 ---
            cond_underlying = all_futures['underlying_symbol'].str.upper() == base_sym.upper()
            cond_exchange = all_futures['exchange'] == rq_exchange
            matched_contracts = all_futures[cond_underlying & cond_exchange]
            
            if matched_contracts.empty:
                continue
                
            contracts_to_fetch = []
            for _, row in matched_contracts.iterrows():
                order_book_id = row['order_book_id']
                listed_date = row['listed_date']
                de_listed_date = row['de_listed_date']
                
                digits = re.findall(r'\d+', order_book_id)
                if not digits or len(digits[0]) < 3:
                    # 如果数字部分少于3位，例如 IF88，则不是标准单月合约，跳过
                    continue
                month_str = digits[0][-2:]
                
                year_str = digits[0][:-2]
                if len(year_str) == 2:
                    contract_year = int("20" + year_str)
                else:
                    contract_year = int(year_str)
                    
                if start_year <= contract_year <= end_year and month_str in months:
                    contracts_to_fetch.append({
                        'id': order_book_id,
                        'start': listed_date,
                        'end': de_listed_date
                    })
                    
            print(f"    📥 [单合约] 开始拉取符合月份筛选的 {len(contracts_to_fetch)} 个历史单合约...")
            
            for item in contracts_to_fetch:
                contract_code = item['id']
                start_date = item['start']
                end_date = item['end']
                
                clean_symbol = contract_code.split('.')[0]
                max_dt = db.get_max_datetime(clean_symbol, exchange, interval)
                
                if isinstance(start_date, str):
                    start_dt_val = datetime.strptime(start_date[:10], "%Y-%m-%d").date()
                else:
                    start_dt_val = start_date.date() if hasattr(start_date, 'date') else start_date
                    
                fetch_start = max_dt.date() if max_dt else start_dt_val
                
                if isinstance(end_date, str):
                    end_dt = datetime.strptime(end_date[:10], "%Y-%m-%d").date()
                else:
                    end_dt = end_date.date() if hasattr(end_date, 'date') else end_date

                if fetch_start >= end_dt:
                    print(f"      ⏭️ 单合约 {contract_code} 已是最新 ({fetch_start})，跳过...")
                    continue
                
                print(f"      📥 正在分片拉取单合约: {contract_code} ({fetch_start} ~ {end_date})...")
                df = fetch_price_chunked(contract_code, fetch_start, end_date, interval)
                
                if df is not None and not df.empty:
                    if 'datetime' not in df.columns and 'time' in df.columns:
                        df = df.rename(columns={'time': 'datetime'})
                    elif 'index' in df.columns:
                        df = df.rename(columns={'index': 'datetime'})
                        
                    bars = []
                    for _, row_data in df.iterrows():
                        clean_symbol = contract_code.split('.')[0]
                        
                        bar = BarData(
                            symbol=clean_symbol,
                            exchange=exchange,
                            datetime=row_data['datetime'].to_pydatetime() if hasattr(row_data['datetime'], 'to_pydatetime') else pd.to_datetime(row_data['datetime']),
                            interval=interval,
                            volume=row_data['volume'],
                            turnover=row_data.get('total_turnover', 0.0),
                            open_interest=row_data.get('open_interest', 0.0),
                            open_price=row_data['open'],
                            high_price=row_data['high'],
                            low_price=row_data['low'],
                            close_price=row_data['close']
                        )
                        bars.append(bar)
                        
                    if bars:
                        db.save_bar_data(bars)
                        print(f"        ✅ 单合约 {contract_code} 入库成功: 共 {len(bars)} 根 1m K线。")
                        total_contracts += 1
                
                time.sleep(0.1)

    print("==================================================")
    print(f"🏁 任务完成！本次共成功下载并导入 {total_contracts} 个合约/连续品种的数据。")
    print("==================================================")

if __name__ == "__main__":
    run_rq_download()
