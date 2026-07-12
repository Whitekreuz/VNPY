import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    dbname='quant_db_prod',
    user=os.getenv('PG_USER', 'postgres'),
    password=os.getenv('PG_PASSWORD', ''),
    host=os.getenv('PG_HOST', 'localhost'),
    port=int(os.getenv('PG_PORT', 5432))
)

cur = conn.cursor()
# We do a fast query on bardata to get unique symbols starting with 'SR'
cur.execute("SELECT DISTINCT symbol FROM bardata WHERE symbol LIKE 'SR%' ORDER BY symbol;")
all_sr = [r[0] for r in cur.fetchall()]
print("All SR symbols in database:", len(all_sr))

active_sr = []
for sym in all_sr:
    digits = "".join([c for c in sym if c.isdigit()])
    if len(digits) == 4:
        yy = int(digits[:2])
        if yy >= 25: # Check >= 2025
            active_sr.append(sym)
    elif len(digits) <= 3:
        active_sr.append(sym)

print("Active SR symbols (>=25 or continuous):", active_sr)

cur.close()
conn.close()
