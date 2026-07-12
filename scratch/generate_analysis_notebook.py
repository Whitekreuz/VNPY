# -*- coding: utf-8 -*-
import json
import os

notebook = {
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# Phase 3.5: 回测绩效分析与多进程参数寻优可视化大盘\n",
    "\n",
    "本 Notebook 展示了对系统内双均线策略在白银高频历史分钟线上的回测结果。主要包含以下部分：\n",
    "1. **历史回测运行**：从本地数据库拉取白银数据，加载策略跑通回测。\n",
    "2. **回测绩效指标计算**：计算年化收益率、最大回撤、夏普比率、索提诺比率、胜率等。\n",
    "3. **专业图表可视化**：使用 `matplotlib` 绘制**资金曲线**、**回撤变化**以及 **K 线买卖信号标记图**。\n",
    "4. **多进程参数网格搜索**：并发寻优最佳参数组合。"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 1. 准备工作与数据回测运行"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "import sys\n",
    "import os\n",
    "from datetime import datetime, timedelta\n",
    "import pandas as pd\n",
    "import matplotlib.pyplot as plt\n",
    "import numpy as np\n",
    "from dotenv import load_dotenv\n",
    "\n",
    "# 确保项目根目录在导入路径中\n",
    "sys.path.insert(0, os.path.abspath('.'))\n",
    "load_dotenv()\n",
    "\n",
    "from data.db_manager import DBManager\n",
    "from backtest.backtester import CtaBacktester\n",
    "from strategy.strategies.double_ma_strategy import DoubleMaStrategy\n",
    "from backtest.analysis import calculate_statistics\n",
    "from backtest.optimizer import run_grid_search\n",
    "from core.models import Direction, Offset\n",
    "\n",

    "# 1. 连接数据库\n",
    "db_name = os.getenv(\"PG_DBNAME_PROD\", \"quant_db_prod\") # 使用生产库\n",

    "db_user = os.getenv(\"PG_USER\", \"postgres\")\n",
    "db_pass = os.getenv(\"PG_PASSWORD\", \"\")\n",
    "db_host = os.getenv(\"PG_HOST\", \"localhost\")\n",
    "db_port = os.getenv(\"PG_PORT\", \"5432\")\n",
    "\n",
    "db = DBManager(dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port)\n",
    "print(f\"✅ 成功连接数据库: {db_name}\")\n",
    "\n",
    "# 2. 初始化回测引擎\n",
    "backtester = CtaBacktester(db)\n",
    "\n",
    "# 寻找数据库中已有的合约数据\n",
    "# 白银主力连续 AG88\n",
    "symbol = \"AG88\"\n",
    "exchange = \"SHF\"\n",
    "interval = \"1m\"\n",
    "start_date = datetime(2026, 1, 1)\n",
    "end_date = datetime(2026, 7, 1)\n",
    "\n",
    "backtester.load_data(symbol, exchange, interval, start_date, end_date)\n"
,
    "\n",
    "if not backtester.bars:\n",
    "    print(f\"⚠️ 警告: 数据库中没有 {symbol}.{exchange} 在该时间段的数据。\")\n",
    "    # 自动降低要求，查询全部数据中最大时间，并向前取30天进行测试\n",
    "    max_dt = db.get_max_datetime(symbol, exchange, interval)\n",
    "    if max_dt:\n",
    "        start_date = max_dt - timedelta(days=30)\n",
    "        end_date = max_dt\n",
    "        print(f\"🔄 自动对齐到最新数据时段: {start_date} 至 {end_date}\")\n",
    "        backtester.load_data(symbol, exchange, interval, start_date, end_date)\n",
    "    else:\n",
    "        print(\"❌ 数据库为空！请先从天勤或米筐运行脚本下载历史数据到本地数据库中。\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 2. 运行双均线策略回测"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "if backtester.bars:\n",
    "    # 绑定策略：快线 10，慢线 30\n",
    "    backtester.set_strategy(DoubleMaStrategy, \"DoubleMa_Demo\", f\"{symbol}.{exchange}\", {\"fast_window\": 10, \"slow_window\": 30})\n",
    "    backtester.run_backtest()\n",
    "    print(f\"回测完成，共产生 {len(backtester.trades)} 笔交易。\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 3. 计算绩效指标报告"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "if backtester.bars and backtester.trades:\n",
    "    # 计算绩效统计\n",
    "    stats = calculate_statistics(backtester.trades, backtester.bars, start_capital=1000000.0, volume_multiple=15)\n",
    "    \n",
    "    # 打印排版整齐的报告\n",
    "    print(\"=\"*45)\n",
    "    print(f\"📊 【回测绩效报告】 {symbol}.{exchange} \")\n",
    "    print(\"=\"*45)\n",
    "    print(f\" 初始资金:      {stats['start_capital']:,.2f} 元\")\n",
    "    print(f\" 期末权益:      {stats['end_equity']:,.2f} 元\")\n",
    "    print(f\" 总收益率:      {stats['total_return']*100:.2f}%\")\n",
    "    print(f\" 年化收益率:    {stats['annualized_return']*100:.2f}%\")\n",
    "    print(f\" 最大回撤:      {stats['max_drawdown']*100:.2f}%\")\n",
    "    print(f\" 夏普比率:      {stats['sharpe_ratio']:.2f}\")\n",
    "    print(f\" 索提诺比率:    {stats['sortino_ratio']:.2f}\")\n",
    "    print(f\" 总交易笔数:    {stats['total_trades']} 笔\")\n",
    "    print(f\" 胜率:          {stats['win_rate']*100:.2f}%\")\n",
    "    print(f\" 盈亏比:        {stats['profit_loss_ratio']:.2f}\")\n",
    "    print(f\" 累计手续费:    {stats['total_commission']:,.2f} 元\")\n",
    "    print(\"=\"*45)\n",
    "else:\n",
    "    print(\"由于数据或成交为空，跳过绩效统计\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 4. 回测可视化大图展示"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "if backtester.bars and backtester.trades:\n",
    "    # 设置中文字体与绘图风格\n",
    "    plt.style.use('seaborn-v0_8-darkgrid' if 'seaborn-v0_8-darkgrid' in plt.style.available else 'default')\n",
    "    plt.rcParams['font.family'] = 'sans-serif'\n",
    "    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun', 'STHeiti', 'sans-serif']\n",
    "    plt.rcParams['axes.unicode_minus'] = False\n",
    "    \n",
    "    df_d = stats[\"daily_equity\"]\n",
    "    \n",
    "    # 图 1: 权益曲线与回撤走势\n",
    "    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), sharex=True, gridspec_kw={'height_ratios': [3, 1]})\n",
    "    \n",
    "    ax1.plot(df_d[\"date\"], df_d[\"equity\"], color=\"#007acc\", linewidth=2, label=\"账户总权益 (Equity)\")\n",
    "    ax1.set_title(f\"白银 {symbol} 均线策略回测资金净值曲线\", fontsize=16, fontweight='bold', pad=15)\n",
    "    ax1.set_ylabel(\"账户权益 (元)\", fontsize=12)\n",
    "    ax1.legend(loc=\"upper left\", fontsize=11)\n",
    "    \n",
    "    ax2.fill_between(df_d[\"date\"], df_d[\"drawdown\"] * 100, 0, color=\"#e05a47\", alpha=0.3, label=\"回撤比率 (Drawdown)\")\n",
    "    ax2.plot(df_d[\"date\"], df_d[\"drawdown\"] * 100, color=\"#e05a47\", linewidth=1)\n",
    "    ax2.set_ylabel(\"回撤幅度 (%)\", fontsize=12)\n",
    "    ax2.set_xlabel(\"日期\", fontsize=12)\n",
    "    ax2.legend(loc=\"lower left\", fontsize=11)\n",
    "    \n",
    "    plt.tight_layout()\n",
    "    plt.show()\n",
    "\n",
    "    # 图 2: 策略买卖点标记图\n",
    "    # 提取策略自己记录的 60m 历史 K 线\n",
    "    history_bars = backtester.strategy.history_bars\n",
    "    if history_bars:\n",
    "        k_data = []\n",
    "        for hb in history_bars:\n",
    "            k_data.append({\"datetime\": hb.datetime, \"close\": hb.close_price})\n",
    "        df_k = pd.DataFrame(k_data).sort_values(\"datetime\").reset_index(drop=True)\n",
    "        \n",
    "        plt.figure(figsize=(15, 7))\n",
    "        plt.plot(df_k[\"datetime\"], df_k[\"close\"], color=\"#555555\", alpha=0.6, label=\"小时线收盘价 (Close)\")\n",
    "        \n",
    "        # 绘制成交买卖点\n",
    "        # 匹配最接近的 60m K 线时间点进行标记\n",
    "        for t in backtester.trades:\n",
    "            # 寻找时间戳最接近的 60m 节点\n",
    "            diffs = np.abs((df_k[\"datetime\"] - t.datetime).dt.total_seconds())\n",
    "            closest_idx = diffs.idxmin()\n",
    "            trade_dt = df_k.loc[closest_idx, \"datetime\"]\n",
    "            trade_price = t.price\n",
    "            \n",
    "            # 根据买卖开平类型设置箭头和颜色\n",
    "            if t.direction == Direction.LONG and t.offset == Offset.OPEN:\n",
    "                plt.scatter(trade_dt, trade_price, color=\"red\", marker=\"^\", s=150, label=\"买开 (Buy Open)\" if \"买开 (Buy Open)\" not in plt.gca().get_legend_handles_labels()[1] else \"\")\n",
    "            elif t.direction == Direction.SHORT and t.offset == Offset.CLOSE:\n",
    "                plt.scatter(trade_dt, trade_price, color=\"blue\", marker=\"v\", s=150, label=\"买平 (Cover Close)\" if \"买平 (Cover Close)\" not in plt.gca().get_legend_handles_labels()[1] else \"\")\n",
    "            elif t.direction == Direction.SHORT and t.offset == Offset.OPEN:\n",
    "                plt.scatter(trade_dt, trade_price, color=\"green\", marker=\"v\", s=150, label=\"卖开 (Short Open)\" if \"卖开 (Short Open)\" not in plt.gca().get_legend_handles_labels()[1] else \"\")\n",
    "            elif t.direction == Direction.LONG and t.offset == Offset.CLOSE:\n",
    "                plt.scatter(trade_dt, trade_price, color=\"orange\", marker=\"^\", s=150, label=\"卖平 (Sell Close)\" if \"卖平 (Sell Close)\" not in plt.gca().get_legend_handles_labels()[1] else \"\")\n",
    "                \n",
    "        plt.title(f\"{symbol} 策略买卖触发交易点位标记图\", fontsize=15, fontweight='bold')\n",
    "        plt.ylabel(\"价格 (元)\")\n",
    "        plt.legend(loc=\"upper left\")\n",
    "        plt.tight_layout()\n",
    "        plt.show()"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 5. 多进程参数网格寻优"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "if backtester.bars:\n",
    "    # 准备寻优参数配置\n",
    "    db_conn_info = {\n",
    "        \"dbname\": db_name,\n",
    "        \"user\": db_user,\n",
    "        \"password\": db_pass,\n",
    "        \"host\": db_host,\n",
    "        \"port\": int(db_port)\n",
    "    }\n",
    "    \n",
    "    grid = {\n",
    "        \"fast_window\": [5, 10, 15],\n",
    "        \"slow_window\": [20, 30, 40]\n",
    "    }\n",
    "    \n",
    "    # 并发执行参数搜索\n",
    "    results = run_grid_search(\n",
    "        strategy_class=DoubleMaStrategy,\n",
    "        db_conn_info=db_conn_info,\n",
    "        symbol=symbol,\n",
    "        exchange=exchange,\n",
    "        interval=interval,\n",
    "        start=start_date,\n",
    "        end=end_date,\n",
    "        parameter_grid=grid,\n",
    "        processes=2  # 并行进程数\n",
    "    )\n",
    "    \n",
    "    # 打印排前 5 名的最佳参数组\n",
    "    print(\"\\n🧬 【网格寻优结果排序 (前5名)】\")\n",
    "    print(\"-\"*65)\n",
    "    print(f\"{'排名':^4} | {'参数组合':<22} | {'夏普比率':^8} | {'总收益率':^8} | {'最大回撤':^8}\")\n",
    "    print(\"-\"*65)\n",
    "    for idx, r in enumerate(results[:5]):\n",
    "        print(f\" {idx+1:^4} | {str(r['setting']):<22} | {r['sharpe_ratio']:^8.2f} | {r['total_return']*100:^7.1f}% | {r['max_drawdown']*100:^7.1f}%\")\n",
    "    print(\"-\"*65)\n",
    "    \n",
    "    db.close() # 关闭主数据库连接"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3 (ipykernel)",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "name": "python"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 2
}

with open("D:\\datasci\\VNPY\\test_backtest_analysis.ipynb", "w", encoding="utf-8") as f:
    json.dump(notebook, f, ensure_ascii=False, indent=1)

print("test_backtest_analysis.ipynb created successfully!")
