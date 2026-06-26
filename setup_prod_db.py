import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

load_dotenv()
try:
    conn = psycopg2.connect(
        dbname='postgres', 
        user=os.getenv('PG_USER', 'postgres'), 
        password=os.getenv('PG_PASSWORD', ''), 
        host=os.getenv('PG_HOST', 'localhost')
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'quant_db_prod'")
    exists = cur.fetchone()
    if not exists:
        cur.execute('CREATE DATABASE quant_db_prod')
        print("Successfully created DB quant_db_prod")
    else:
        print("DB quant_db_prod already exists.")
    cur.close()
    conn.close()
except Exception as e:
    print(f"创建数据库失败: {e}")
