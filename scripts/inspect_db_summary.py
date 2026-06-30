import os
import sys
import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data.db_manager import DBManager

def inspect_db():
    load_dotenv()
    db_name = os.getenv("PG_DBNAME_PROD", "quant_db_prod")
    db_user = os.getenv("PG_USER", "postgres")
    db_pass = os.getenv("PG_PASSWORD", "")
    db_host = os.getenv("PG_HOST", "localhost")
    db_port = os.getenv("PG_PORT", "5432")
    
    print(f"Connecting to database {db_name}...")
    try:
        db = DBManager(dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port)
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    # 查询 bardata 表中，按 exchange 和 基础品种 分组统计的数据行数、最小日期、最大日期
    query = """
        SELECT 
            exchange,
            regexp_replace(symbol, '[0-9]+$', '') AS underlying,
            COUNT(DISTINCT symbol) AS contract_count,
            COUNT(*) AS bar_count,
            MIN(datetime) AS min_time,
            MAX(datetime) AS max_time
        FROM bardata
        GROUP BY exchange, underlying
        ORDER BY exchange, underlying;
    """
    
    try:
        df = pd.read_sql_query(query, db.conn)
        if df.empty:
            print("No data found in bardata table.")
        else:
            print("\n--- Database Content Summary ---")
            print(df.to_string(index=False))
    except Exception as e:
        print(f"Query failed: {e}")

if __name__ == "__main__":
    inspect_db()
