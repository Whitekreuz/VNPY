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

# Clean up rb2610 from quant_db
try:
    db1 = DBManager(dbname="quant_db", user=db_user, password=db_pass, host=db_host, port=db_port)
    with db1.conn.cursor() as cur:
        cur.execute("DELETE FROM bardata WHERE symbol = 'rb2610';")
        print("Deleted rb2610 explicitly from quant_db.")
        db1.conn.commit()
    db1.close()
except Exception as e:
    print("Error cleaning quant_db:", e)
