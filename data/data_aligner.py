# -*- coding: utf-8 -*-
import pandas as pd
from datetime import datetime
from core.models import BarData

class DataAligner:
    """
    RiceQuant 与 TqSdk 行情数据对齐引擎
    封装了交易所代码映射、合约名称转换、时区偏移行权、成交额估算等标准化规则。
    """
    
    # 交易所映射对照表
    EXCHANGE_TO_TQ = {
        "SHF": "SHFE",
        "DCE": "DCE",
        "CZC": "CZCE",
        "CFE": "CFFEX",
        "GFE": "GFEX"
    }
    
    EXCHANGE_FROM_TQ = {v: k for k, v in EXCHANGE_TO_TQ.items()}

    @classmethod
    def get_tq_exchange(cls, vn_exchange: str) -> str:
        """VNPY 交易所代码 -> TqSdk 交易所代码"""
        return cls.EXCHANGE_TO_TQ.get(vn_exchange.upper(), vn_exchange.upper())

    @classmethod
    def get_vn_exchange(cls, tq_exchange: str) -> str:
        """TqSdk 交易所代码 -> VNPY 交易所代码"""
        return cls.EXCHANGE_FROM_TQ.get(tq_exchange.upper(), tq_exchange.upper())

    @classmethod
    def align_tq_datetime(cls, tq_datetime_series: pd.Series) -> pd.Series:
        """
        天勤原始时间戳 (UTC开始时间) -> VNPY/米筐标准时间戳 (北京时间 CST 结束时间)
        CST_End_Time = UTC_Start_Time + 8 hours + 1 minute
        """
        return pd.to_datetime(tq_datetime_series) + pd.Timedelta(hours=8) + pd.Timedelta(minutes=1)

    @classmethod
    def estimate_tq_turnover(cls, volume_series: pd.Series, close_series: pd.Series, volume_multiple: float) -> pd.Series:
        """
        估算天勤 K 线成交额
        turnover = volume * close * volume_multiple
        """
        return volume_series * close_series * volume_multiple

    @classmethod
    def convert_tq_kline_to_df(cls, tq_df: pd.DataFrame, db_symbol: str, vn_exchange: str, volume_multiple: float = 10.0) -> pd.DataFrame:
        """
        将天勤 get_kline_serial 返回的 DataFrame 转换为对齐米筐标准的清洗后 DataFrame
        """
        df = tq_df.copy()
        
        # 1. 时间戳转换与对齐
        df['datetime'] = cls.align_tq_datetime(df['datetime'])
        
        # 2. 估算成交额
        df['turnover'] = cls.estimate_tq_turnover(df['volume'], df['close'], volume_multiple)
        
        # 3. 字段改名与规范
        df = df.rename(columns={
            'open_oi': 'open_interest_start',
            'close_oi': 'open_interest'
        })
        
        # 4. 添加标准符号信息
        df['symbol'] = db_symbol
        df['exchange'] = vn_exchange
        df['interval'] = "1m"
        
        return df[['datetime', 'symbol', 'exchange', 'interval', 'open', 'high', 'low', 'close', 'volume', 'turnover', 'open_interest']]

    @classmethod
    def to_bar_data_list(cls, aligned_df: pd.DataFrame) -> list:
        """
        将对齐后的 DataFrame 转换为 BarData 实体列表以存入数据库
        """
        bars = []
        for _, row in aligned_df.iterrows():
            bar = BarData(
                symbol=row['symbol'],
                exchange=row['exchange'],
                datetime=row['datetime'].to_pydatetime() if hasattr(row['datetime'], 'to_pydatetime') else pd.to_datetime(row['datetime']),
                interval=row['interval'],
                volume=float(row['volume']),
                turnover=float(row['turnover']),
                open_interest=float(row['open_interest']),
                open_price=float(row['open']),
                high_price=float(row['high']),
                low_price=float(row['low']),
                close_price=float(row['close'])
            )
            bars.append(bar)
        return bars
