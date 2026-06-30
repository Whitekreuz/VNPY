import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data.db_manager import DBManager

def clear_database():
    load_dotenv()
    db_name = os.getenv("PG_DBNAME_PROD", "quant_db_prod")
    db_user = os.getenv("PG_USER", "postgres")
    db_pass = os.getenv("PG_PASSWORD", "")
    db_host = os.getenv("PG_HOST", "localhost")
    db_port = os.getenv("PG_PORT", "5432")
    
    ans = input(f"⚠️ 警告: 即将清空数据库 {db_name} 中的 bardata (K线表) 和 main_contract_mapping (换月映射表)。该操作不可逆！是否继续？(y/n): ")
    if ans.lower() != 'y':
        print("操作已取消。")
        return
        
    try:
        db = DBManager(dbname=db_name, user=db_user, password=db_pass, host=db_host, port=db_port)
        with db.conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE bardata;")
            cur.execute("TRUNCATE TABLE main_contract_mapping;")
            db.conn.commit()
        print("✅ 数据库清空成功！可以开始全新的数据下载。")
    except Exception as e:
        print(f"❌ 清空数据库失败: {e}")

if __name__ == "__main__":
    clear_database()
