import yfinance as yf
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, timedelta
from FinMind.data import DataLoader
from fuzzywuzzy import process

def get_historical_data(symbol, period="1y", auto_adjust=True):
    """
    Fetch historical price data using yfinance.
    symbol: e.g., '2330.TW' or '2330'
    auto_adjust: If True, returns adjusted price to handle gaps from dividends/splits.
    """
    if not symbol.endswith(".TW") and not symbol.endswith(".TWO"):
        symbol = f"{symbol}.TW"

    try:
        stock = yf.Ticker(symbol)
        # yfinance history() by default returns adjusted prices if auto_adjust=True
        df = stock.history(period=period, auto_adjust=auto_adjust)
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

def get_recent_institutional_data(days=10):
    """
    Get daily institutional data for the last few days for all stocks.
    Returns a dict: {date: {code: net_buy}}
    """
    daily_data = {}
    current_date = datetime.now()
    count = 0
    attempt = 0

    # Try using FinMind if possible, or fallback to TWSE crawler
    dl = DataLoader()

    while count < days and attempt < 20:
        target_date = current_date - timedelta(days=attempt)
        if target_date.weekday() < 5:
            date_str = target_date.strftime('%Y-%m-%d')
            try:
                # FinMind Institutional Data
                df = dl.taiwan_stock_institutional_investors(
                    data_id="", # Empty means all
                    start_date=date_str,
                    end_date=date_str
                )
                if not df.empty:
                    daily_data[date_str] = {}
                    # Group by stock_id
                    for stock_id, group in df.groupby('stock_id'):
                        sitc = group[group['name'] == 'Investment_Trust']['buy'].sum() - \
                               group[group['name'] == 'Investment_Trust']['sell'].sum()
                        foreign = group[group['name'] == 'Foreign_Investor']['buy'].sum() - \
                                  group[group['name'] == 'Foreign_Investor']['sell'].sum()
                        total = group['buy'].sum() - group['sell'].sum()

                        daily_data[date_str][stock_id] = {
                            'SITC': sitc,
                            'Foreign': foreign,
                            'Total': total
                        }
                    count += 1
                else:
                    # Fallback to TWSE crawler
                    df_twse = get_institutional_investors(target_date)
                    if df_twse is not None:
                        daily_data[date_str] = {}
                        for _, row in df_twse.iterrows():
                            code = row['證券代號'].strip()
                            try:
                                sitc_net = float(row['投信買賣超股數'].replace(',', '')) if isinstance(row['投信買賣超股數'], str) else row['投信買賣超股數']
                                foreign_net = float(row['外資及陸資買賣超股數(不含外資自營商)'].replace(',', '')) if isinstance(row['外資及陸資買賣超股數(不含外資自營商)'], str) else row['外資及陸資買賣超股數(不含外資自營商)']
                                total_net = float(row['三大法人買賣超股數'].replace(',', '')) if isinstance(row['三大法人買賣超股數'], str) else row['三大法人買賣超股數']

                                daily_data[date_str][code] = {
                                    'SITC': sitc_net,
                                    'Foreign': foreign_net,
                                    'Total': total_net
                                }
                            except:
                                continue
                        count += 1
            except Exception as e:
                print(f"Error fetching institutional data for {date_str}: {e}")

            time.sleep(0.5)
        attempt += 1

    return daily_data

def get_margin_trading(date_obj=None):
    """
    Crawl margin trading data (融資融券) from TWSE.
    """
    if date_obj is None:
        date_obj = datetime.now()
    date_str = date_obj.strftime('%Y%m%d')
    url = f"https://www.twse.com.tw/rwd/zh/margin/MI_MARGN?date={date_str}&selectType=ALLSEL&response=json"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data['stat'] != 'OK':
            return None
        return pd.DataFrame(data['data'], columns=data['fields'])
    except:
        return None

def get_all_tsec_data():
    """
    Fetch all stock symbols and names from TWSE.
    """
    url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    try:
        response = requests.get(url)
        df = pd.read_html(response.text)[0]
        df.columns = df.iloc[0]
        df = df.iloc[2:]
        # Filter for stocks (format: "Code Name")
        df['Code'] = df['有價證券代號及名稱'].str.split('　').str[0]
        df['Name'] = df['有價證券代號及名稱'].str.split('　').str[1]
        # Keep only numeric codes (stocks)
        df = df[df['Code'].str.isdigit()]
        return df[['Code', 'Name']]
    except Exception as e:
        print(f"Error fetching symbols: {e}")
        return pd.DataFrame()

def get_all_tsec_symbols():
    """
    Fetch all stock symbols from TWSE.
    """
    df = get_all_tsec_data()
    if df.empty:
        return []
    return df['Code'].tolist()

def lookup_stock_code(query):
    """
    Lookup stock code by name or code with fuzzy matching.
    """
    # If query is numeric, assume it's a code
    if query.isdigit():
        return query

    df = get_all_tsec_data()
    if df.empty:
        return None

    # Exact match
    match = df[df['Name'] == query]
    if not match.empty:
        return match.iloc[0]['Code']

    # Fuzzy match
    names = df['Name'].tolist()
    best_match, score = process.extractOne(query, names)
    if score >= 70: # Confidence threshold
        return df[df['Name'] == best_match].iloc[0]['Code']

    return None

def get_fundamental_data(symbol):
    """
    Fetch fundamental data (PE, Yield, Revenue).
    """
    if not symbol.endswith(".TW") and not symbol.endswith(".TWO"):
        symbol = f"{symbol}.TW"

    data = {}
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        data['pe'] = info.get('trailingPE', 'N/A')
        data['yield'] = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 'N/A'
        data['revenue_growth'] = info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 'N/A'
        data['market_cap'] = info.get('marketCap', 'N/A')
        data['name'] = info.get('longName', symbol)
    except:
        data['pe'] = 'N/A'
        data['yield'] = 'N/A'
        data['revenue_growth'] = 'N/A'
    return data

if __name__ == "__main__":
    # Test
    print("Testing get_historical_data for 2330.TW...")
    df = get_historical_data("2330.TW")
    if df is not None:
        print(df.tail())
