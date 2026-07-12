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

# All tables
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)

for t in tables:
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position", (t,))
    cols = cur.fetchall()
    print(f"\nTable [{t}] columns:")
    for c in cols:
        print(f"  {c[0]}: {c[1]}")

# Check sample from main_contract_mapping
if 'main_contract_mapping' in tables:
    cur.execute("SELECT * FROM main_contract_mapping LIMIT 10")
    rows = cur.fetchall()
    print("\nSample main_contract_mapping rows:")
    for r in rows:
        print(" ", r)
    cur.execute("SELECT COUNT(*) FROM main_contract_mapping")
    print("Total rows in main_contract_mapping:", cur.fetchone()[0])

# Check distinct symbols in bardata (first letters / varieties)
cur.execute("""
    SELECT DISTINCT 
        regexp_replace(symbol, '[0-9]', '', 'g') as variety,
        MIN(datetime) as earliest,
        MAX(datetime) as latest,
        COUNT(*) as bar_count
    FROM bardata
    WHERE interval='1m'
    GROUP BY variety
    ORDER BY variety
""")
rows = cur.fetchall()
print("\nAll varieties in bardata with date ranges:")
for r in rows:
    print(f"  {r[0]}: {r[1].date()} to {r[2].date()} ({r[3]:,} bars)")

conn.close()
