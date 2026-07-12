import psycopg2, os
from dotenv import load_dotenv
load_dotenv()

try:
    conn = psycopg2.connect(
        dbname='quant_db_prod',
        user=os.getenv('PG_USER', 'postgres'),
        password=os.getenv('PG_PASSWORD', ''),
        host=os.getenv('PG_HOST', 'localhost'),
        port=int(os.getenv('PG_PORT', 5432))
    )
    print("Database connection success!")
    cur = conn.cursor()
    
    # Query active queries
    cur.execute("""
        SELECT pid, state, query, age(clock_timestamp(), query_start) 
        FROM pg_stat_activity 
        WHERE state != 'idle' AND query NOT LIKE '%pg_stat_activity%'
    """)
    print("Active queries:")
    for r in cur.fetchall():
        print(r)
        
    conn.close()
except Exception as e:
    print("Error:", e)
