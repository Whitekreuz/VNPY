# -*- coding: utf-8 -*-
import os
import sys
import json
import psycopg2
import uvicorn
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import numpy as np
import pandas as pd

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv()

from data.db_manager import DBManager
from backtest.backtester import CtaBacktester
from backtest.analysis import calculate_statistics
from strategy.strategies.double_ma_strategy import DoubleMaStrategy


app = FastAPI(title="Moderixest Trade Quant Dashboard")

# Define static directory path
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui"))
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ─── DB helpers ────────────────────────────────────────────────────────────────
def get_db(db_name: str = None) -> DBManager:
    load_db_name = db_name or os.getenv("PG_DBNAME_PROD", "quant_db_prod")
    return DBManager(
        dbname=load_db_name,
        user=os.getenv("PG_USER", "postgres"),
        password=os.getenv("PG_PASSWORD", ""),
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", 5432))
    )

def get_raw_conn(db_name: str = None):
    """Get a raw psycopg2 connection for complex queries."""
    load_db_name = db_name or os.getenv("PG_DBNAME_PROD", "quant_db_prod")
    return psycopg2.connect(
        dbname=load_db_name,
        user=os.getenv("PG_USER", "postgres"),
        password=os.getenv("PG_PASSWORD", ""),
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", 5432))
    )

# ─── Load JSON config once at startup ─────────────────────────────────────────
CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "futures_symbols.json"))
_config_cache = None

def load_config():
    global _config_cache
    if _config_cache is None:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            _config_cache = json.load(f)
    return _config_cache

SECTOR_NAMES = {
    "oils_and_oilseeds": "油脂油料",
    "agriculture": "农产品",
    "new_energy": "新能源",
    "base_metals": "有色金属",
    "energy_chemicals": "能源化工",
    "ferrous_metals": "黑色建材",
    "shipping_light": "航运轻工",
    "precious_metals": "贵金属",
    "crude_oil_products": "原油油品",
    "financials": "金融期指"
}

# Cache of DB symbols to avoid repeated heavy queries
_db_symbols_cache = None
_db_symbols_cache_time = None
CACHE_TTL_SECONDS = 300  # 5 minute cache

def get_db_symbols():
    """Get distinct symbols from DB with caching (5 min TTL)."""
    global _db_symbols_cache, _db_symbols_cache_time
    now = datetime.now()
    if _db_symbols_cache is not None and _db_symbols_cache_time is not None:
        if (now - _db_symbols_cache_time).total_seconds() < CACHE_TTL_SECONDS:
            return _db_symbols_cache
    
    conn = get_raw_conn()
    cur = conn.cursor()
    # Fast query using PostgreSQL loose index scan (recursive CTE) for 27x speedup
    cur.execute("""
        WITH RECURSIVE t AS (
            (SELECT symbol FROM bardata WHERE interval = '1m' ORDER BY symbol LIMIT 1)
            UNION ALL
            SELECT (SELECT symbol FROM bardata WHERE symbol > t.symbol AND interval = '1m' ORDER BY symbol LIMIT 1)
            FROM t
            WHERE t.symbol IS NOT NULL
        )
        SELECT symbol FROM t WHERE symbol IS NOT NULL;
    """)
    symbols = set(r[0] for r in cur.fetchall())
    conn.close()
    _db_symbols_cache = symbols
    _db_symbols_cache_time = now
    return symbols


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/")
def get_index():
    """Serve index.html"""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_path):
        with open(index_path, "w", encoding="utf-8") as f:
            f.write("<h1>UI Directory Initialized</h1>")
    return FileResponse(index_path)


@app.get("/api/symbols")
def get_symbols():
    """
    Return 10-sector categorized symbols.
    Contract list shows:
      - Continuous contracts: AG88, AG888, AG99
      - Month-aggregated codes: AG02, AG04, ... (each spans all historical years of that month)
    Filtered against actual DB data so only months with real data are shown.
    """
    try:
        config_data = load_config()
        db_symbols = get_db_symbols()

        final_categorized = {}

        for sector_key, sector_info in config_data.items():
            sector_name = SECTOR_NAMES.get(sector_key, sector_key)
            symbols_dict = sector_info.get("symbols", {})
            sector_data = {}

            for symbol_key, sym_info in symbols_dict.items():
                variety_code = symbol_key.split(".")[0].upper()
                variety_chinese = sym_info.get("name", variety_code)
                variety_key = f"{variety_chinese} ({variety_code})"
                months = sym_info.get("months", [])
                continuous = sym_info.get("continuous", ["88", "99"])

                contracts = []

                # Continuous contracts (e.g. AG88, AG888, AG99) - only if in DB
                for c in continuous:
                    sym = f"{variety_code}{c}"
                    if sym in db_symbols:
                        contracts.append(sym)

                # Month-aggregated codes: only include months that have ≥1 actual contract in DB
                for mm in months:
                    # Check if any year has data for this month
                    has_data = any(
                        f"{variety_code}{yy:02d}{mm}" in db_symbols
                        for yy in range(15, 29)
                    )
                    if has_data:
                        # Month aggregated code: e.g. SR05, AG02, RB10
                        contracts.append(f"{variety_code}{mm}")

                if contracts:
                    sector_data[variety_key] = contracts

            if sector_data:
                final_categorized[sector_name] = sector_data

        return {"status": "success", "data": final_categorized}

    except Exception as e:
        fallback_data = {
            "贵金属": {
                "白银 (AG)": ["AG88", "AG99", "AG02", "AG04", "AG06", "AG08", "AG10", "AG12"],
                "黄金 (AU)": ["AU88", "AU99", "AU02", "AU04", "AU06", "AU08", "AU10", "AU12"]
            }
        }
        return {"status": "error", "message": str(e), "data": fallback_data}


@app.get("/api/kline")
def get_kline(
    symbol: str = Query(..., description="Contract symbol. Can be: AG88 (continuous), AG2506 (specific), or AG06 (month-aggregated = all historical June contracts spliced)"),
    exchange: str = Query(..., description="Exchange e.g. CZC, SHF, DCE"),
    interval: str = Query("1d", description="Interval: 1m, 5m, 15m, 30m, 1h, 4h, 1d"),
    start: str = Query(None, description="Start date YYYY-MM-DD"),
    end: str = Query(None, description="End date YYYY-MM-DD"),
    limit: int = Query(500, description="Max bars to return (default 500, max 20000)")
):
    """
    Fetch OHLCV K-line data by aggregating 1m bars from DB.
    Supports: 1m, 5m, 15m, 30m, 1h, 4h, 1d resampling.
    For month-aggregated symbols (e.g. SR05), splices all historical yearly contracts.
    """
    try:
        limit = min(limit, 20000)

        # Parse date range defaults
        end_dt = datetime.now() if end is None else datetime.strptime(end, "%Y-%m-%d")
        if start is None:
            if interval == "1d":
                start_dt = end_dt - timedelta(days=365 * 8)
            elif interval in ("1h", "4h"):
                start_dt = end_dt - timedelta(days=365)
            else:
                start_dt = end_dt - timedelta(days=90)
        else:
            start_dt = datetime.strptime(start, "%Y-%m-%d")

        # Detect if this is a month-aggregated code:
        # Pattern: variety code (letters) + exactly 2 digits (01-12)
        # e.g. SR05, AG02, RB10 — NOT SR2505 (4 digits) or AG88 (suffix contains 8)
        import re
        is_month_aggregated = False
        month_suffix = None
        variety_prefix = None

        m = re.match(r'^([A-Z]+)(\d{2})$', symbol)
        if m:
            prefix = m.group(1)
            suffix = m.group(2)
            # Confirm it's a month (01-12), not a continuous code like 88/99
            if 1 <= int(suffix) <= 12:
                is_month_aggregated = True
                variety_prefix = prefix
                month_suffix = suffix

        # Map interval to seconds
        interval_seconds = {
            "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
            "1h": 3600, "4h": 14400, "1d": 86400
        }
        secs = interval_seconds.get(interval, 86400)

        conn = get_raw_conn()
        cur = conn.cursor()

        if is_month_aggregated:
            # Month-splice: Find matching symbols in cache first
            # e.g., variety_prefix = "AG", month_suffix = "06" -> match "AG1806", "AG1906" etc.
            pattern_regex = re.compile(f"^{re.escape(variety_prefix)}\\d{{2}}{month_suffix}$")
            db_symbols = get_db_symbols()
            matching_symbols = [s for s in db_symbols if pattern_regex.match(s)]
            
            if not matching_symbols:
                conn.close()
                return {
                    "status": "success",
                    "symbol": symbol,
                    "exchange": exchange,
                    "interval": interval,
                    "is_spliced": True,
                    "count": 0,
                    "data": []
                }

            sql = """
                SELECT
                    to_timestamp(floor(EXTRACT(epoch FROM datetime) / %(secs)s) * %(secs)s) AS bar_time,
                    (array_agg(open_price ORDER BY datetime))[1]      AS open_price,
                    MAX(high_price)                                     AS high_price,
                    MIN(low_price)                                      AS low_price,
                    (array_agg(close_price ORDER BY datetime DESC))[1] AS close_price,
                    SUM(volume)                                         AS volume,
                    (array_agg(open_interest ORDER BY datetime DESC))[1] AS open_interest
                FROM bardata
                WHERE symbol = ANY(%(symbols)s)
                  AND exchange = %(exchange)s
                  AND interval = '1m'
                  AND datetime >= %(start)s
                  AND datetime < %(end)s
                GROUP BY bar_time
                ORDER BY bar_time
            """
            cur.execute(sql, {
                "secs": secs,
                "exchange": exchange,
                "symbols": matching_symbols,
                "start": start_dt,
                "end": end_dt
            })
        else:
            # Exact contract query (continuous like AG88 or specific like AG2506)
            sql = """
                SELECT
                    to_timestamp(floor(EXTRACT(epoch FROM datetime) / %(secs)s) * %(secs)s) AS bar_time,
                    (array_agg(open_price ORDER BY datetime))[1]      AS open_price,
                    MAX(high_price)                                     AS high_price,
                    MIN(low_price)                                      AS low_price,
                    (array_agg(close_price ORDER BY datetime DESC))[1] AS close_price,
                    SUM(volume)                                         AS volume,
                    (array_agg(open_interest ORDER BY datetime DESC))[1] AS open_interest
                FROM bardata
                WHERE symbol = %(symbol)s
                  AND exchange = %(exchange)s
                  AND interval = '1m'
                  AND datetime >= %(start)s
                  AND datetime < %(end)s
                GROUP BY bar_time
                ORDER BY bar_time
            """
            cur.execute(sql, {
                "secs": secs,
                "symbol": symbol,
                "exchange": exchange,
                "start": start_dt,
                "end": end_dt
            })

        rows = cur.fetchall()
        conn.close()

        # Trim to limit (return most recent `limit` bars)
        if len(rows) > limit:
            rows = rows[-limit:]

        data = []
        for row in rows:
            bar_time, o, h, l, c, v, oi = row
            data.append({
                "t": bar_time.strftime("%Y-%m-%d %H:%M:%S"),
                "o": round(float(o), 4) if o else 0,
                "h": round(float(h), 4) if h else 0,
                "l": round(float(l), 4) if l else 0,
                "c": round(float(c), 4) if c else 0,
                "v": round(float(v), 0) if v else 0,
                "oi": round(float(oi), 0) if oi else 0
            })

        return {
            "status": "success",
            "symbol": symbol,
            "exchange": exchange,
            "interval": interval,
            "is_spliced": is_month_aggregated,
            "count": len(data),
            "data": data
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/kline/varieties")
def get_kline_varieties():
    """
    Return a flat list of {sector, variety_name, variety_code, exchange, contracts}
    for the K-line chart symbol selector.
    """
    try:
        config_data = load_config()
        db_symbols = get_db_symbols()

        result = []
        for sector_key, sector_info in config_data.items():
            sector_name = SECTOR_NAMES.get(sector_key, sector_key)
            for symbol_key, sym_info in sector_info.get("symbols", {}).items():
                parts = symbol_key.split(".")
                variety_code = parts[0].upper()
                exchange = parts[1] if len(parts) > 1 else ""
                variety_chinese = sym_info.get("name", variety_code)
                months = sym_info.get("months", [])
                continuous = sym_info.get("continuous", ["88", "99"])

                contracts = []
                for c in continuous:
                    sym = f"{variety_code}{c}"
                    if sym in db_symbols:
                        contracts.append(sym)
                for yy in range(15, 29):
                    for mm in months:
                        sym = f"{variety_code}{yy:02d}{mm}"
                        if sym in db_symbols:
                            contracts.append(sym)

                if contracts:
                    result.append({
                        "sector": sector_name,
                        "name": variety_chinese,
                        "code": variety_code,
                        "exchange": exchange,
                        "contracts": contracts
                    })

        return {"status": "success", "data": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/backtest")
def run_backtest(payload: Dict[str, Any]):
    """Run portfolio backtest"""
    try:
        symbols = payload.get("symbols", [])
        start_str = payload.get("start", "2026-01-01")
        end_str = payload.get("end", "2026-07-01")
        params = payload.get("params", {"fast_window": 10, "slow_window": 30})
        capital = payload.get("capital", 1000000.0)
        commission = payload.get("commission_rate", 0.0001)

        start_dt = datetime.strptime(start_str, "%Y-%m-%d")
        end_dt = datetime.strptime(end_str, "%Y-%m-%d") + timedelta(days=1) - timedelta(microseconds=1)

        db_manager = get_db()
        symbol_daily_df_list = []
        individual_results = {}

        for symbol_str in symbols:
            conn = get_raw_conn()
            cur = conn.cursor()
            cur.execute("SELECT exchange FROM bardata WHERE symbol = %s LIMIT 1", (symbol_str,))
            row = cur.fetchone()
            cur.close()
            conn.close()
            
            exchange = row[0] if row else "SHFE"

            bt = CtaBacktester(db_manager)
            bt.load_data(symbol_str, exchange, "1m", start_dt, end_dt)
            
            vt_symbol = f"{symbol_str}.{exchange}"
            bt.set_strategy(DoubleMaStrategy, f"DoubleMA_{symbol_str}", vt_symbol, params)
            bt.run_backtest()

            stats = calculate_statistics(bt.trades, bt.bars, start_capital=capital, commission_rate=commission)
            
            if stats:
                individual_results[symbol_str] = {
                    "total_days": int(stats.get("total_days", 0)),
                    "total_trades": int(stats.get("total_trades", 0)),
                    "total_return": float(stats.get("total_return", 0)),
                    "annual_return": float(stats.get("annualized_return", 0)),
                    "max_drawdown": float(stats.get("max_drawdown", 0)),
                    "sharpe_ratio": float(stats.get("sharpe_ratio", 0)),
                    "win_rate": float(stats.get("win_rate", 0))
                }
                
                df_d = stats["daily_equity"].copy()
                df_d["symbol"] = symbol_str
                symbol_daily_df_list.append(df_d)

        if not symbol_daily_df_list:
            return {
                "status": "error",
                "message": "No data or backtest failed for all selected symbols"
            }

        # Combine daily equities
        df_all = pd.concat(symbol_daily_df_list)
        df_all["pnl"] = df_all["equity"] - capital
        
        df_portfolio = df_all.groupby("date")["pnl"].sum().reset_index()
        df_portfolio["equity"] = capital + df_portfolio["pnl"]
        df_portfolio = df_portfolio.sort_values("date").reset_index(drop=True)
        
        df_portfolio["return"] = df_portfolio["equity"].pct_change().fillna(0.0)
        df_portfolio["cum_max"] = df_portfolio["equity"].cummax()
        df_portfolio["drawdown"] = (df_portfolio["equity"] - df_portfolio["cum_max"]) / df_portfolio["cum_max"]
        
        portfolio_total_return = (df_portfolio["equity"].iloc[-1] - capital) / capital
        portfolio_max_drawdown = df_portfolio["drawdown"].min()
        
        daily_std = df_portfolio["return"].std()
        portfolio_sharpe = (df_portfolio["return"].mean() / daily_std) * np.sqrt(240) if daily_std > 0 else 0.0
        
        equity_series = []
        for _, r in df_portfolio.iterrows():
            equity_series.append({
                "date": str(r["date"]),
                "equity": float(r["equity"]),
                "drawdown": float(r["drawdown"])
            })

        avg_win_rate = np.mean([res["win_rate"] for res in individual_results.values()]) if individual_results else 0.0

        portfolio_summary = {
            "total_return": float(portfolio_total_return),
            "sharpe_ratio": float(portfolio_sharpe),
            "max_drawdown": float(portfolio_max_drawdown),
            "win_rate": float(avg_win_rate),
            "equity_series": equity_series,
            "individual": individual_results
        }

        return {
            "status": "success",
            "message": "Backtest completed",
            "data": portfolio_summary
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/backtest/save")
def save_strategy_stub(payload: Dict[str, Any]):
    """Stub endpoint for strategy pool saving"""
    return {
        "status": "success",
        "message": "Stub strategy pool save completed successfully",
        "payload_received": payload
    }

@app.post("/api/db/sync")
def sync_db_stub():
    """Stub endpoint for database synchronization"""
    return {
        "status": "success",
        "message": "Stub DB sync completed successfully"
    }

if __name__ == "__main__":
    uvicorn.run("web_server:app", host="127.0.0.1", port=8000, reload=True)
