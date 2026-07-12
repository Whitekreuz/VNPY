import psycopg2, os
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
cur.execute("SELECT DISTINCT symbol FROM bardata WHERE symbol LIKE 'SR%' ORDER BY symbol")
symbols = [r[0] for r in cur.fetchall()]
print("SR symbols:", symbols)
conn.close()
