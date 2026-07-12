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
cur.execute("SELECT DISTINCT interval FROM bardata ORDER BY interval")
print("Intervals in DB:", [r[0] for r in cur.fetchall()])
conn.close()
