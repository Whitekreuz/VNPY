import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    dbname='quant_db',
    user=os.getenv('PG_USER', 'postgres'),
    password=os.getenv('PG_PASSWORD', ''),
    host=os.getenv('PG_HOST', 'localhost'),
    port=int(os.getenv('PG_PORT', 5432))
)

cur = conn.cursor()
# Query all tables in public schema
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
""")
tables = [r[0] for r in cur.fetchall()]
print("Tables in quant_db_prod:", tables)

for table in tables:
    cur.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{table}';
    """)
    cols = cur.fetchall()
    print(f"Table '{table}' columns:")
    for col in cols:
        print(f"  - {col[0]}: {col[1]}")

cur.close()
conn.close()
