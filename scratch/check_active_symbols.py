# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from data.db_manager import DBManager

db_name = os.getenv("PG_DBNAME_PROD", "quant_db_prod")
db_user = os.getenv("PG_USER", "postgres")
db_pass = os.getenv("PG_PASSWORD", "")
db_host = os.getenv("PG_HOST", "localhost")
db_port = os.getenv("PG_PORT", "5432")

db = DBManager(dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port)
with db.conn.cursor() as cur:
    cur.execute("""
        SELECT symbol, COUNT(*) 
        FROM bardata 
        WHERE symbol LIKE 'AG%' AND datetime >= '2026-01-01' 
        GROUP BY symbol 
        ORDER BY COUNT(*) DESC 
        LIMIT 10;
    """)
    print("AG symbols count >= 2026-01-01:", cur.fetchall())
    
    cur.execute("""
        SELECT symbol, COUNT(*) 
        FROM bardata 
        WHERE symbol LIKE 'RB%' AND datetime >= '2026-01-01' 
        GROUP BY symbol 
        ORDER BY COUNT(*) DESC 
        LIMIT 10;
    """)
    print("RB symbols count >= 2026-01-01:", cur.fetchall())
db.close()
