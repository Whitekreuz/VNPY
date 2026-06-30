import os
import sys
import json
import time
from datetime import datetime, timedelta
import pandas as pd

# 确保能导入项目根目录的模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.ifind_loader import IFinDLoader
from data.db_manager import DBManager
from core.models import BarData
from dotenv import load_dotenv

def get_last_day_of_month(any_date):
    next_month = any_date.replace(day=28) + timedelta(days=4)
    return next_month - timedelta(days=next_month.day)

def generate_chunks(start_date: datetime, end_date: datetime, chunk_days: int = 90):
    """将总时间段按天数进行切片"""
    chunks = []
    current_start = start_date
    while current_start < end_date:
        current_end = min(current_start + timedelta(days=chunk_days), end_date)
        chunks.append((current_start, current_end))
        current_start = current_end + timedelta(days=1)
    return chunks

def run_bulk_download():
    # 1. 加载环境变量与配置
    load_dotenv()
    
    # 强制连接 PROD 生产库 (若没有设置，默认回退到 quant_db_prod)
    db_name = os.getenv("PG_DBNAME_PROD", "quant_db_prod")
    db_user = os.getenv("PG_USER", "postgres")
    db_pass = os.getenv("PG_PASSWORD", "")
    db_host = os.getenv("PG_HOST", "localhost")
    db_port = os.getenv("PG_PORT", "5432")
    
    print("==================================================")
    print(f"🚀 初始化历史单合约全量扫盘任务")
    print(f"📦 目标生产数据库: {db_name}@{db_host}")
    print("==================================================")
    
    try:
        db = DBManager(dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port)
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return

    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'futures_symbols.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 2. 登录 iFinD
    loader = IFinDLoader()
    if not loader.login():
        print("iFinD 登录失败！请检查网络和账号。")
        return

    # 3. 扫盘参数设定
    start_year = 2018
    end_year = 2026
    interval = "1m"
    
    total_contracts = 0
    success_contracts = 0
    
    for category, cat_data in config.items():
        print(f"\n📂 开始扫描板块: {category} - {cat_data.get('description', '')}")
        
        for symbol_raw, sym_info in cat_data['symbols'].items():
            base_sym, exchange = symbol_raw.split('.')
            
            # 由于当前 iFinD 账户没有 DCE 的分钟线权限，主动跳过大商所品种以节约时间和 API 请求
            if exchange == 'DCE':
                print(f"  ⏭️ 主动跳过大商所品种: {sym_info['name']} ({symbol_raw})")
                continue
                
            months = sym_info['months']
            name = sym_info['name']
            
            for year in range(start_year, end_year + 1):
                for month in months:
                    total_contracts += 1
                    
                    # 构造合约代码，例如: ag2006.SHF, OI801.CZC
                    if exchange == 'CZC':
                        year_str = str(year)[-1:]
                    else:
                        year_str = str(year)[-2:]
                    
                    contract_code = f"{base_sym}{year_str}{month}.{exchange}"
                    
                    # 确定该合约的合理生命周期：通常从交割前一年的对应月份开始，到交割当月的月末结束。
                    # 为了冗余，我们提前 1.5 年开始拉取
                    try:
                        contract_end = get_last_day_of_month(datetime(year, int(month), 1))
                        contract_start = datetime(year - 1, 1, 1) # 暴力点，直接从上一年的1月1日开始
                    except ValueError:
                        continue
                    
                    print(f"  ⏳ 正在拉取 [{name}] {contract_code} ({contract_start.date()} ~ {contract_end.date()})...")
                    
                    # 切片拉取 (每次 90 天，防 iFinD 限制)
                    chunks = generate_chunks(contract_start, contract_end, chunk_days=90)
                    all_bars = []
                    
                    for chunk_start, chunk_end in chunks:
                        df = loader.fetch_history_bars(contract_code, chunk_start, chunk_end, interval)
                        if df is not None and not df.empty:
                            # 转换为 BarData
                            for _, row in df.iterrows():
                                bar = BarData(
                                    symbol=contract_code.split('.')[0], # ag2006
                                    exchange=exchange,
                                    datetime=row['datetime'],
                                    interval=interval,
                                    volume=row['volume'],
                                    turnover=row.get('turnover', 0.0),
                                    open_interest=row.get('open_interest', 0.0),
                                    open_price=row['open_price'],
                                    high_price=row['high_price'],
                                    low_price=row['low_price'],
                                    close_price=row['close_price']
                                )
                                all_bars.append(bar)
                                
                        # 降低 API 请求频率
                        time.sleep(0.5)
                        
                    if all_bars:
                        try:
                            db.save_bar_data(all_bars)
                            print(f"    入库成功: {contract_code} 共 {len(all_bars)} 根 1m K线。")
                            success_contracts += 1
                        except Exception as e:
                            print(f"    入库失败: {contract_code}，原因: {e}")
                    else:
                        print(f"    未拉取到数据: {contract_code} (可能是尚未上市或超出权限)。")

    loader.logout()
    print("==================================================")
    print(f"🏁 扫盘任务结束！共尝试 {total_contracts} 个合约，成功入库 {success_contracts} 个合约。")
    print("==================================================")

if __name__ == "__main__":
    # 可以加一个确认提示，防止误操作直接跑几十个小时
    ans = input("⚠️ 即将开始长周期的全量数据下载。请确认已挂载 VPN 并保持网络通畅。是否继续？(y/n): ")
    if ans.lower() == 'y':
        run_bulk_download()
    else:
        print("任务取消。")
