import sys
import os
import getpass
from datetime import datetime, timedelta
from dotenv import load_dotenv

# 加载 .env
load_dotenv()

# 将项目根目录加入路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.db_manager import DBManager
from backtest.backtester import CtaBacktester
from strategy.strategies.double_ma_strategy import DoubleMaStrategy

def run():
    print("="*50)
    print("Phase 2.5: CTA 回测引擎链路闭环验证")
    print("="*50)
    
    # 连接数据库
    db_name = os.getenv("PG_DBNAME", "quant_db")
    db_user = os.getenv("PG_USER", "postgres")
    db_pass = os.getenv("PG_PASSWORD", "")
    db_host = os.getenv("PG_HOST", "localhost")
    db_port = os.getenv("PG_PORT", "5432")
    
    try:
        db = DBManager(dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port)
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return

    # 初始化回测引擎
    backtester = CtaBacktester(db)
    
    symbol = "ag00.SHF"
    interval = "1m"
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # 加载数据
    db_symbol = symbol.split('.')[0]
    db_exchange = symbol.split('.')[1] if '.' in symbol else "SHF"
    backtester.load_data(db_symbol, db_exchange, interval, start_date, end_date)
    
    if not backtester.bars:
        print(f"未能从数据库加载到 {symbol} 的数据，请先运行 download_data.py！")
        return
        
    # 绑定策略类与参数
    backtester.set_strategy(DoubleMaStrategy, "DoubleMa_Test", symbol, {"fast_window": 10, "slow_window": 20})
    
    # 开始回测
    backtester.run_backtest()
    
    print("\n--- 回测统计 ---")
    print(f"总成交笔数: {len(backtester.trades)}")
    print(f"期末持仓: {backtester.positions}")
    if backtester.trades:
        print(f"最后一笔成交: {backtester.trades[-1]}")

if __name__ == "__main__":
    run()
