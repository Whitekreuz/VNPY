import os
import sys
import re
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data.db_manager import DBManager

def get_symbol_expiry(symbol: str) -> int:
    """提取合约的到期年月，用于比较先后顺序。如 ag2006 -> 2006"""
    match = re.search(r'\d+', symbol)
    if match:
        return int(match.group())
    return 0

def run_mapping_generation():
    load_dotenv()
    db_name = os.getenv("PG_DBNAME_PROD", "quant_db_prod")
    db_user = os.getenv("PG_USER", "postgres")
    db_pass = os.getenv("PG_PASSWORD", "")
    db_host = os.getenv("PG_HOST", "localhost")
    db_port = os.getenv("PG_PORT", "5432")
    
    print(f"🔗 连接数据库 {db_name}...")
    try:
        db = DBManager(dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port)
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return

    # 1. 用 SQL 聚合出每天每个合约的最大持仓量
    # 注意：这里会把所有 1m 数据聚合成天级别
    print("📊 正在从 bardata 计算每日持仓分布，这可能需要几分钟...")
    query = """
        WITH daily_oi AS (
            SELECT 
                regexp_replace(symbol, '[0-9]+$', '') AS underlying,
                exchange,
                symbol,
                DATE(datetime) AS trade_date,
                MAX(open_interest) AS max_oi
            FROM bardata
            GROUP BY 1, 2, 3, 4
        )
        SELECT * FROM daily_oi ORDER BY underlying, exchange, trade_date, max_oi DESC;
    """
    
    df = pd.read_sql_query(query, db.conn)
    if df.empty:
        print("数据库中没有数据。")
        return

    print("🧠 正在执行粘性（Ratchet）换月算法...")
    # 按品种分组处理
    grouped = df.groupby(['underlying', 'exchange'])
    
    mapping_records = []
    
    for (underlying, exchange), group in grouped:
        print(f"  -> 处理 {underlying}.{exchange}")
        
        # 按天排序
        dates = sorted(group['trade_date'].unique())
        
        current_main = None
        candidate_main = None
        consecutive_days = 0
        
        for d in dates:
            day_data = group[group['trade_date'] == d]
            if day_data.empty:
                continue
                
            # 按 OI 排序
            day_data = day_data.sort_values(by='max_oi', ascending=False)
            
            top_symbol = day_data.iloc[0]['symbol']
            top_oi = day_data.iloc[0]['max_oi']
            
            # 找到现任主力的当前持仓量
            current_main_oi = 0
            if current_main is not None:
                current_row = day_data[day_data['symbol'] == current_main]
                if not current_row.empty:
                    current_main_oi = current_row.iloc[0]['max_oi']
            
            # 找到次主力
            sub_symbol = None
            if len(day_data) > 1:
                # 次主力通常是不等于当前主力的那个持仓最大的
                sub_row = day_data[day_data['symbol'] != (current_main if current_main else top_symbol)]
                if not sub_row.empty:
                    sub_symbol = sub_row.iloc[0]['symbol']
            
            # 初始状态
            if current_main is None:
                current_main = top_symbol
            else:
                # 判断是否换月：必须是比当前主力晚的合约 (例如 2409 > 2405)
                if top_symbol != current_main and get_symbol_expiry(top_symbol) > get_symbol_expiry(current_main):
                    # 规则 1：如果超越 10% 以上，直接暴力换月
                    if top_oi > current_main_oi * 1.10:
                        current_main = top_symbol
                        consecutive_days = 0
                    else:
                        # 规则 2：连续 3 天持仓量第一，才换月
                        if top_symbol == candidate_main:
                            consecutive_days += 1
                            if consecutive_days >= 3:
                                current_main = top_symbol
                                candidate_main = None
                                consecutive_days = 0
                        else:
                            candidate_main = top_symbol
                            consecutive_days = 1
            
            mapping_records.append({
                'underlying': underlying,
                'exchange': exchange,
                'date': d,
                'main_symbol': current_main,
                'sub_symbol': sub_symbol if sub_symbol else current_main
            })
            
    # 2. 将计算好的映射表插入数据库
    print("💾 正在将计算好的换月映射写入 main_contract_mapping 表...")
    if mapping_records:
        insert_query = """
            INSERT INTO main_contract_mapping (underlying, exchange, date, main_symbol, sub_symbol)
            VALUES %s
            ON CONFLICT (underlying, exchange, date) DO UPDATE SET
                main_symbol = EXCLUDED.main_symbol,
                sub_symbol = EXCLUDED.sub_symbol;
        """
        
        values = [
            (r['underlying'], r['exchange'], r['date'], r['main_symbol'], r['sub_symbol'])
            for r in mapping_records
        ]
        
        try:
            from psycopg2.extras import execute_values
            with db.conn.cursor() as cur:
                execute_values(cur, insert_query, values)
                db.conn.commit()
            print("✅ 换月映射表写入成功！")
        except Exception as e:
            print(f"写入映射表失败: {e}")

if __name__ == "__main__":
    run_mapping_generation()
