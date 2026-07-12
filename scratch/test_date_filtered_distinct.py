import psycopg2
import os
import time
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
start_time = time.time()

# Test fast query on recent data
query = "SELECT DISTINCT symbol FROM bardata WHERE datetime >= '2025-01-01' ORDER BY symbol;"
cur.execute(query)
symbols = [r[0] for r in cur.fetchall()]
end_time = time.time()

print(f"Loaded {len(symbols)} unique symbols from recent data in {end_time - start_time:.4f} seconds!")
print("Symbols:", symbols[:20])

cur.close()
conn.close()
