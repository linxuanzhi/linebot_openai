import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta

def get_historical_data(symbol, period="1y"):
    """
    Fetch historical price data using yfinance.
    symbol: e.g., '2330.TW' or '2330'
    """
    if not symbol.endswith(".TW") and not symbol.endswith(".TWO"):
        # Default to TSEC if no suffix is provided, but this is a simplification
        symbol = f"{symbol}.TW"

    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period=period)
        if df.empty:
            # Try .TWO if .TW failed
            if symbol.endswith(".TW"):
                symbol = symbol.replace(".TW", ".TWO")
                stock = yf.Ticker(symbol)
                df = stock.history(period=period)

            if df.empty:
                print(f"No data found for {symbol}")
                return None
        return df
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

def minguo_to_gregorian(date_str):
    """
    Convert Minguo date string (e.g., '112/05/20' or '112/5/20') to Gregorian date object.
    """
    try:
        # Handle variations like '112/05/20' or ' 112/05/20'
        clean_date = date_str.strip()
        parts = clean_date.split('/')
        if len(parts) != 3:
            return None
        year = int(parts[0]) + 1911
        month = int(parts[1])
        day = int(parts[2])
        return datetime(year, month, day)
    except Exception as e:
        print(f"Error converting Minguo date {date_str}: {e}")
        return None

def get_institutional_investors(date_obj=None):
    """
    Crawl institutional investors net buy/sell from TWSE.
    date_obj: datetime object
    """
    if date_obj is None:
        date_obj = datetime.now()

    date_str = date_obj.strftime('%Y%m%d')
    url = f"https://www.twse.com.tw/rwd/zh/fund/T86W?date={date_str}&selectType=ALL&response=json"

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()

        if data['stat'] != 'OK':
            print(f"No institutional data for {date_str}")
            return None

        columns = data['fields']
        rows = data['data']
        df = pd.DataFrame(rows, columns=columns)

        # Data cleaning: remove commas and convert to numeric
        # Columns: '證券代號', '證券名稱', '三大法人買賣超股數' (Index 18 usually)
        # However, let's find the correct index by name
        target_col = '三大法人買賣超股數'
        if target_col in df.columns:
            df[target_col] = df[target_col].str.replace(',', '').astype(float)

        return df
    except Exception as e:
        print(f"Error crawling institutional data for {date_str}: {e}")
        return None

def get_recent_institutional_data(days=3):
    """
    Get aggregated institutional data for the last few days.
    """
    aggregated_data = {}
    current_date = datetime.now()
    count = 0
    attempt = 0

    while count < days and attempt < 10:
        target_date = current_date - timedelta(days=attempt)
        # Skip weekends (approximate)
        if target_date.weekday() < 5:
            df = get_institutional_investors(target_date)
            if df is not None:
                for _, row in df.iterrows():
                    code = row['證券代號'].strip()
                    net_buy = float(row['三大法人買賣超股數'].replace(',', '')) if isinstance(row['三大法人買賣超股數'], str) else row['三大法人買賣超股數']
                    aggregated_data[code] = aggregated_data.get(code, 0) + net_buy
                count += 1
            time.sleep(1) # Rate limiting
        attempt += 1

    return aggregated_data

if __name__ == "__main__":
    # Test
    print("Testing get_historical_data for 2330.TW...")
    df = get_historical_data("2330.TW")
    if df is not None:
        print(df.tail())
