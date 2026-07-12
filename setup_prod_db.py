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
    
    # 1. 创建生产库 quant_db_prod
    cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'quant_db_prod'")
    exists_prod = cur.fetchone()
    if not exists_prod:
        cur.execute('CREATE DATABASE quant_db_prod')
        print("Successfully created DB quant_db_prod")
    else:
        print("DB quant_db_prod already exists.")
        
    # 2. 创建测试库 quant_db_test
    cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'quant_db_test'")
    exists_test = cur.fetchone()
    if not exists_test:
        cur.execute('CREATE DATABASE quant_db_test')
        print("Successfully created DB quant_db_test")
    else:
        print("DB quant_db_test already exists.")
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"创建数据库失败: {e}")

