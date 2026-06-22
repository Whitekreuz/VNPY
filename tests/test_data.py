import unittest
import sys
import os
from datetime import datetime

# 将项目根目录加入路径以便导入
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.models import BarData

class TestDataModules(unittest.TestCase):
    def test_bar_data_creation(self):
        bar = BarData(
            symbol="rb2310",
            exchange="SHFE",
            datetime=datetime(2023, 1, 1, 9, 30),
            open_price=4000.0,
            high_price=4010.0,
            low_price=3990.0,
            close_price=4005.0,
            volume=100
        )
        self.assertEqual(bar.vt_symbol, "rb2310.SHFE")
        self.assertEqual(bar.open_price, 4000.0)
        
    def test_ifind_loader_import(self):
        # 测试在未真实登录环境下的导入和实例化是否正常
        try:
            from data.ifind_loader import IFinDLoader
            loader = IFinDLoader()
            self.assertFalse(loader.connected)
        except ImportError as e:
            # 环境中未安装 pandas 或 psycopg2 时跳过
            self.skipTest(f"跳过 ifind_loader 测试，由于依赖缺失: {e}")
        except Exception as e:
            self.fail(f"导入 IFinDLoader 失败: {e}")

if __name__ == "__main__":
    unittest.main()
