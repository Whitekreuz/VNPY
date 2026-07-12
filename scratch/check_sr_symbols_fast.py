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
# Query for SR2601 and SR2701 specifically
cur.execute("SELECT DISTINCT symbol FROM bardata WHERE symbol IN ('SR2601', 'SR2701')")
print("SR2601/SR2701 present:", cur.fetchall())

# Query for any symbol containing 27
cur.execute("SELECT DISTINCT symbol FROM bardata WHERE symbol LIKE '%27%' LIMIT 20")
print("Any 27 symbols:", cur.fetchall())

conn.close()
