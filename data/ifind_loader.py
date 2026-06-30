import pandas as pd
from datetime import datetime
import os
from dotenv import load_dotenv

# 加载 .env 环境变量
load_dotenv()

try:
    from iFinDPy import THS_iFinDLogin, THS_iFinDLogout, THS_HF, THS_HQ
    IFIND_INSTALLED = True
except ImportError:
    IFIND_INSTALLED = False
    print("Warning: iFinDPy module not found. IFinDLoader will not work.")

class IFinDLoader:
    def __init__(self):
        self.connected = False

    def login(self, username=None, password=None):
        if not IFIND_INSTALLED:
            print("未安装 iFinDPy 库，请使用 pip install iFinDPy 安装。")
            return False
            
        username = username or os.getenv("IFIND_USERNAME")
        password = password or os.getenv("IFIND_PASSWORD")
        
        if not username or not password:
            print("错误：缺少 iFinD 账号或密码。请在代码中传入，或在 .env 文件中配置 IFIND_USERNAME 和 IFIND_PASSWORD")
            return False
            
        ret = THS_iFinDLogin(username, password)
        if ret == 0 or ret == -201: # 0: 成功, -201: 已登录
            self.connected = True
            print("iFinD 登录成功")
            return True
        else:
            print(f"iFinD 登录失败, 错误码: {ret}")
            return False
            
    def logout(self):
        if self.connected and IFIND_INSTALLED:
            THS_iFinDLogout()
            self.connected = False
            print("iFinD 登出成功")

    def fetch_history_bars(self, symbol: str, start_date: datetime, end_date: datetime, interval: str = "1m"):
        """获取历史 K 线数据"""
        if not self.connected:
            print("请先登录 iFinD")
            return pd.DataFrame()
            
        start_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
        end_str = end_date.strftime("%Y-%m-%d %H:%M:%S")
        
        # 将系统定义的 interval 转换为 iFinD 参数
        # THS_HF 支持分钟级数据
        if interval.endswith("m"):
            ret = THS_HF(symbol, 'open;high;low;close;volume;amount;openInterest', 'Fill:Blank', start_str, end_str)
        else:
            # 默认日线调用 THS_HQ
            ret = THS_HQ(symbol, 'open,high,low,close,volume,amount,openInterest', '', start_str, end_str)
        
        if ret.errorcode != 0:
            if ret.errorcode == -4226:
                # 忽略权限错误或未上市的日志轰炸
                pass
            else:
                print(f"获取数据失败: {symbol} - {ret.errmsg} (code: {ret.errorcode})")
            return pd.DataFrame()
            
        df = ret.data
        if df is None or df.empty:
            return pd.DataFrame()
            
        # 格式化，使其与我们的 BarData 字段一致
        df = df.rename(columns={
            'time': 'datetime',
            'open': 'open_price',
            'high': 'high_price',
            'low': 'low_price',
            'close': 'close_price',
            'volume': 'volume',
            'amount': 'turnover',
            'openInterest': 'open_interest'
        })
        
        df['datetime'] = pd.to_datetime(df['datetime'])
        df['symbol'] = symbol.split('.')[0] if '.' in symbol else symbol
        df['exchange'] = symbol.split('.')[1] if '.' in symbol else ""
        df['interval'] = interval
        
        return df
