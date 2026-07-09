# -*- coding: utf-8 -*-
import os
import sys
import time
from datetime import datetime
import pandas as pd
from openctp_ctp import mdapi, tdapi
from core.event_engine import EventEngine, Event
from core.models import TickData, OrderData, TradeData, Status, Direction, Offset

# Ensure stdout uses UTF-8 and line buffering
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True, encoding='utf-8')

def _to_str(val: object, encoding: str = 'gbk') -> str:
    """将 CTP 字段统一转换为 str，兼容 bytes（旧版）和 str（新版 openctp_ctp）。"""
    if isinstance(val, bytes):
        return val.decode(encoding, errors='ignore')
    return val or ""

class CtpGateway:
    """
    轻量化 CTP 接口网关
    支持实时行情 (MdApi) 接收与广播，以及仿真/实盘交易前置 (TdApi) 对接。
    """
    def __init__(self, event_engine: EventEngine):
        self.event_engine = event_engine
        self.gateway_name = "CTP"
        
        # API 实例与 SPI 实例
        self.md_api = None
        self.td_api = None
        self.md_spi = None
        self.td_spi = None
        
        # 连接与登录状态
        self.md_connected = False
        self.md_logged_in = False
        self.td_connected = False
        self.td_logged_in = False
        
        # CTP 客户端认证信息 (ReqAuthenticate 所需)
        self.app_id = ""
        self.auth_code = ""
        
        # 订阅合约缓存
        self.subscribed_contracts = set()
        
        # 缓存每个合约的最新行情累计量，以便将累计 Volume/Turnover 转换为 Tick 内增量
        self.last_tick_data = {}

    def connect(self, setting: dict = None):
        """
        连接前置机
        如果 setting 为 None，则从环境变量中读取配置。
        """
        if setting is None:
            setting = {
                "investor_id": os.getenv("SIMNOW_INVESTOR_ID", ""),
                "password": os.getenv("SIMNOW_PASSWORD", ""),
                "broker_id": os.getenv("SIMNOW_BROKER_ID", "9999"),
                "trade_front": os.getenv("SIMNOW_TRADE_FRONT", "tcp://180.168.146.187:10130"),
                "md_front": os.getenv("SIMNOW_MD_FRONT", "tcp://180.168.146.187:10131"),
                "app_id": os.getenv("SIMNOW_APP_ID", "simnow_client_test"),
                "auth_code": os.getenv("SIMNOW_AUTH_CODE", "0000000000000000"),
            }

        self.investor_id = setting.get("investor_id", "")
        self.password = setting.get("password", "")
        self.broker_id = setting.get("broker_id", "9999")
        self.trade_front = setting.get("trade_front", "")
        self.md_front = setting.get("md_front", "")
        self.app_id = setting.get("app_id", "simnow_client_test")
        self.auth_code = setting.get("auth_code", "0000000000000000")

        if not self.investor_id or not self.password:
            print("⚠️ [CTP网关] 未检测到有效的 CTP 账户密码配置，跳过网关连接。")
            return

        # 创建临时的 CTP 流量文件目录，防止污染根目录
        os.makedirs("temp", exist_ok=True)

        # 1. 建立行情连接
        if self.md_front:
            print(f"🔌 [CTP网关] 正在建立行情前置连接: {self.md_front} ...")
            self.md_api = mdapi.CThostFtdcMdApi.CreateFtdcMdApi("temp/md_flow")
            self.md_spi = CtpMdSpi(self)
            self.md_api.RegisterSpi(self.md_spi)
            self.md_api.RegisterFront(self.md_front)
            self.md_api.Init()

        # 2. 建立交易连接
        if self.trade_front:
            print(f"🔌 [CTP网关] 正在建立交易前置连接: {self.trade_front} ...")
            self.td_api = tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi("temp/td_flow")
            self.td_spi = CtpTdSpi(self)
            self.td_api.RegisterSpi(self.td_spi)

            self.td_api.RegisterFront(self.trade_front)
            self.td_api.Init()

    def subscribe(self, symbol: str, exchange: str):
        """
        订阅合约行情
        """
        # 将标准 symbol 转换为 CTP 格式的 symbol (如 CF2609 -> CF609)
        ctp_symbol = self.to_ctp_symbol(symbol, exchange)
        self.subscribed_contracts.add((symbol, exchange, ctp_symbol))
        
        if self.md_logged_in and self.md_api:
            # 字节列表传递
            self.md_api.SubscribeMarketData([ctp_symbol.encode('utf-8')], 1)
            print(f"📥 [CTP网关] 订阅合约行情: {ctp_symbol} ({symbol}.{exchange})")

    def close(self):
        """释放 CTP API 连接"""
        if self.md_api:
            try:
                self.md_api.RegisterSpi(None)
            except Exception:
                pass
            self.md_api.Release()
            self.md_api = None
            print("🔌 [CTP网关] 行情接口已释放。")
        if self.td_api:
            try:
                self.td_api.RegisterSpi(None)
            except Exception:
                pass
            self.td_api.Release()
            self.td_api = None
            print("🔌 [CTP网关] 交易接口已释放。")
        
        # 同步重置所有连通状态变量
        self.md_connected = False
        self.md_logged_in = False
        self.td_connected = False
        self.td_logged_in = False


    @staticmethod
    def to_ctp_symbol(symbol: str, exchange: str) -> str:
        """
        将通用合约名称转换为 CTP 期望的命名规则
        1. 郑商所 (CZC) 代码为 3 位年份月份 (如 CF2609 -> CF609)
        2. 中金所 (CFE) 合约代码大写 (如 IF2609)
        3. 其他交易所合约代码小写 (如 rb2610)
        """
        sym_upper = symbol.upper()
        exch_upper = exchange.upper()
        
        # 郑商所 3 位年份转换
        if exch_upper in ["CZC", "CZCE"] and symbol[-4:].isdigit():
            # 取前缀 + 3位数字 (丢弃千位数字)
            return symbol[:-4] + symbol[-3:]
            
        # 中金所大写，其他小写
        if exch_upper in ["CFE", "CFFEX"]:
            return sym_upper
        else:
            return symbol.lower()

    @staticmethod
    def clean_czc_symbol(symbol: str) -> str:
        """
        将 CTP 格式的郑商所 3 位合约转换为 VNPY 标准 4 位合约代码
        (如 CF609 -> CF2609)
        """
        # 郑商所一般为前缀 2-3 字母 + 3位数字
        if len(symbol) >= 5 and symbol[-3:].isdigit():
            year_digit = int(symbol[-3])
            current_year = datetime.now().year
            current_decade = (current_year // 10) * 10
            
            inferred_year = current_decade + year_digit
            # 容错：如果是 CF909 且当前是 2026年，代表 2019 (已退市) 或 2029 (未上市)
            if inferred_year < current_year - 2:
                inferred_year += 10
            elif inferred_year > current_year + 2:
                inferred_year -= 10
                
            return symbol[:-3] + str(inferred_year)[2:] + symbol[-2:]
        return symbol

class CtpMdSpi(mdapi.CThostFtdcMdSpi):
    """
    CTP 行情回调 SPI 实现
    """
    def __init__(self, gateway: CtpGateway):
        super().__init__()
        self.gateway = gateway

    def OnFrontConnected(self):
        print("🌐 [CTP行情] 行情前置机连通，开始登录...")
        self.gateway.md_connected = True
        
        req = mdapi.CThostFtdcReqUserLoginField()
        req.BrokerID = self.gateway.broker_id
        req.UserID = self.gateway.investor_id
        req.Password = self.gateway.password
        self.gateway.md_api.ReqUserLogin(req, 1)

    def OnFrontDisconnected(self, nReason: int):
        print(f"❌ [CTP行情] 行情前置机连接断开！原因代码: {nReason}")
        self.gateway.md_connected = False
        self.gateway.md_logged_in = False

    def OnRspUserLogin(self, pRspUserLogin, pRspInfo, nRequestID, bIsLast):
        if pRspInfo and pRspInfo.ErrorID != 0:
            err_msg = _to_str(pRspInfo.ErrorMsg)
            print(f"❌ [CTP行情] 登录行情服务器失败！代码: {pRspInfo.ErrorID}, 原因: {err_msg}")
        else:
            print("✅ [CTP行情] 行情服务器登录成功！")
            self.gateway.md_logged_in = True
            
            # 重新订阅缓存的合约行情列表
            if self.gateway.subscribed_contracts:
                print(f"🔄 [CTP行情] 重新订阅已缓存的 {len(self.gateway.subscribed_contracts)} 个合约行情...")
                for symbol, exchange, ctp_symbol in self.gateway.subscribed_contracts:
                    self.gateway.md_api.SubscribeMarketData([ctp_symbol.encode('utf-8')], 1)

    def OnRtnDepthMarketData(self, pDepthMarketData):
        if not pDepthMarketData:
            return
            
        try:
            ctp_symbol = _to_str(pDepthMarketData.InstrumentID)
            raw_exchange = _to_str(pDepthMarketData.ExchangeID)
            
            # 交易所映射还原
            from data.data_aligner import DataAligner
            vn_exchange = "SHF"
            if raw_exchange:
                vn_exchange = DataAligner.get_vn_exchange(raw_exchange)
            else:
                # 模糊推断
                if ctp_symbol.isupper():
                    vn_exchange = "CFE"
                elif len(ctp_symbol) >= 5 and ctp_symbol[-3:].isdigit():
                    vn_exchange = "CZC"
                else:
                    # 默认 SHF 或 DCE (通过外部订阅时的对照关系做匹配)
                    for sym, exch, ctp_s in self.gateway.subscribed_contracts:
                        if ctp_s == ctp_symbol:
                            vn_exchange = exch
                            break
            
            # 郑商所 3位代码还原为 4位标准代码
            if vn_exchange == "CZC":
                db_symbol = CtpGateway.clean_czc_symbol(ctp_symbol).upper()
            else:
                db_symbol = ctp_symbol.upper()
                
            # 解析时间
            action_day = _to_str(pDepthMarketData.ActionDay) or datetime.now().strftime("%Y%m%d")
            update_time = _to_str(pDepthMarketData.UpdateTime) or "00:00:00"
            millisec = pDepthMarketData.UpdateMillisec if pDepthMarketData.UpdateMillisec else 0

            # 安全检测：若 ActionDay 与本机日期相差超过 1 天（如 7x24 回放环境），
            # 则使用本机系统时间，避免生成错误的历史时间戳影响 Bar 合成
            today_str = datetime.now().strftime("%Y%m%d")
            try:
                from datetime import date
                ad = date(int(action_day[:4]), int(action_day[4:6]), int(action_day[6:8]))
                td = date(int(today_str[:4]), int(today_str[4:6]), int(today_str[6:8]))
                if abs((ad - td).days) > 1:
                    dt = datetime.now().replace(microsecond=0)
                else:
                    dt_str = f"{action_day} {update_time}.{millisec:03d}"
                    try:
                        dt = datetime.strptime(dt_str, "%Y%m%d %H:%M:%S.%f")
                    except ValueError:
                        dt = datetime.now()
            except (ValueError, IndexError):
                dt = datetime.now()


            # 转换累计成交量/成交额为增量
            cumulative_volume = float(pDepthMarketData.Volume)
            cumulative_turnover = float(pDepthMarketData.Turnover)
            
            last_vol, last_turn = self.gateway.last_tick_data.get(db_symbol, (None, None))
            if last_vol is None:
                # 首笔 Tick，增量计为 0
                inc_volume = 0.0
                inc_turnover = 0.0
            else:
                inc_volume = cumulative_volume - last_vol
                inc_turnover = cumulative_turnover - last_turn
                
                # 容错：防止隔夜重置或换月清零导致负数
                if inc_volume < 0:
                    inc_volume = cumulative_volume
                if inc_turnover < 0:
                    inc_turnover = cumulative_turnover
                    
            self.gateway.last_tick_data[db_symbol] = (cumulative_volume, cumulative_turnover)

            # 拼装标准 TickData 结构
            tick = TickData(
                symbol=db_symbol,
                exchange=vn_exchange,
                datetime=dt,
                last_price=pDepthMarketData.LastPrice if pDepthMarketData.LastPrice < 1e10 else 0.0,
                volume=inc_volume,
                turnover=inc_turnover,
                open_interest=float(pDepthMarketData.OpenInterest),
                limit_up=pDepthMarketData.UpperLimitPrice if pDepthMarketData.UpperLimitPrice < 1e10 else 0.0,
                limit_down=pDepthMarketData.LowerLimitPrice if pDepthMarketData.LowerLimitPrice < 1e10 else 0.0,
                bid_price_1=pDepthMarketData.BidPrice1 if pDepthMarketData.BidPrice1 < 1e10 else 0.0,
                bid_volume_1=float(pDepthMarketData.BidVolume1),
                ask_price_1=pDepthMarketData.AskPrice1 if pDepthMarketData.AskPrice1 < 1e10 else 0.0,
                ask_volume_1=float(pDepthMarketData.AskVolume1),
            )
            
            # 广播事件（跨线程调用，必须使用 put_threadsafe！）
            self.gateway.event_engine.put_threadsafe(Event("eTick.", tick))
        except Exception as e:
            print(f"❌ [CTP行情] 解析 Tick 数据报错: {e}")

class CtpTdSpi(tdapi.CThostFtdcTraderSpi):
    """
    CTP 交易回调 SPI 实现
    """
    def __init__(self, gateway: CtpGateway):
        super().__init__()
        self.gateway = gateway

    def OnFrontConnected(self):
        print("🌐 [CTP交易] 交易前置机连通，开始客户端认证...")
        self.gateway.td_connected = True
        
        # 现代 CTP 要求在 ReqUserLogin 之前先完成 ReqAuthenticate 鉴权
        req = tdapi.CThostFtdcReqAuthenticateField()
        req.BrokerID = self.gateway.broker_id
        req.UserID = self.gateway.investor_id
        req.AppID = self.gateway.app_id
        req.AuthCode = self.gateway.auth_code
        self.gateway.td_api.ReqAuthenticate(req, 0)

    def OnRspAuthenticate(self, pRspAuthenticateField, pRspInfo, nRequestID, bIsLast):
        """客户端认证回调 - 成功后才发起登录"""
        if pRspInfo and pRspInfo.ErrorID != 0:
            err_msg = pRspInfo.ErrorMsg.decode('gbk', errors='ignore') if isinstance(pRspInfo.ErrorMsg, bytes) else pRspInfo.ErrorMsg
            print(f"❌ [CTP交易] 客户端认证失败！代码: {pRspInfo.ErrorID}, 原因: {err_msg}")
            print("💡 提示：请检查 .env 中的 SIMNOW_APP_ID 和 SIMNOW_AUTH_CODE 配置是否正确。")
            return
        
        print("🔐 [CTP交易] 客户端认证成功，开始登录...")
        req = tdapi.CThostFtdcReqUserLoginField()
        req.BrokerID = self.gateway.broker_id
        req.UserID = self.gateway.investor_id
        req.Password = self.gateway.password
        self.gateway.td_api.ReqUserLogin(req, 1)

    def OnFrontDisconnected(self, nReason: int):
        print(f"❌ [CTP交易] 交易前置机连接断开！原因代码: {nReason}")
        self.gateway.td_connected = False
        self.gateway.td_logged_in = False

    def OnRspUserLogin(self, pRspUserLogin, pRspInfo, nRequestID, bIsLast):
        if pRspInfo and pRspInfo.ErrorID != 0:
            err_msg = pRspInfo.ErrorMsg.decode('gbk', errors='ignore')
            print(f"❌ [CTP交易] 登录交易柜台失败！代码: {pRspInfo.ErrorID}, 原因: {err_msg}")
        else:
            print("✅ [CTP交易] 交易柜台登录成功！")
            self.gateway.td_logged_in = True
            
            # 自动查询一次账户权益，确保连接真正连通
            req = tdapi.CThostFtdcQryTradingAccountField()
            req.BrokerID = self.gateway.broker_id
            req.InvestorID = self.gateway.investor_id
            # 延时避开流量控速
            time.sleep(0.5)
            self.gateway.td_api.ReqQryTradingAccount(req, 2)

    def OnRspQryTradingAccount(self, pTradingAccount, pRspInfo, nRequestID, bIsLast):
        if pTradingAccount:
            print(f"💰 [CTP交易] 账户连通度验证成功。可用资金: {pTradingAccount.Available:.2f} | 动态权益: {pTradingAccount.Balance:.2f}")
