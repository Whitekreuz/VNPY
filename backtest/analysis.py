# -*- coding: utf-8 -*-
"""
量化回测绩效分析模块
根据回测成交记录 (TradeData) 与 K 线历史序列 (BarData) 计算核心绩效指标。
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any
from core.models import TradeData, BarData, Direction, Offset

def calculate_statistics(
    trades: List[TradeData],
    bars: List[BarData],
    start_capital: float = 1000000.0,
    volume_multiple: int = 10,
    commission_rate: float = 0.0001  # 默认万分之一手续费
) -> Dict[str, Any]:
    """
    根据交易成交历史和 K 线历史，计算专业的量化绩效指标。
    """
    if not bars:
        return {}

    # 1. 整理 K 线为 DataFrame，按时间排序
    bar_data = []
    for b in bars:
        bar_data.append({
            "datetime": b.datetime,
            "date": b.datetime.date(),
            "close": b.close_price
        })
    df_bars = pd.DataFrame(bar_data).sort_values("datetime").reset_index(drop=True)

    # 2. 整理成交记录，建立时间戳到成交的映射
    trade_map = {}
    for t in trades:
        # 将相同分钟的交易归为一组
        dt_key = t.datetime.replace(second=0, microsecond=0)
        trade_map.setdefault(dt_key, []).append(t)

    # 3. 逐根 K 线模拟持仓与盈亏，计算逐分钟的权益曲线
    capital = start_capital
    pos = 0.0
    entry_price = 0.0
    equity_curve = []
    total_commission = 0.0

    # 记录已平仓的交易盈亏，用于胜率统计
    round_trip_pnls = []

    for idx, row in df_bars.iterrows():
        dt = row["datetime"]
        close_price = row["close"]
        
        # 检查当前分钟是否有交易发生
        current_trades = trade_map.get(dt, [])
        for t in current_trades:
            # 计算手续费
            trade_value = t.price * t.volume * volume_multiple
            commission = trade_value * commission_rate
            total_commission += commission
            capital -= commission

            # 区分开平仓
            is_open = (t.offset == Offset.OPEN)
            is_long = (t.direction == Direction.LONG)

            if is_open:
                # 开仓：更新平均持仓成本
                new_pos = pos + (t.volume if is_long else -t.volume)
                if pos == 0:
                    entry_price = t.price
                else:
                    # 只有方向相同时才平均成本
                    if (pos > 0 and is_long) or (pos < 0 and not is_long):
                        entry_price = (abs(pos) * entry_price + t.volume * t.price) / abs(new_pos)
                pos = new_pos
            else:
                # 平仓：计算已实现盈亏并加到账户资金上
                if pos > 0 and not is_long:  # 多单平仓
                    closed_vol = min(pos, t.volume)
                    pnl = (t.price - entry_price) * closed_vol * volume_multiple
                    capital += pnl
                    pos -= closed_vol
                    round_trip_pnls.append(pnl - (commission * 2))  # 估算双边手续费扣除后的净盈亏
                elif pos < 0 and is_long:   # 空单平仓
                    closed_vol = min(abs(pos), t.volume)
                    pnl = (entry_price - t.price) * closed_vol * volume_multiple
                    capital += pnl
                    pos += closed_vol
                    round_trip_pnls.append(pnl - (commission * 2))

        # 计算当前 Bar 结束时的总权益 (Equity = 现金 + 持仓未实现盈亏)
        unrealized_pnl = 0.0
        if pos != 0:
            unrealized_pnl = pos * (close_price - entry_price) * volume_multiple
            
        equity = capital + unrealized_pnl
        equity_curve.append({
            "datetime": dt,
            "date": row["date"],
            "equity": equity,
            "close": close_price
        })

    df_equity = pd.DataFrame(equity_curve)

    # 4. 计算每日权益 (Daily Equity) 作为核心指标计算基础
    df_daily = df_equity.groupby("date").last().reset_index()
    df_daily["return"] = df_daily["equity"].pct_change().fillna(0.0)

    # 5. 计算具体量化统计指标
    total_days = len(df_daily)
    start_equity = start_capital
    end_equity = df_daily["equity"].iloc[-1]
    total_return = (end_equity - start_equity) / start_equity
    
    # 年化收益率 (假设一年 240 个交易日)
    annualized_return = total_return * (240 / max(total_days, 1))

    # 最大回撤 (Max Drawdown)
    df_daily["cum_max"] = df_daily["equity"].cummax()
    df_daily["drawdown"] = (df_daily["equity"] - df_daily["cum_max"]) / df_daily["cum_max"]
    max_drawdown = df_daily["drawdown"].min()

    # 夏普比率 (Sharpe Ratio) (假设无风险收益率为 0%)
    daily_std = df_daily["return"].std()
    if daily_std > 0:
        sharpe_ratio = (df_daily["return"].mean() / daily_std) * np.sqrt(240)
    else:
        sharpe_ratio = 0.0

    # 索提诺比率 (Sortino Ratio)
    downside_returns = df_daily["return"][df_daily["return"] < 0]
    downside_std = downside_returns.std()
    if downside_std > 0:
        sortino_ratio = (df_daily["return"].mean() / downside_std) * np.sqrt(240)
    else:
        sortino_ratio = 0.0

    # 胜率与盈亏比
    wins = [p for p in round_trip_pnls if p > 0]
    losses = [p for p in round_trip_pnls if p <= 0]
    total_trades = len(round_trip_pnls)
    win_rate = len(wins) / total_trades if total_trades > 0 else 0.0
    
    avg_win = np.mean(wins) if wins else 0.0
    avg_loss = abs(np.mean(losses)) if losses else 0.0
    profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0.0

    return {
        "start_capital": start_capital,
        "end_equity": end_equity,
        "total_return": total_return,
        "annualized_return": annualized_return,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
        "total_trades": total_trades,
        "win_rate": win_rate,
        "profit_loss_ratio": profit_loss_ratio,
        "total_commission": total_commission,
        "round_trip_pnls": round_trip_pnls,
        "daily_equity": df_daily[["date", "equity", "return", "drawdown"]]
    }
