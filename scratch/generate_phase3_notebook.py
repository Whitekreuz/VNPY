# -*- coding: utf-8 -*-
import json
import os

notebook = {
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# Phase 3 策略与风控子模块可视化验证测试\n",
    "\n",
    "本 Notebook 旨在直观测试并展示 Phase 3 核心重构与优化子模块的运行效果：\n",
    "1. **BarGenerator**：时间戳边界 K 线合成与空缺分钟对齐测试\n",
    "2. **RiskManager**：自适应秒级流控与风控规则拦截测试\n",
    "3. **DoubleMaStrategy**：双均线策略逻辑及成交/持仓管理测试"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "## 准备工作与依赖引入"
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
    "import time\n",
    "from datetime import datetime, timedelta\n",
    "import pandas as pd\n",
    "\n",
    "# 确保项目根目录在导入路径中\n",
    "sys.path.insert(0, os.path.abspath('.'))\n",
    "\n",
    "from core.models import TickData, BarData, OrderData, TradeData, Direction, Offset, Status\n",
    "from strategy.bar_generator import BarGenerator\n",
    "from risk.risk_manager import RiskManager\n",
    "from strategy.strategies.double_ma_strategy import DoubleMaStrategy\n",
    "print(\"✅ 依赖库导入完成\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "--- \n",
    "## 模块 1: BarGenerator 时间边界与分钟空缺对齐测试\n",
    "\n",
    "这里我们模拟一组 Tick 和 Bar 数据流，其中故意制造 **2分钟的行情空白（不发送数据）**，对比旧的“计数法”与最新的“时间边界法”的区别。"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "print(\"=== 测试 1: 正常行情下的 5 分钟合成 ===\")\n",
    "bars_5m = []\n",
    "def on_bar(bar):\n",
    "    bg.update_bar(bar)\n",
    "def on_5m_bar(bar):\n",
    "    bars_5m.append(bar)\n",
    "    print(f\"[5m Bar闭合] 时间: {bar.datetime.strftime('%H:%M')} | Open: {bar.open_price} | Close: {bar.close_price} | Vol: {bar.volume}\")\n",
    "\n",
    "bg = BarGenerator(on_bar, window=5, on_window_bar=on_5m_bar)\n",
    "\n",
    "# 喂入 09:00 - 09:04 (5根K线)\n",
    "for i in range(5):\n",
    "    bar = BarData(symbol=\"IF2401\", exchange=\"CFFEX\", datetime=datetime(2024, 1, 1, 9, i),\n",
    "                  open_price=4000.0, high_price=4010.0, low_price=3990.0, close_price=4005.0,\n",
    "                  volume=10, turnover=40000.0, interval=\"1m\")\n",
    "    bg.update_bar(bar)\n",
    "\n",
    "print(f\"合成 5m Bar 数量: {len(bars_5m)}\")\n",
    "assert len(bars_5m) == 1, \"应该已在09:04边界闭合推送一根\"\n",
    "\n",
    "print(\"\\n=== 测试 2: 制造行情空缺对齐测试 ===\")\n",
    "bars_5m_gap = []\n",
    "def on_5m_bar_gap(bar):\n",
    "    bars_5m_gap.append(bar)\n",
    "    print(f\"[5m Bar闭合(空缺场景)] 时间: {bar.datetime.strftime('%H:%M')} | Vol: {bar.volume}\")\n",
    "\n",
    "bg_gap = BarGenerator(on_bar, window=5, on_window_bar=on_5m_bar_gap)\n",
    "\n",
    "# 喂入：09:00, 09:01\n",
    "# 缺失：09:02, 09:03\n",
    "# 喂入：09:04 (刚好是本周期的最后边界)\n",
    "print(\"-> 喂入 09:00 K线\")\n",
    "bg_gap.update_bar(BarData(symbol=\"IF\", exchange=\"CF\", datetime=datetime(2024, 1, 1, 9, 0), volume=10, interval=\"1m\"))\n",
    "print(\"-> 喂入 09:01 K线\")\n",
    "bg_gap.update_bar(BarData(symbol=\"IF\", exchange=\"CF\", datetime=datetime(2024, 1, 1, 9, 1), volume=10, interval=\"1m\"))\n",
    "print(\"-> 缺失 09:02, 09:03行情...\")\n",
    "print(\"-> 喂入 09:04 K线(应在此时触发整分对齐闭合)\")\n",
    "bg_gap.update_bar(BarData(symbol=\"IF\", exchange=\"CF\", datetime=datetime(2024, 1, 1, 9, 4), volume=10, interval=\"1m\"))\n",
    "\n",
    "print(f\"合成数: {len(bars_5m_gap)} | 合成Bar的累计成交量 (应为30手): {bars_5m_gap[0].volume if bars_5m_gap else 0}\")\n",
    "\n",
    "print(\"\\n-> 喂入 09:09 K线 (跨大段空缺，此时应自动结算 09:05 的区间)\")\n",
    "bg_gap.update_bar(BarData(symbol=\"IF\", exchange=\"CF\", datetime=datetime(2024, 1, 1, 9, 9), volume=10, interval=\"1m\"))\n",
    "print(f\"合成总数: {len(bars_5m_gap)}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "--- \n",
    "## 模块 2: RiskManager 自适应流控与规则拦截测试\n",
    "\n",
    "我们制造每秒超高频报单，验证：\n",
    "1. 超过流控被立即拦截。\n",
    "2. 模拟进入下一秒后，流控计数自适应归零复位，无需外部介入。"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "class MockEngine:\n",
    "    def write_log(self, msg):\n",
    "        print(f\"🚨 [风控引擎日志] {msg}\")\n",
    "\n",
    "engine = MockEngine()\n",
    "rm = RiskManager(engine)\n",
    "rm.order_flow_limit = 2  # 设置极小的流控以进行测试\n",
    "rm.cancel_limit = 2\n",
    "rm.trade_limit = 5\n",
    "\n",
    "order = OrderData(symbol=\"IF2401\", exchange=\"CFFEX\", orderid=\"1\")\n",
    "\n",
    "print(\"=== 测试 1: 流控拦截与自动解锁 ===\")\n",
    "print(f\"1. 发送报单 1: {rm.check_order(order)}\")\n",
    "print(f\"2. 发送报单 2: {rm.check_order(order)}\")\n",
    "print(f\"3. 发送报单 3 (同秒内超限，应拦截): {rm.check_order(order)}\")\n",
    "\n",
    "print(\"\\n-> 模拟进入下一秒 (手动更新秒数)... \")\n",
    "rm._last_second -= 2\n",
    "\n",
    "print(f\"4. 发送报单 4 (自动解锁，应成功): {rm.check_order(order)}\")\n",
    "\n",
    "print(\"\\n=== 测试 2: 撤单次数超限拦截 ===\")\n",
    "rm.on_cancel(order)\n",
    "rm.on_cancel(order)\n",
    "print(f\"当前已撤单次数: {rm.cancel_count.get(order.vt_symbol)}\")\n",
    "print(f\"5. 再次报单 (因超限应被拦截): {rm.check_order(order)}\")"
   ]
  },
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "--- \n",
    "## 模块 3: CtaTemplate & DoubleMaStrategy 实弹策略与持仓管理\n",
    "\n",
    "我们将双均线策略加载到回测环境中，推入一段能产生金叉和死叉的 1m 价格序列，观察：\n",
    "1. 1m Bar 到 60m Bar 合成。\n",
    "2. 快慢均线计算。\n",
    "3. 策略发出交易信号，通过 `on_trade` 自动维护虚拟持仓量 `pos`。"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": None,
   "metadata": {},
   "outputs": [],
   "source": [
    "class MockCtaEngine:\n",
    "    def __init__(self):\n",
    "        self.trades = []\n",
    "    def send_order(self, strategy, direction, offset, price, volume, stop):\n",
    "        # 模拟撮合立即成交\n",
    "        tradeid = f\"T_{len(self.trades)+1}\"\n",
    "        trade = TradeData(\n",
    "            symbol=strategy.vt_symbol.split('.')[0],\n",
    "            exchange=strategy.vt_symbol.split('.')[1],\n",
    "            orderid=f\"O_{tradeid}\",\n",
    "            tradeid=tradeid,\n",
    "            direction=direction,\n",
    "            offset=offset,\n",
    "            price=price,\n",
    "            volume=volume,\n",
    "            datetime=datetime.now()\n",
    "        )\n",
    "        self.trades.append(trade)\n",
    "        # 回调策略\n",
    "        strategy.on_trade(trade)\n",
    "        return trade.orderid\n",
    "    def cancel_order(self, strategy, vt_orderid):\n",
    "        print(f\"策略请求撤销委托单: {vt_orderid}\")\n",
    "    def write_log(self, msg):\n",
    "        print(f\"📝 [策略日志] {msg}\")\n",
    "\n",
    "cta_engine = MockCtaEngine()\n",
    "strategy = DoubleMaStrategy(cta_engine, \"DoubleMA_Test\", \"rb2405.SHFE\", {\"fast_window\": 2, \"slow_window\": 5})\n",
    "strategy.inited = True\n",
    "strategy.trading = True\n",
    "\n",
    "print(\"=== 开始推送 1 分钟 K 线模拟小时均线计算 ===\")\n",
    "# 我们设置策略的 bg 合成窗口为 60 (60分钟合成一根小时线)\n",
    "# 我们将生成 60 * 6 = 360 根 1 分钟 K 线来产生 6 根小时线\n",
    "# 价格曲线：前3根小时收盘价 3500, 后3根小时收盘价 3520 (形成金叉)\n",
    "prices = [3500] * 180 + [3520] * 180\n",
    "\n",
    "for index, price in enumerate(prices):\n",
    "    bar = BarData(\n",
    "        symbol=\"rb2405\", exchange=\"SHFE\",\n",
    "        datetime=datetime(2024, 1, 1, 9, 0) + timedelta(minutes=index),\n",
    "        open_price=price, high_price=price+2, low_price=price-2, close_price=price,\n",
    "        volume=10, interval=\"1m\"\n",
    "    )\n",
    "    strategy.on_bar(bar)\n",
    "\n",
    "print(f\"\\n均线计算结果 -> 快轨MA0: {strategy.fast_ma0} | 慢轨MA0: {strategy.slow_ma0}\")\n",
    "print(f\"策略持仓状态 pos: {strategy.pos} (金叉后应该已开多仓1手)\")"
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

with open("D:\\datasci\\VNPY\\test_phase3_modules.ipynb", "w", encoding="utf-8") as f:
    json.dump(notebook, f, ensure_ascii=False, indent=1)

print("test_phase3_modules.ipynb created successfully!")
