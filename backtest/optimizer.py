# -*- coding: utf-8 -*-
"""
多进程网格寻优优化器
"""

import os
import sys
import itertools
from datetime import datetime
from multiprocessing import Pool, cpu_count
from typing import List, Dict, Any, Tuple

# 引入本地模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data.db_manager import DBManager
from backtest.backtester import CtaBacktester
from backtest.analysis import calculate_statistics

def _backtest_worker(args: Tuple[Dict[str, Any], Dict[str, Any], str, str, str, str, str, Any, float]) -> Dict[str, Any]:
    """
    单个参数组合的回测 Worker。
    在子进程中自己连接数据库并加载数据以防止 Pickle 序列化冲突。
    """
    setting, db_conn_info, symbol, exchange, interval, start_str, end_str, strategy_class_name, start_capital = args
    
    # 获取真正的策略类
    # 为了防止 Pickle 传递类失败，我们从 sys.modules 中反射获取
    from strategy.strategies.double_ma_strategy import DoubleMaStrategy
    strategy_class = DoubleMaStrategy # 默认双均线策略（可按需扩展）

    # 实例化子进程专用 DBManager
    db = DBManager(
        dbname=db_conn_info["dbname"],
        user=db_conn_info["user"],
        password=db_conn_info["password"],
        host=db_conn_info["host"],
        port=db_conn_info["port"]
    )
    
    start = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")
    
    backtester = CtaBacktester(db)
    # 重定向日志输出，避免多进程终端疯狂乱印
    backtester.write_log = lambda msg: None
    
    # 模拟数据加载
    backtester.load_data(symbol, exchange, interval, start, end)
    
    if not backtester.bars:
        db.close()
        return {"setting": setting, "sharpe_ratio": 0.0, "total_return": 0.0, "max_drawdown": 0.0, "success": False}
        
    # 运行
    backtester.set_strategy(strategy_class, "opt_strategy", f"{symbol}.{exchange}", setting)
    backtester.run_backtest()
    
    # 计算绩效
    stats = calculate_statistics(backtester.trades, backtester.bars, start_capital=start_capital)
    
    db.close()
    
    return {
        "setting": setting,
        "total_return": stats.get("total_return", 0.0),
        "annualized_return": stats.get("annualized_return", 0.0),
        "max_drawdown": stats.get("max_drawdown", 0.0),
        "sharpe_ratio": stats.get("sharpe_ratio", 0.0),
        "total_trades": stats.get("total_trades", 0),
        "win_rate": stats.get("win_rate", 0.0),
        "success": True
    }

def run_grid_search(
    strategy_class: Any,
    db_conn_info: Dict[str, str],
    symbol: str,
    exchange: str,
    interval: str,
    start: datetime,
    end: datetime,
    parameter_grid: Dict[str, List[Any]],
    start_capital: float = 1000000.0,
    processes: int = None
) -> List[Dict[str, Any]]:
    """
    并发运行网格搜索。
    """
    if processes is None:
        processes = max(cpu_count() - 1, 1)

    print("="*50)
    print(f"🧬 启动多进程网格寻优，进程数: {processes}")
    print(f"标的: {symbol}.{exchange} | 区间: {start.strftime('%Y-%m-%d')} 至 {end.strftime('%Y-%m-%d')}")
    print("="*50)

    # 1. 展开参数网格为组合列表
    keys, values = zip(*parameter_grid.items())
    experiments = [dict(zip(keys, v)) for v in itertools.product(*values)]
    print(f"🔥 参数展开成功，共计 {len(experiments)} 组参数待回测")

    # 2. 转换为 worker 任务参数元组
    start_str = start.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end.strftime("%Y-%m-%d %H:%M:%S")
    
    tasks = []
    for setting in experiments:
        tasks.append((
            setting,
            db_conn_info,
            symbol,
            exchange,
            interval,
            start_str,
            end_str,
            strategy_class.__name__,
            start_capital
        ))

    # 3. 进程池并发运行
    results = []
    with Pool(processes=processes) as pool:
        for idx, res in enumerate(pool.imap_unordered(_backtest_worker, tasks)):
            if res.get("success"):
                print(f" [{idx+1}/{len(experiments)}] 参数 {res['setting']} => 夏普: {res['sharpe_ratio']:.2f} | 收益率: {res['total_return']*100:.1f}%")
                results.append(res)
            else:
                print(f" [{idx+1}/{len(experiments)}] 参数 {res['setting']} => 回测失败")

    # 4. 根据夏普比率降序排列
    results.sort(key=lambda x: x.get("sharpe_ratio", -999.0), reverse=True)
    return results
