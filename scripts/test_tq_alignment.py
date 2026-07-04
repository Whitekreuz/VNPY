# -*- coding: utf-8 -*-
import sys
import os
import time
import pandas as pd
from dotenv import load_dotenv

# Reconfigure stdout to use UTF-8 and enable line buffering (no hang, no print issues)
sys.stdout.reconfigure(line_buffering=True, encoding='utf-8')

print("STEP 1: Starting alignment test script", flush=True)

print("STEP 2: Importing DBManager and tqsdk...", flush=True)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data.db_manager import DBManager
from tqsdk import TqApi, TqAuth
print("STEP 2: Imports completed", flush=True)

print("STEP 3: Loading credentials and connecting to DB...", flush=True)
load_dotenv()
tq_username = os.environ.get("TQ_USERNAME")
tq_password = os.environ.get("TQ_PASSWORD")

db_name = os.getenv("PG_DBNAME_PROD", "quant_db_prod")
db_user = os.getenv("PG_USER", "postgres")
db_pass = os.getenv("PG_PASSWORD", "")
db_host = os.getenv("PG_HOST", "localhost")
db_port = os.getenv("PG_PORT", "5432")

db = DBManager(dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port)
print("STEP 3: Database connection established", flush=True)

print("STEP 4: Connecting to TqApi...", flush=True)
api = TqApi(auth=TqAuth(tq_username, tq_password))
print("STEP 4: TqApi connection successful", flush=True)

try:
    print("STEP 5: Pulling recent K-lines for KQ.m@SHFE.rb...", flush=True)
    klines = api.get_kline_serial("KQ.m@SHFE.rb", 60, data_length=100)
    
    # 核心修复：周末休市期间 wait_update() 会无限阻塞等待新 Tick 产生。
    # 必须传入 deadline 参数（设定 5 秒超时），在这期间天勤底层会自动把历史 K 线同步下来。
    print("STEP 5: Waiting 5 seconds for historical data sync...", flush=True)
    api.wait_update(deadline=time.time() + 5)
    print("STEP 5: K-lines sync completed", flush=True)

    klines['datetime_str'] = pd.to_datetime(klines['datetime'])
    print("\n=== TqSdk K-lines (Last 3 rows) ===", flush=True)
    print(klines[['datetime_str', 'open', 'high', 'low', 'close', 'volume', 'open_oi']].tail(3), flush=True)

    print("\nSTEP 6: Loading max datetime from local DB...", flush=True)
    max_dt = db.get_max_datetime("RB88", "SHF", "1m")
    print(f"STEP 6: Local DB (RB88) max datetime: {max_dt}", flush=True)

finally:
    print("\nSTEP 7: Closing TqApi...", flush=True)
    api.close()
    print("STEP 7: TqApi connection closed successfully", flush=True)

print("STEP 8: Test completed", flush=True)
