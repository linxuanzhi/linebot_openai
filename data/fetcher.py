import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
import os
from datetime import datetime, timedelta

def fetch_stock_data(stock_id, days=180):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    # 統一台股代號格式
    if stock_id.isdigit():
        # 嘗試 .TW (上市)
        formatted_id = f"{stock_id}.TW"
    else:
        formatted_id = stock_id

    try:
        df = yf.download(formatted_id, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)
        if df.empty and stock_id.isdigit():
            # 嘗試 .TWO (上櫃)
            formatted_id = f"{stock_id}.TWO"
            df = yf.download(formatted_id, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)

        if not df.empty:
            df.reset_index(inplace=True)
            df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
            df.rename(columns={'Date': 'date', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}, inplace=True)
            return df
    except Exception as e:
        print(f"yfinance error for {stock_id}: {e}")

    return pd.DataFrame()

def fetch_institutional_investors(stock_id):
    token = os.getenv('FINMIND_TOKEN', '')
    dl = DataLoader()
    if token:
        dl.login_by_token(token)

    try:
        # 獲取最近 7 天的三大法人資料
        df = dl.taiwan_stock_institutional_investors(
            stock_id=stock_id,
            start_date=(datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        )
        return df
    except Exception as e:
        print(f"FinMind error: {e}")
        return pd.DataFrame()

def get_hot_stocks():
    """
    獲取熱門股票清單 (簡化版：回傳台灣前 20 大權值股代號)
    """
    return ['2330', '2317', '2454', '2308', '2382', '2412', '2881', '2882', '2303', '3711', '2357', '3231', '2886', '2603', '2891', '1301', '1303', '2884', '2002', '2885']
