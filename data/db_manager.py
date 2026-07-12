import pandas as pd
from typing import List
from datetime import datetime
from core.models import BarData

try:
    import psycopg2
    from psycopg2.extras import execute_values
    PSYCOPG2_INSTALLED = True
except ImportError:
    PSYCOPG2_INSTALLED = False

class DBManager:
    """PostgreSQL 数据库管理模块，用于高效存储 K线 和 Tick 数据"""
    def __init__(self, dbname, user, password, host="localhost", port=5432):
        if not PSYCOPG2_INSTALLED:
            raise ImportError("未安装 psycopg2，请运行: pip install psycopg2-binary")
            
        self.conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        self.create_tables()
        self.create_mapping_table()

    def create_tables(self):
        """建表操作"""
        with self.conn.cursor() as cur:
            # 创建 K线表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bardata (
                    symbol VARCHAR(50),
                    exchange VARCHAR(50),
                    datetime TIMESTAMP,
                    interval VARCHAR(10),
                    volume FLOAT,
                    turnover FLOAT,
                    open_interest FLOAT,
                    open_price FLOAT,
                    high_price FLOAT,
                    low_price FLOAT,
                    close_price FLOAT,
                    PRIMARY KEY (symbol, exchange, interval, datetime)
                );
            """)
            # 如果安装了 TimescaleDB，强烈建议在数据库中执行: 
            # SELECT create_hypertable('bardata', 'datetime', if_not_exists => TRUE);
            self.conn.commit()

    def create_mapping_table(self):
        """建表操作: 主力合约映射表"""
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS main_contract_mapping (
                    underlying VARCHAR(50),
                    exchange VARCHAR(50),
                    date DATE,
                    main_symbol VARCHAR(50),
                    sub_symbol VARCHAR(50),
                    PRIMARY KEY (underlying, exchange, date)
                );
            """)
            self.conn.commit()

    def save_bar_data(self, bars: List[BarData]):
        if not bars:
            return
            
        query = """
            INSERT INTO bardata (symbol, exchange, datetime, interval, volume, turnover, open_interest, open_price, high_price, low_price, close_price)
            VALUES %s
            ON CONFLICT (symbol, exchange, interval, datetime) DO UPDATE SET
                volume = EXCLUDED.volume,
                turnover = EXCLUDED.turnover,
                open_interest = EXCLUDED.open_interest,
                open_price = EXCLUDED.open_price,
                high_price = EXCLUDED.high_price,
                low_price = EXCLUDED.low_price,
                close_price = EXCLUDED.close_price;
        """
        
        values = [
            (b.symbol, b.exchange, b.datetime, b.interval, b.volume, b.turnover, b.open_interest, b.open_price, b.high_price, b.low_price, b.close_price)
            for b in bars
        ]
        
        with self.conn.cursor() as cur:
            execute_values(cur, query, values)
            self.conn.commit()

    def load_bar_data(self, symbol: str, exchange: str, interval: str, start: datetime, end: datetime) -> List[BarData]:
        # Parse symbol to check if it's a specific monthly contract (e.g. SR2605, AG2612)
        variety = "".join([c for c in symbol if c.isalpha()])
        digits = "".join([c for c in symbol if c.isdigit()])
        
        # Splicing applies if digits is length 4 and symbol is not continuous (ends in 88, 888, 99)
        if len(digits) == 4 and not digits.endswith("88") and not digits.endswith("888") and not digits.endswith("99"):
            try:
                y_target = int(digits[:2])
                m_target = int(digits[2:])
                
                # Construct candidate symbols from year 18 to 29 (covering 2018 to 2029)
                candidates = [f"{variety}{yy:02d}{m_target:02d}" for yy in range(18, 30)]
                
                bars = []
                query = """
                    SELECT symbol, exchange, datetime, interval, volume, turnover, open_interest, open_price, high_price, low_price, close_price
                    FROM bardata
                    WHERE symbol = %s AND exchange = %s AND interval = %s AND datetime >= %s AND datetime <= %s
                    ORDER BY datetime ASC;
                """
                
                with self.conn.cursor() as cur:
                    for sym in candidates:
                        sym_digits = "".join([c for c in sym if c.isdigit()])
                        yy = int(sym_digits[:2])
                        mm = int(sym_digits[2:])
                        
                        delivery_year = 2000 + yy
                        
                        # Splicing window boundaries: active from MM-16 of previous year to MM-15 of delivery year
                        window_start = datetime(delivery_year - 1, mm, 16, 0, 0, 0)
                        window_end = datetime(delivery_year, mm, 15, 23, 59, 59)
                        
                        # Boundary extensions for query range
                        if sym == candidates[0]:
                            window_start = start
                        if sym == candidates[-1]:
                            window_end = end
                            
                        q_start = max(start, window_start)
                        q_end = min(end, window_end)
                        
                        if q_start <= q_end:
                            cur.execute(query, (sym, exchange, interval, q_start, q_end))
                            rows = cur.fetchall()
                            for row in rows:
                                bars.append(BarData(
                                    symbol=row[0], exchange=row[1], datetime=row[2], interval=row[3],
                                    volume=row[4], turnover=row[5], open_interest=row[6],
                                    open_price=row[7], high_price=row[8], low_price=row[9], close_price=row[10]
                                ))
                if bars:
                    return bars
            except Exception as e:
                print(f"Splicing failed: {e}. Fallback to direct query.")

        # Fallback / Default: Direct query for single symbol
        query = """
            SELECT symbol, exchange, datetime, interval, volume, turnover, open_interest, open_price, high_price, low_price, close_price
            FROM bardata
            WHERE symbol = %s AND exchange = %s AND interval = %s AND datetime >= %s AND datetime <= %s
            ORDER BY datetime ASC;
        """
        
        with self.conn.cursor() as cur:
            cur.execute(query, (symbol, exchange, interval, start, end))
            rows = cur.fetchall()
            
        bars = []
        for row in rows:
            bars.append(BarData(
                symbol=row[0], exchange=row[1], datetime=row[2], interval=row[3],
                volume=row[4], turnover=row[5], open_interest=row[6],
                open_price=row[7], high_price=row[8], low_price=row[9], close_price=row[10]
            ))
        return bars


    def get_max_datetime(self, symbol: str, exchange: str, interval: str) -> datetime:
        query = """
            SELECT MAX(datetime)
            FROM bardata
            WHERE symbol = %s AND exchange = %s AND interval = %s;
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (symbol, exchange, interval))
            row = cur.fetchone()
            if row and row[0]:
                return row[0]
            return None

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()

