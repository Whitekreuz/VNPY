import sys
import os
import getpass
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 加载 .env
load_dotenv()

# 将项目根目录加入路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.ifind_loader import IFinDLoader
from data.db_manager import DBManager
from core.models import BarData

def run():
    print("="*50)
    print("Phase 2.5: 同花顺 iFinD 历史数据批量拉取与入库")
    print("="*50)
    
    loader = IFinDLoader()
    if not loader.login():
        print("iFinD 登录失败，请检查 .env 配置或账号状态。")
        return

    # 设置拉取的品种（白银连续主力）和时间段
    # 注意：同花顺期货主力连续合约代码一般为 品种+00，如 ag00.SHF
    symbol = "ag00.SHF"
    interval = "1m"
    
    # 抓取过去 30 天的 1m 数据，避免触发免费账号 5W 条记录的限制
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    print(f"\n开始拉取数据：")
    print(f"-> 品种: {symbol}")
    print(f"-> 周期: {interval}")
    print(f"-> 时间: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    
    # 拉取 K线 数据
    df = loader.fetch_history_bars(symbol, start_date, end_date, interval=interval)
    
    loader.logout()
    
    if df is None or df.empty:
        print("\n未能拉取到数据，可能是节假日或参数错误。")
        return
        
    print(f"\n成功拉取到 {len(df)} 条记录。开始转换并入库...")
    
    # 连接数据库
    db_name = os.getenv("PG_DBNAME", "quant_db")
    db_user = os.getenv("PG_USER", "postgres")
    db_pass = os.getenv("PG_PASSWORD", "")
    db_host = os.getenv("PG_HOST", "localhost")
    db_port = os.getenv("PG_PORT", "5432")
    
    try:
        db = DBManager(dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port)
    except Exception as e:
        print(f"数据库连接失败，请检查 PostgreSQL 服务和配置: {e}")
        return

    # 组装 BarData 列表
    bars = []
    for _, row in df.iterrows():
        bar = BarData(
            symbol=row['symbol'],
            exchange=row['exchange'],
            datetime=row['datetime'],
            interval=row['interval'],
            open_price=float(row['open_price']),
            high_price=float(row['high_price']),
            low_price=float(row['low_price']),
            close_price=float(row['close_price']),
            volume=float(row['volume']),
            turnover=float(row['turnover'])
        )
        bars.append(bar)
        
    # 保存入库
    try:
        db.save_bar_data(bars)
        print(f"成功将 {len(bars)} 根 K 线写入 PostgreSQL 数据库表 (bardata) 中！")
    except Exception as e:
        print(f"写入数据库时发生错误: {e}")

if __name__ == "__main__":
    run()
