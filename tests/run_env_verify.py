import sys
import os
import getpass
from dotenv import load_dotenv

load_dotenv()

# 将项目根目录加入路径以便导入模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.ifind_loader import IFinDLoader, IFIND_INSTALLED
from data.db_manager import DBManager, PSYCOPG2_INSTALLED

def test_ifind():
    print("\n" + "-"*40)
    print("开始验证 同花顺 iFinD 接口")
    print("-"*40)
    if not IFIND_INSTALLED:
        print("❌ 错误: 环境中未找到 iFinDPy。")
        print("请确保已在 quant 环境中运行: pip install iFinDPy")
        return False
        
    env_user = os.getenv("IFIND_USERNAME", "")
    env_pass = os.getenv("IFIND_PASSWORD", "")
    
    if env_user and env_pass:
        print(f"检测到 .env 中已配置 iFinD 账号: {env_user}")
        username = env_user
        password = env_pass
    else:
        username = input("请输入 iFinD 账号 (按回车跳过验证): ").strip()
        if not username:
            print("⏩ 跳过 iFinD 验证。")
            return True
        password = getpass.getpass("请输入 iFinD 密码: ")
    
    print("正在尝试连接 iFinD 服务器...")
    loader = IFinDLoader()
    success = loader.login(username, password)
    
    if success:
        print("✅ iFinD 接口登录验证成功！API 权限正常。")
        loader.logout()
        return True
    else:
        print("❌ iFinD 登录失败，请检查账号密码或网络权限。")
        return False

def test_postgres():
    print("\n" + "-"*40)
    print("开始验证 PostgreSQL 数据库")
    print("-"*40)
    if not PSYCOPG2_INSTALLED:
        print("❌ 错误: 环境中未找到 psycopg2。")
        print("请确保已在 quant 环境中运行: pip install psycopg2-binary")
        return False
        
    env_db = os.getenv("PG_DBNAME", "quant_db")
    env_user = os.getenv("PG_USER", "postgres")
    env_pass = os.getenv("PG_PASSWORD", "")
    env_host = os.getenv("PG_HOST", "localhost")
    env_port = os.getenv("PG_PORT", "5432")

    if env_pass:
        print(f"检测到 .env 中已配置 PostgreSQL 密码，将自动尝试连接...")
        dbname = env_db
        user = env_user
        password = env_pass
        host = env_host
        port = env_port
    else:
        dbname = input("请输入 PostgreSQL 数据库名称 (按回车跳过验证，默认输入 quant_db): ").strip()
        if not dbname:
            print("⏩ 跳过 PostgreSQL 验证。")
            return True
            
        user = input("请输入 PostgreSQL 用户名 (默认 postgres): ").strip() or "postgres"
        password = getpass.getpass("请输入 PostgreSQL 密码: ")
        host = input("请输入主机地址 (默认 localhost): ").strip() or "localhost"
        port = input("请输入端口号 (默认 5432): ").strip() or "5432"
    
    print(f"正在尝试连接至 postgresql://{user}:***@{host}:{port}/{dbname} ...")
    try:
        # DBManager 在初始化时会自动尝试连接并执行建表
        db = DBManager(dbname=dbname, user=user, password=password, host=host, port=port)
        print("✅ PostgreSQL 数据库连接成功！自动建表功能验证通过。")
        return True
    except Exception as e:
        print(f"❌ PostgreSQL 连接或建表失败:\n{e}")
        print("请检查 PostgreSQL 服务是否已启动，以及对应的 Database 是否已通过客户端手动创建。")
        return False

if __name__ == "__main__":
    print("="*50)
    print("量化交易系统 Phase 2 - 实盘环境与数据接口联调脚本")
    print("注意: 本脚本不会在本地保存任何密码，关闭终端即焚")
    print("="*50)
    
    ifind_ok = test_ifind()
    pg_ok = test_postgres()
    
    print("\n" + "="*50)
    if ifind_ok and pg_ok:
        print("🎉 恭喜！Phase 2 外部环境依赖全部验证通过！")
    else:
        print("⚠️ 存在未通过的验证项，请参考上方错误提示进行修复。")
    print("="*50)
