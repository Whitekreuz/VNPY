import os
import sys
import json
import time
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data.db_manager import DBManager
from core.models import BarData

# 延迟导入 tqsdk
tq = None

def get_tq_exchange(exchange: str) -> str:
    """将系统交易所名称映射为天勤交易所格式"""
    mapping = {
        "SHF": "SHFE",
        "DCE": "DCE",
        "CZC": "CZCE",
        "CFE": "CFFEX",
        "GFE": "GFEX",
        "INE": "INE"
    }
    return mapping.get(exchange.upper(), exchange.upper())

def run_daily_update():
    global tq
    try:
        from tqsdk import TqApi, TqAuth
    except ImportError:
        print("❌ 未检测到 tqsdk 库，请先运行: pip install tqsdk")
        return

    load_dotenv()
    
    # 1. 数据库连接
    db_name = os.getenv("PG_DBNAME_PROD", "quant_db_prod")
    db_user = os.getenv("PG_USER", "postgres")
    db_pass = os.getenv("PG_PASSWORD", "")
    db_host = os.getenv("PG_HOST", "localhost")
    db_port = os.getenv("PG_PORT", "5432")
    
    print("==================================================")
    print(f"🔄 启动天勤量化 (TqSdk) 每日增量更新引擎")
    print(f"📦 目标生产数据库: {db_name}@{db_host}")
    print("==================================================")
    
    try:
        db = DBManager(dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port)
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return

    # 2. 天勤登录认证 (使用免费注册的账号密码)
    tq_user = os.getenv("TQ_USERNAME")
    tq_pass = os.getenv("TQ_PASSWORD")
    
    if not tq_user or not tq_pass:
        print("💡 未在环境变量中检测到 TQ_USERNAME 或 TQ_PASSWORD")
        tq_user = input("请输入您的天勤账号(手机号): ").strip()
        tq_pass = input("请输入您的天勤密码: ").strip()
        
    try:
        api = TqApi(auth=TqAuth(tq_user, tq_pass))
        print("✅ 天勤量化 API 登录成功！")
    except Exception as e:
        print(f"❌ 天勤量化登录失败: {e}")
        return

    # 3. 读取品种配置
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'futures_symbols.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    current_year = datetime.now().year
    years_to_check = [current_year - 1, current_year, current_year + 1]
    
    total_inserted = 0

    try:
        for category, cat_data in config.items():
            print(f"\n📂 处理板块: {category}")
            for symbol_raw, sym_info in cat_data['symbols'].items():
                base_sym, exchange = symbol_raw.split('.')
                tq_exchange = get_tq_exchange(exchange)
                name = sym_info['name']
                months = sym_info['months']
                
                print(f"  ✨ 正在更新品种: [{name}] {symbol_raw}")
                
                # 需要查询的全部合约列表（包含单合约和连续合约）
                targets = []
                
                # A. 连续合约：主力连续 (88 -> KQ.m@)、指数连续 (99 -> KQ.i@)
                # 天勤格式: KQ.m@SHFE.rb / KQ.i@SHFE.rb
                # 注意：天勤的代码品种部分必须跟交易所一致，比如大商所豆粕是小写 m
                # 我们可以通过临时拉取 quote 来自动匹配真实合约，判断其品种大小写
                tq_base = base_sym
                
                targets.append({
                    "tq_code": f"KQ.m@{tq_exchange}.{tq_base}",
                    "db_symbol": f"{base_sym}88"
                })
                targets.append({
                    "tq_code": f"KQ.i@{tq_exchange}.{tq_base}",
                    "db_symbol": f"{base_sym}99"
                })
                
                # B. 单合约：根据配置的 active months，检查前一年、今年、后一年的合约
                for y in years_to_check:
                    y_str = str(y)[-2:] # 取后两位 '26'
                    for m in months:
                        contract_code = f"{tq_exchange}.{tq_base}{y_str}{m}"
                        targets.append({
                            "tq_code": contract_code,
                            "db_symbol": f"{base_sym}{y_str}{m}"
                        })
                
                # 开始逐个下载当天数据（拉取最近的 1000 根 1m K线，覆盖完整的一天）
                for target in targets:
                    tq_code = target["tq_code"]
                    db_symbol = target["db_symbol"]
                    
                    try:
                        # 仅获取最近的 1000 根 K线（覆盖一整天 360 根绰绰有余，且完全在免费版 8000 根额度内）
                        klines = api.get_kline_serial(tq_code, duration_seconds=60, data_length=1000)
                        
                        # 稍微等待数据同步
                        api.wait_update()
                        
                        if klines is not None and len(klines) > 0:
                            bars = []
                            # 过滤出当天的 K 线数据 (判断最新时间与本地时间的差值，或者直接同步最近 500 根防止节假日遗漏)
                            # 这里采用 INSERT ON CONFLICT DO UPDATE，直接把这 1000 根推过去即可，数据库会自动去重
                            for _, row in klines.iterrows():
                                # 天勤的 datetime 是纳秒时间戳
                                dt = datetime.fromtimestamp(row['datetime'] / 1e9)
                                
                                bar = BarData(
                                    symbol=db_symbol,
                                    exchange=exchange,
                                    datetime=dt,
                                    interval="1m",
                                    volume=float(row['volume']),
                                    turnover=float(row.get('value', 0.0)), # 天勤的成交额字段为 value
                                    open_interest=float(row.get('open_interest', 0.0)),
                                    open_price=float(row['open']),
                                    high_price=float(row['high']),
                                    low_price=float(row['low']),
                                    close_price=float(row['close'])
                                )
                                bars.append(bar)
                                
                            if bars:
                                db.save_bar_data(bars)
                                total_inserted += len(bars)
                                
                    except Exception as e:
                        # 对于不活跃或未上市合约，天勤报错是正常情况，静默跳过
                        pass
                        
                # 减缓请求速度，防触发反爬
                time.sleep(0.1)
                
        print("==================================================")
        print(f"🏁 增量数据更新完成！共向数据库追加/同步了 {total_inserted} 根 1m K线数据。")
        print("==================================================")

    finally:
        api.close()

if __name__ == "__main__":
    run_daily_update()
