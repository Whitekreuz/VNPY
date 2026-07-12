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

# Distinct symbols in quant_db
try:
    db1 = DBManager(dbname="quant_db", user=db_user, password=db_pass, host=db_host, port=db_port)
    with db1.conn.cursor() as cur:
        cur.execute("SELECT DISTINCT symbol FROM bardata ORDER BY symbol;")
        print("Symbols in quant_db:", [r[0] for r in cur.fetchall()])
    db1.close()
except Exception as e:
    print("Error querying quant_db:", e)

# Distinct symbols in quant_db_prod
try:
    db2 = DBManager(dbname="quant_db_prod", user=db_user, password=db_pass, host=db_host, port=db_port)
    with db2.conn.cursor() as cur:
        cur.execute("SELECT DISTINCT symbol FROM bardata ORDER BY symbol;")
        symbols = [r[0] for r in cur.fetchall()]
        print("Symbols in quant_db_prod:", symbols)
        # Filter symbols that are test symbols (contain TQ, CTP, RQ, lower case, etc.)
        test_symbols = [s for s in symbols if any(x in s.upper() for x in ["TQ", "CTP", "RQ"]) or s != s.upper()]
        print("Suspected test/problem symbols in quant_db_prod:", test_symbols)
    db2.close()
except Exception as e:
    print("Error querying quant_db_prod:", e)
