import unittest
import pandas as pd
from analysis.indicators import calculate_indicators
from database.db_manager import update_user_settings, get_user_settings

class TestStockBot(unittest.TestCase):
    def test_indicators(self):
        # 建立假數據
        data = {
            'date': pd.date_range(start='2023-01-01', periods=100),
            'open': [100]*100,
            'high': [110]*100,
            'low': [90]*100,
            'close': [105]*100,
            'volume': [1000]*100
        }
        df = pd.DataFrame(data)
        df = calculate_indicators(df)
        self.assertIn('macd', df.columns)
        self.assertIn('rsi', df.columns)
        self.assertIn('k', df.columns)

    def test_db(self):
        user_id = 99999
        update_user_settings(user_id, stock_id='2317', data_length=100)
        settings = get_user_settings(user_id)
        self.assertEqual(settings.stock_id, '2317')
        self.assertEqual(settings.data_length, 100)

if __name__ == '__main__':
    unittest.main()
