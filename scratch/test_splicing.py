import psycopg2
import os
import time
from datetime import datetime
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

# Test Splicing Logic for SR2605
symbol = "SR2605"
exchange = "CZC"
interval = "1m"
start = datetime(2018, 1, 1)
end = datetime(2026, 7, 1)

# 1. Parse symbol
variety = "".join([c for c in symbol if c.isalpha()])
digits = "".join([c for c in symbol if c.isdigit()])

print(f"Parsed variety: {variety}, digits: {digits}")

if len(digits) == 4:
    y_target = int(digits[:2])
    m_target = int(digits[2:])
    
    # Query all matching symbols for this variety and month
    pattern = f"{variety}%{m_target:02d}"
    cur.execute("SELECT DISTINCT symbol FROM bardata WHERE symbol LIKE %s;", (pattern,))
    matching_symbols = sorted([r[0] for r in cur.fetchall()])
    print("Found matching historical symbols:", matching_symbols)
    
    all_bars_count = 0
    spliced_details = []
    
    for sym in matching_symbols:
        sym_digits = "".join([c for c in sym if c.isdigit()])
        yy = int(sym_digits[:2])
        mm = int(sym_digits[2:])
        
        delivery_year = 2000 + yy
        
        # Splicing window
        window_start = datetime(delivery_year - 1, mm, 16, 0, 0, 0)
        window_end = datetime(delivery_year, mm, 15, 23, 59, 59)
        
        # Overrides for boundaries
        if sym == matching_symbols[0]:
            window_start = start
        if sym == matching_symbols[-1]:
            window_end = end
            
        q_start = max(start, window_start)
        q_end = min(end, window_end)
        
        if q_start <= q_end:
            cur.execute("""
                SELECT COUNT(*) FROM bardata 
                WHERE symbol = %s AND exchange = %s AND interval = %s AND datetime >= %s AND datetime <= %s;
            """, (sym, exchange, interval, q_start, q_end))
            cnt = cur.fetchone()[0]
            all_bars_count += cnt
            spliced_details.append(f"{sym} inside [{q_start} to {q_end}]: {cnt} bars")
            
    print(f"Spliced total: {all_bars_count} bars.")
    for d in spliced_details:
        print("  -", d)

cur.close()
conn.close()
