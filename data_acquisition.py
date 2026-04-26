import yfinance as yf
import pandas as pd
import requests
import time
import os
import difflib
from datetime import datetime, timedelta
from FinMind.data import DataLoader

# Global Cache for Stock List
STOCK_LIST_DF = pd.DataFrame()

def sync_stock_list():
    """
    Fetch the latest TSEC and OTC stock symbols and names from TWSE/TPEx.
    """
    global STOCK_LIST_DF
    print("Syncing stock list from TWSE...")

    tsec_url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    otc_url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"

    all_data = []
    for url, suffix in [(tsec_url, ".TW"), (otc_url, ".TWO")]:
        try:
            response = requests.get(url)
            response.encoding = 'big5'
            # TWSE page is simple enough to parse with BS4 to avoid pandas column issues
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', {'class': 'h4'})
            rows = table.find_all('tr')

            for row in rows[1:]: # Skip header
                cols = row.find_all('td')
                if len(cols) < 1: continue
                text = cols[0].get_text().strip()
                if '　' in text:
                    code, name = text.split('　', 1)
                    if code.isdigit():
                        all_data.append({
                            'Code': code,
                            'Name': name,
                            'Full_Code': code + suffix
                        })
        except Exception as e:
            print(f"Error syncing {suffix} stocks: {e}")

    if all_data:
        STOCK_LIST_DF = pd.DataFrame(all_data)
        STOCK_LIST_DF = STOCK_LIST_DF.drop_duplicates(subset=['Code'])
        print(f"Sync complete. Total stocks: {len(STOCK_LIST_DF)}")
    return STOCK_LIST_DF

def find_stock(query):
    """
    Lookup stock code by code or name.
    Returns: (code, name, full_code) or (None, suggestions, None)
    """
    global STOCK_LIST_DF
    if STOCK_LIST_DF.empty:
        sync_stock_list()

    # 1. Check if query is a numeric code
    if query.isdigit():
        match = STOCK_LIST_DF[STOCK_LIST_DF['Code'] == query]
        if not match.empty:
            row = match.iloc[0]
            return row['Code'], row['Name'], row['Full_Code']

    # 2. Exact name match
    match = STOCK_LIST_DF[STOCK_LIST_DF['Name'] == query]
    if not match.empty:
        row = match.iloc[0]
        return row['Code'], row['Name'], row['Full_Code']

    # 3. Fuzzy match using difflib
    names = STOCK_LIST_DF['Name'].tolist()
    suggestions = difflib.get_close_matches(query, names, n=3, cutoff=0.3)
    return None, suggestions, None

def get_historical_data(full_code, period="1y", auto_adjust=True):
    """
    Fetch historical price data using yfinance.
    """
    try:
        stock = yf.Ticker(full_code)
        df = stock.history(period=period, auto_adjust=auto_adjust)
        return df
    except Exception as e:
        print(f"Error fetching data for {full_code}: {e}")
        return None

def get_recent_institutional_data(days=10):
    """
    Fetch institutional investor data via FinMind.
    """
    dl = DataLoader()
    token = os.getenv('FINMIND_TOKEN', '')
    if token:
        dl.login(api_token=token)

    current_date = datetime.now()
    daily_data = {}
    count = 0
    attempt = 0

    while count < days and attempt < 20:
        target_date = current_date - timedelta(days=attempt)
        if target_date.weekday() < 5:
            date_str = target_date.strftime('%Y-%m-%d')
            try:
                df = dl.taiwan_stock_institutional_investors(
                    data_id="",
                    start_date=date_str,
                    end_date=date_str
                )
                if not df.empty:
                    daily_data[date_str] = {}
                    for stock_id, group in df.groupby('stock_id'):
                        sitc = group[group['name'] == 'Investment_Trust']['buy'].sum() - \
                               group[group['name'] == 'Investment_Trust']['sell'].sum()
                        foreign = group[group['name'] == 'Foreign_Investor']['buy'].sum() - \
                                  group[group['name'] == 'Foreign_Investor']['sell'].sum()
                        daily_data[date_str][stock_id] = {'SITC': sitc, 'Foreign': foreign}
                    count += 1
            except:
                pass
            time.sleep(0.1)
        attempt += 1
    return daily_data

def get_fundamental_data(full_code):
    """
    Fetch fundamental metrics using yfinance.
    """
    try:
        ticker = yf.Ticker(full_code)
        info = ticker.info
        return {
            'pe': info.get('trailingPE', 'N/A'),
            'yield': info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 'N/A',
            'revenue_growth': info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 'N/A',
            'market_cap': info.get('marketCap', 'N/A')
        }
    except:
        return {'pe': 'N/A', 'yield': 'N/A', 'revenue_growth': 'N/A', 'market_cap': 'N/A'}
