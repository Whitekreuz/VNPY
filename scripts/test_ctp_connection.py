# -*- coding: utf-8 -*-
import os
import sys
import time
from dotenv import load_dotenv

# Ensure stdout uses UTF-8 and line buffering
sys.stdout.reconfigure(line_buffering=True, encoding='utf-8')

try:
    from openctp_ctp import mdapi, tdapi
except ImportError:
    print("❌ 未检测到 openctp-ctp 库，请先运行: pip install openctp-ctp")
    sys.exit(1)

class TestMdSpi(mdapi.CThostFtdcMdSpi):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.connected = False
        self.logged_in = False

    def OnFrontConnected(self):
        print("🌐 [行情前置] 连接成功！")
        self.connected = True
        
        # 尝试登录
        req = mdapi.CThostFtdcReqUserLoginField()
        req.BrokerID = os.getenv("SIMNOW_BROKER_ID", "9999")
        req.UserID = os.getenv("SIMNOW_INVESTOR_ID", "")
        req.Password = os.getenv("SIMNOW_PASSWORD", "")
        
        print(f"🔑 [行情前置] 正在发起登录 (UserID: {req.UserID})...")
        self.api.ReqUserLogin(req, 1)

    def OnRspUserLogin(self, pRspUserLogin, pRspInfo, nRequestID, bIsLast):
        if pRspInfo and pRspInfo.ErrorID != 0:
            print(f"❌ [行情前置] 登录失败！错误代码: {pRspInfo.ErrorID}, 错误信息: {pRspInfo.ErrorMsg.decode('gbk')}")
        else:
            print("✅ [行情前置] 登录成功！")
            self.logged_in = True
            
            # 订阅测试品种，比如螺纹钢主力 rb2610
            contracts = ["rb2610"]
            # 转换成字节列表以兼容 C++ 接口
            self.api.SubscribeMarketData([c.encode('utf-8') for c in contracts], len(contracts))
            print(f"📥 [行情前置] 正在订阅行情: {contracts}")

    def OnRtnDepthMarketData(self, pDepthMarketData):
        if pDepthMarketData:
            print(f"📊 [实时行情] 品种: {pDepthMarketData.InstrumentID.decode('utf-8')}, "
                  f"最新价: {pDepthMarketData.LastPrice}, "
                  f"成交量: {pDepthMarketData.Volume}, "
                  f"持仓量: {pDepthMarketData.OpenInterest}, "
                  f"时间: {pDepthMarketData.UpdateTime.decode('utf-8')}.{pDepthMarketData.UpdateMillisec}")

class TestTraderSpi(tdapi.CThostFtdcTraderSpi):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.connected = False
        self.logged_in = False

    def OnFrontConnected(self):
        print("🌐 [交易前置] 连接成功！")
        self.connected = True
        
        # 交易登录需要先发出握手/认证（SimNow 公共环境或普通柜台通常也需要发送）
        req = tdapi.CThostFtdcReqUserLoginField()
        req.BrokerID = os.getenv("SIMNOW_BROKER_ID", "9999")
        req.UserID = os.getenv("SIMNOW_INVESTOR_ID", "")
        req.Password = os.getenv("SIMNOW_PASSWORD", "")
        
        print(f"🔑 [交易前置] 正在发起登录 (UserID: {req.UserID})...")
        self.api.ReqUserLogin(req, 1)

    def OnRspUserLogin(self, pRspUserLogin, pRspInfo, nRequestID, bIsLast):
        if pRspInfo and pRspInfo.ErrorID != 0:
            print(f"❌ [交易前置] 登录失败！错误代码: {pRspInfo.ErrorID}, 错误信息: {pRspInfo.ErrorMsg.decode('gbk')}")
        else:
            print("✅ [交易前置] 登录成功！")
            self.logged_in = True
            
            # 登录成功后查询账户资金
            req = tdapi.CThostFtdcQryTradingAccountField()
            req.BrokerID = os.getenv("SIMNOW_BROKER_ID", "9999")
            req.InvestorID = os.getenv("SIMNOW_INVESTOR_ID", "")
            time.sleep(0.5)
            self.api.ReqQryTradingAccount(req, 2)
            print("🔍 [交易前置] 正在查询账户资金...")

    def OnRspQryTradingAccount(self, pTradingAccount, pRspInfo, nRequestID, bIsLast):
        if pTradingAccount:
            print(f"💰 [资金状态] 可用资金: {pTradingAccount.Available:.2f}, "
                  f"静态权益: {pTradingAccount.PreBalance:.2f}, "
                  f"当前权益: {pTradingAccount.Balance:.2f}")

def main():
    load_dotenv()
    
    investor_id = os.getenv("SIMNOW_INVESTOR_ID")
    password = os.getenv("SIMNOW_PASSWORD")
    
    if not investor_id or not password:
        print("⚠️ 未检测到 SIMNOW_INVESTOR_ID 或 SIMNOW_PASSWORD。")
        print("💡 请先在工作区的 .env 文件中填入您的 SimNow 账号与密码。")
        sys.exit(0)
        
    broker_id = os.getenv("SIMNOW_BROKER_ID", "9999")
    trade_front = os.getenv("SIMNOW_TRADE_FRONT", "tcp://180.168.146.187:10130")
    md_front = os.getenv("SIMNOW_MD_FRONT", "tcp://180.168.146.187:10131")
    
    print("==================================================")
    print("🔌 启动 SimNow CTP 行情与交易双向连通测试")
    print(f"BrokerID: {broker_id} | UserID: {investor_id}")
    print(f"Trade Front: {trade_front}")
    print(f"MD Front: {md_front}")
    print("==================================================")

    # 创建临时的 CTP 流量文件目录，防止污染根目录
    os.makedirs("temp", exist_ok=True)

    # 1. 初始化行情 MD API
    print("📝 初始化行情前置机...")
    md_api = mdapi.CThostFtdcMdApi.CreateFtdcMdApi("temp/test_flow_md")
    md_spi = TestMdSpi(md_api)
    md_api.RegisterSpi(md_spi)
    md_api.RegisterFront(md_front)
    md_api.Init()

    # 2. 初始化交易 TD API
    print("📝 初始化交易前置机...")
    td_api = tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi("temp/test_flow_td")
    td_spi = TestTraderSpi(td_api)
    td_api.RegisterSpi(td_spi)
    td_api.RegisterFront(trade_front)
    td_api.Init()

    # 保持主线程活动以等待回调
    try:
        print("\n⏳ 正在监听行情与交易响应事件，按 Ctrl+C 退出测试...\n")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🔌 正在关闭 CTP 接口...")
    finally:
        md_api.Release()
        td_api.Release()
        print("✅ 接口释放完成，测试结束。")

if __name__ == "__main__":
    main()
