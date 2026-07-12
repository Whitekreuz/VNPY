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
cur.execute("SELECT DISTINCT symbol FROM bardata WHERE symbol IN ('SR2601', 'SR2701') AND exchange = 'CZC' AND interval = '1m'")
print("SR2601/SR2701 present:", cur.fetchall())
conn.close()
