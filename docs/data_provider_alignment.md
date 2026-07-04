# RiceQuant & TqSdk 数据源对齐规范 (ADR)

本规范规定了米筐 (RiceQuant) 与天勤 (TqSdk) 数据源在期货 1分钟 (1m) 及 1小时 (1H) K线上的时间戳、交易所、连续合约命名、以及字段的统一对齐逻辑。

---

## 1. 核心对齐规则

由于两家数据商数据发布的时间戳表达方式、时区、以及字段缺失等问题，本系统制定了以下物理对齐标准。所有数据在入库或回测加载前，必须通过 [`data/data_aligner.py`](file:///D:/datasci/VNPY/data/data_aligner.py) 进行规范化转换。

### 1.1 时间戳对齐 (北京时间 CST vs 国际协调时 UTC)
* **天勤 (TqSdk)**: 原始 `datetime` 为 UTC 时区的 Unix 纪元纳秒时间戳，且代表的是该 K线的**开始时间** (例如周五下午日盘最后一根 K线的时间戳转化为 UTC 字符串为 `2026-07-03 06:59:00`，夜盘最后一根 K线为 `2026-07-03 14:59:00`)。
* **米筐 (RiceQuant) & 本地库**: 代表的是北京时间 (CST) 且为 K线的**结束时间** (例如周五日盘结束时间为 `15:00:00`，夜盘结束为 `23:00:00`)。
* **对齐公式**:
  $$\text{CST\_End\_Time} = \text{UTC\_Start\_Time} + 8\,\text{Hours} + 1\,\text{Minute}$$

### 1.2 交易所代码对照
| VNPY / 数据库缩写 | 米筐 (RiceQuant) 后缀 | 天勤 (TqSdk) 前缀 | 实际交易所 |
| :--- | :--- | :--- | :--- |
| **SHF** | .SHF | SHFE | 上海期货交易所 |
| **DCE** | .DCE | DCE | 大连商品交易所 |
| **CZC** | .CZC | CZCE | 郑州商品交易所 |
| **CFE** | .CFE | CFFEX | 中国金融期货交易所 |
| **GFE** | .GFE | GFEX | 广州期货交易所 |

### 1.3 连续属性合约命名对齐
* **主力连续 (88)**: 米筐表示为大写 `RB88`，天勤表示为 `KQ.m@SHFE.rb`。
* **指数连续 (888)**: 米筐表示为大写 `RB888`，天勤表示为 `KQ.i@SHFE.rb`。
* **次主力连续 (99)**: 米筐表示为大写 `RB99`。天勤本身不提供次主力符号，需通过对该品种所有未过期合约的持仓量 (`open_interest`) 进行降序排列，取持仓量第二大的具体合约代码 (如 `SHFE.rb2701`) 进行数据拉取。

### 1.4 单月合约命名及年份转换
* **标准大写**: 所有单月合约名称必须保持大写 (如 `RB2610` 而不是小写 `rb2610`)。
* **郑商所 (CZCE) 年份缩写**:
  * 郑商所在天勤中的格式为 3位代码 (如 `CZCE.CF309`)，而数据库统一要求 4位代码 (如 `CF2309`)。
  * 对齐方法：必须通过天勤 `query_symbol_info` 取得合约的静态信息 `delivery_year` (如 `2023`) 和 `delivery_month` (如 `9`)，动态拼装为标准 4位代码 `CF2309`。

### 1.5 字段换算与成交额补充
* **持仓量**: 天勤 K 线中 `open_oi` 为开盘持仓，`close_oi` 为收盘持仓。本地库与米筐均以收盘持仓为准，因此使用天勤的 `close_oi` 对齐为 `open_interest`。
* **成交额 (Turnover) 估算**:
  * 天勤 1m K线无成交额字段，米筐和本地数据库均要求成交额。
  * **估算公式**:
    $$\text{Turnover} = \text{Volume} \times \text{Close} \times \text{Volume\_Multiple}$$
  * `Volume_Multiple` (合约乘数) 通过 `query_symbol_info` 或 `get_quote` 动态获取 (例如螺纹钢为 10，黄金为 1000)。

---

## 2. 转换模块设计

对齐功能的具体实现位于：[data_aligner.py](file:///D:/datasci/VNPY/data/data_aligner.py) 模块中。

调用示例：
```python
from data.data_aligner import DataAligner

# 假设从天勤获取了 klines DataFrame
aligned_df = DataAligner.convert_tq_kline_to_df(
    tq_df=klines,
    db_symbol="RB88",
    vn_exchange="SHF",
    volume_multiple=10.0
)

# 转化为 VNPY 的 BarData 实体列表
bars = DataAligner.to_bar_data_list(aligned_df)

# 直接入库
db.save_bar_data(bars)
```
