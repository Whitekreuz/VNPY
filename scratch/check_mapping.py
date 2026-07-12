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

# Check main_contract_mapping
cur.execute("SELECT COUNT(*) FROM main_contract_mapping")
print("main_contract_mapping rows:", cur.fetchone()[0])

cur.execute("SELECT * FROM main_contract_mapping LIMIT 20")
rows = cur.fetchall()
print("\nSample main_contract_mapping:")
for r in rows:
    print(" ", r)

# Check distinct underlying values to see the variety codes used
cur.execute("SELECT DISTINCT underlying, exchange FROM main_contract_mapping ORDER BY underlying LIMIT 60")
rows = cur.fetchall()
print("\nDistinct underlying+exchange in main_contract_mapping:")
for r in rows:
    print(f"  underlying={r[0]}, exchange={r[1]}")

conn.close()
