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
cur.execute("SELECT COUNT(*) FROM main_contract_mapping;")
count = cur.fetchone()[0]
print("Mapping count:", count)

cur.execute("SELECT DISTINCT sub_symbol FROM main_contract_mapping ORDER BY sub_symbol LIMIT 50;")
symbols = [r[0] for r in cur.fetchall()]
print("Some mapping symbols:", symbols)

cur.close()
conn.close()
