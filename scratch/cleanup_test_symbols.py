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

# 1. Clean up quant_db
try:
    db1 = DBManager(dbname="quant_db", user=db_user, password=db_pass, host=db_host, port=db_port)
    with db1.conn.cursor() as cur:
        # Find all test symbols in quant_db
        cur.execute("SELECT DISTINCT symbol FROM bardata;")
        symbols = [r[0] for r in cur.fetchall()]
        # Delete lowercase symbols or test patterns
        test_symbols = [s for s in symbols if any(x in s.upper() for x in ["TQ", "CTP", "RQ"]) or s != s.upper()]
        print("Test symbols to delete from quant_db:", test_symbols)
        for ts in test_symbols:
            cur.execute("DELETE FROM bardata WHERE symbol = %s;", (ts,))
            print(f"Deleted {ts} from quant_db.")
        db1.conn.commit()
    db1.close()
except Exception as e:
    print("Error cleaning quant_db:", e)

# 2. Clean up quant_db_prod
try:
    db2 = DBManager(dbname="quant_db_prod", user=db_user, password=db_pass, host=db_host, port=db_port)
    with db2.conn.cursor() as cur:
        # Find all test symbols in quant_db_prod
        cur.execute("SELECT DISTINCT symbol FROM bardata;")
        symbols = [r[0] for r in cur.fetchall()]
        test_symbols = [s for s in symbols if any(x in s.upper() for x in ["TQ", "CTP", "RQ"]) or s != s.upper()]
        print("Test symbols to delete from quant_db_prod:", test_symbols)
        for ts in test_symbols:
            cur.execute("DELETE FROM bardata WHERE symbol = %s;", (ts,))
            print(f"Deleted {ts} from quant_db_prod.")
        db2.conn.commit()
    db2.close()
except Exception as e:
    print("Error cleaning quant_db_prod:", e)
