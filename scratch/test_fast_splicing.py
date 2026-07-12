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

# Test fast candidate-based splicing for SR2605
variety = "SR"
month = 5
start = datetime(2018, 1, 1)
end = datetime(2026, 7, 1)
exchange = "CZC"
interval = "1m"

start_time = time.time()

# Construct candidate symbols from 2018 to 2027
candidates = [f"{variety}{yy:02d}{month:02d}" for yy in range(18, 28)]
print("Candidate symbols:", candidates)

all_bars_count = 0
spliced_details = []

for sym in candidates:
    digits = "".join([c for c in sym if c.isdigit()])
    yy = int(digits[:2])
    mm = int(digits[2:])
    
    delivery_year = 2000 + yy
    
    # Active window
    window_start = datetime(delivery_year - 1, mm, 16, 0, 0, 0)
    window_end = datetime(delivery_year, mm, 15, 23, 59, 59)
    
    # Adjust boundaries
    if sym == candidates[0]:
        window_start = start
    if sym == candidates[-1]:
        window_end = end
        
    q_start = max(start, window_start)
    q_end = min(end, window_end)
    
    if q_start <= q_end:
        cur.execute("""
            SELECT COUNT(*) FROM bardata 
            WHERE symbol = %s AND exchange = %s AND interval = %s AND datetime >= %s AND datetime <= %s;
        """, (sym, exchange, interval, q_start, q_end))
        cnt = cur.fetchone()[0]
        if cnt > 0:
            all_bars_count += cnt
            spliced_details.append(f"{sym} inside [{q_start} to {q_end}]: {cnt} bars")

end_time = time.time()
print(f"Loaded spliced count: {all_bars_count} bars in {end_time - start_time:.4f} seconds!")
for d in spliced_details:
    print("  -", d)

cur.close()
conn.close()
