import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def test():
    conn = psycopg2.connect(
        dbname=os.getenv("PG_DBNAME_PROD", "quant_db_prod"),
        user=os.getenv("PG_USER", "postgres"),
        password=os.getenv("PG_PASSWORD", ""),
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", 5432))
    )
    cur = conn.cursor()
    import time
    
    # Test normal DISTINCT
    print("Testing normal DISTINCT query...")
    t0 = time.time()
    try:
        cur.execute("SELECT DISTINCT symbol FROM bardata WHERE interval = '1m'")
        rows1 = cur.fetchall()
        print(f"Normal DISTINCT took: {time.time() - t0:.4f}s, count: {len(rows1)}")
    except Exception as e:
        print("Normal DISTINCT failed:", e)
        conn.rollback()

    # Test recursive CTE
    print("Testing recursive CTE query...")
    t0 = time.time()
    try:
        cur.execute("""
            WITH RECURSIVE t AS (
                (SELECT symbol FROM bardata WHERE interval = '1m' ORDER BY symbol LIMIT 1)
                UNION ALL
                SELECT (SELECT symbol FROM bardata WHERE symbol > t.symbol AND interval = '1m' ORDER BY symbol LIMIT 1)
                FROM t
                WHERE t.symbol IS NOT NULL
            )
            SELECT symbol FROM t WHERE symbol IS NOT NULL;
        """)
        rows2 = cur.fetchall()
        print(f"Recursive CTE took: {time.time() - t0:.4f}s, count: {len(rows2)}")
    except Exception as e:
        print("Recursive CTE failed:", e)
        conn.rollback()
        
    conn.close()

if __name__ == "__main__":
    test()
