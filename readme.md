# 商品与股票量化交易系统

## 🎯 项目定位与目的
本项目旨在探索、评估并最终搭建一个面向国内金融市场的、**完全自主可控**的轻量级量化交易系统。
系统初期的核心聚焦于**商品（期货/期权）的量化交易**，主要基于分钟级别（K线）的交易逻辑。在未来，系统计划横向扩展，延伸成为一个兼容**股票市场的综合性量化交易平台**。

系统架构**深度汲取了 VNPY 的核心事件驱动思想**，但坚决摒弃其沉重的桌面端界面与耦合依赖。我们将完全自主化地提取重构系统的核心引擎、独立建立基于 PostgreSQL 的数据中心，并最终通过 FastAPI + Vue/Echarts 构建现代化的 Web 可视化大屏。

---

## 🗺️ 整体开发与实施计划 (Roadmap)

我们将整个系统的研发过程严谨地拆分为以下 5 个核心 Phase。
**开发规范约定**：每完成一个子模块，都必须在 `docs/` 目录下建立该模块独立的使用规则说明文件，并在 `tests/` 目录下建立对应的测试脚本。

### Phase 1: 核心系统底座 (Core Engine)
搭建整个系统的心脏——异步事件驱动引擎。
- [ ] 定义基础数据模型 (TickData, BarData, OrderData 等，借鉴 VNPY 标准字段)。
- [ ] 开发轻量级的纯后台主引擎 (`TradingEngine`)。
- [ ] 开发基于 `asyncio` 的核心事件分发引擎 (`EventEngine`)。
- [ ] 开发本地沙盒仿真账户环境 (`PaperAccount`)。
- [ ] 撰写说明文档 (`docs/core_engine.md`) 并完成事件分发机制测试 (`tests/test_event_engine.py`)。

### Phase 2: 数据底座、记录与回测模块 (Data, Recorder & Backtest)
打通脱机历史数据与实盘行情数据的保存闭环。
- [ ] 完成 PostgreSQL + TimescaleDB 的本地环境配置。
- [ ] 开发基于 iFinD API 的历史分钟/日线数据下载与清洗脚本 (`data/ifind_loader.py`)。
- [ ] 开发数据库统一交互与入库模块 (`data/db_manager.py`)。
- [ ] 开发高效的本地脱机 CTA 回测引擎 (`backtest/backtester.py`)。
- [ ] 开发实盘并行运行的数据落盘记录器 (`data/recorder.py`)。
- [ ] 撰写说明文档 (`docs/data_and_backtest.md`) 并完成历史数据存取测试 (`tests/test_data.py`)。

### Phase 3: 策略引擎与事前风控 (Strategy Engine & Risk Control)
定义量化策略的生命周期和系统“安全带”。
- [ ] 开发标准化的 CTA 策略基类模板 (`strategy/template.py`)。
- [ ] 独立剥离并完善分钟 K 线合成器 (`strategy/bar_generator.py`)。
- [ ] 编写用于验证系统运转的演示策略 (`strategy/demo_strategy.py`)。
- [ ] 开发极简但严格的全局事前风控拦截器，涵盖资金与流控 (`risk/risk_manager.py`)。
- [ ] 撰写说明文档 (`docs/strategy_and_risk.md`) 并完成策略信号触发及风控阻断测试。

### Phase 4: 交易网关接口 (Gateway Layer)
对接真实世界，打通实盘与模拟盘行情及交易通道。
- [ ] 制定并开发网关抽象基类 (`gateway/base_gateway.py`)，为期货与未来股票扩容定下规范。
- [ ] 安装并引入 `vnpy_ctp` 底层 C++ 动态库。
- [ ] 自主编写 CTP 适配器 (`gateway/ctp_gateway`)，将底层 CTP 结构转译为我们的标准体系。
- [ ] 注册 SimNow 账号，进行全链路的实盘行情接收与模拟发单测试。
- [ ] 撰写说明文档 (`docs/gateway.md`) 并完成连接测试 (`tests/test_gateway.py`)。

### Phase 5: 现代 Web 可视化大屏 (Visualization Dashboard)
剥离一切桌面端羁绊，打造现代化的量化操作控制台。
- [ ] 开发基于 FastAPI 的后端数据服务，通过 WebSocket 桥接核心事件引擎，向外推送持仓、资金与日志流。
- [ ] 基于数据库汇集各子策略资金曲线（投组管理理念），开发历史盈亏结算查询接口。
- [ ] 开发前端 Web 控制台页面（监控面板、启停控制、Echarts 实时K线图表展示）。
- [ ] 撰写可视化启动与部署文档 (`docs/visualization.md`)。

---

## 📅 项目当前进展
*当前任务聚焦*: **准备启动 Phase 1**。
