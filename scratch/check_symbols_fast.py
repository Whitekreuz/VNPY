import psycopg2, os
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(
    dbname='quant_db_prod',
    user=os.getenv('PG_USER','postgres'),
    password=os.getenv('PG_PASSWORD',''),
    host=os.getenv('PG_HOST','localhost'),
    port=int(os.getenv('PG_PORT',5432))
)
cur = conn.cursor()

# Get distinct symbols with their date range - but using DISTINCT ON for speed
# Just get unique symbols quickly using pg_stats or a fast sampled query
cur.execute("""
    SELECT DISTINCT symbol, exchange
    FROM bardata
    WHERE interval = '1m'
    ORDER BY symbol
    LIMIT 500;
""")
rows = cur.fetchall()
print(f"Found {len(rows)} distinct symbols in bardata (1m interval):")
for r in rows[:80]:
    print(f"  {r[0]} @ {r[1]}")
if len(rows) > 80:
    print(f"  ... and {len(rows)-80} more")

conn.close()
