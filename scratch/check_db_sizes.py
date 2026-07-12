# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from data.db_manager import DBManager

db_user = os.getenv("PG_USER", "postgres")
db_pass = os.getenv("PG_PASSWORD", "")
db_host = os.getenv("PG_HOST", "localhost")
db_port = os.getenv("PG_PORT", "5432")

# Count in quant_db
try:
    db1 = DBManager(dbname="quant_db", user=db_user, password=db_pass, host=db_host, port=db_port)
    with db1.conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM bardata;")
        print("Total bars in quant_db:", cur.fetchone()[0])
    db1.close()
except Exception as e:
    print("Error querying quant_db:", e)

# Count in quant_db_prod
try:
    db2 = DBManager(dbname="quant_db_prod", user=db_user, password=db_pass, host=db_host, port=db_port)
    with db2.conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM bardata;")
        print("Total bars in quant_db_prod:", cur.fetchone()[0])
    db2.close()
except Exception as e:
    print("Error querying quant_db_prod:", e)
