# 数据底座、记录与回测说明文档 (Data & Backtest)

本模块负责打破策略研究与实盘交易之间的数据壁垒。它包含了从第三方同花顺 (iFinD) 拉取数据、统一结构化后写入 PostgreSQL，以及为本地回测提供历史数据投喂的全套功能。

## 目录结构与功能

- **`data/ifind_loader.py`**：基于您本地拥有的同花顺 `iFinDPy` 权限编写。它将 iFinD 的复杂 `DataFrame` 无缝转译为我们系统标准的 `BarData` 字段。
- **`data/db_manager.py`**：系统的底层数据库大管家，依托 `psycopg2`，直接使用原生 SQL 对 PostgreSQL 进行极速的读写和建表操作。（强烈建议您在数据库中启用 TimescaleDB 插件，通过把时间字段转化为 Hypertable 来获得极致的时序查询体验）。
- **`data/recorder.py`**：实盘时并行的记录器插件。它挂载在核心系统底座 (`TradingEngine`) 上，一边让策略交易，一边悄无声息地收集 `EventEngine` 里流淌的实时 K 线，并批量入库保存。
- **`backtest/backtester.py`**：脱机回测器。直接将数据库拉出的连续历史 `BarData` 投喂给策略类，完成离线模拟。

## PostgreSQL 部署要求

为使本模块完美运转，您需要在量化 Python 环境下完成如下依赖安装：

```bash
# 必须安装
pip install psycopg2-binary
pip install pandas

# 如果使用同花顺脚本，请确保官方库存在
pip install iFinDPy
```

### 初始化数据库环境：
我们默认您在本地（`localhost`）搭建了 PostgreSQL 服务。在运行任何代码前，请在您的 Postgres 客户端（如 pgAdmin 或 DataGrip）中建立一个专属数据库（例如 `quant_db`）：

```sql
CREATE DATABASE quant_db;
```

当 `DBManager` 第一次被实例化时，它会自动在 `quant_db` 内建立带有复合主键防重的 `bardata` 数据表。
