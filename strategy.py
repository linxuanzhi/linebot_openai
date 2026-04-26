import pandas as pd
import numpy as np

def calculate_ma(df, windows=[5, 10, 20, 60]):
    """
    Calculate Moving Averages.
    """
    for window in windows:
        df[f'{window}MA'] = df['Close'].rolling(window=window).mean()
    return df

def calculate_bollinger_bands(df, window=20, num_std=2):
    """
    Calculate Bollinger Bands.
    """
    rolling_mean = df['Close'].rolling(window=window).mean()
    rolling_std = df['Close'].rolling(window=window).std()
    df['BB_Middle'] = rolling_mean
    df['BB_Upper'] = rolling_mean + (rolling_std * num_std)
    df['BB_Lower'] = rolling_mean - (rolling_std * num_std)
    return df

def calculate_rsi(df, window=14):
    """
    Calculate Relative Strength Index (RSI).
    """
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def calculate_macd(df, fast=12, slow=26, signal=9):
    """
    Calculate MACD.
    """
    exp1 = df['Close'].ewm(span=fast, adjust=False).mean()
    exp2 = df['Close'].ewm(span=slow, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal_Line'] = df['MACD'].ewm(span=signal, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal_Line']
    return df

def check_ma_bullish_alignment(df):
    """
    Check for 5MA > 10MA > 20MA.
    """
    if '5MA' not in df.columns or '10MA' not in df.columns or '20MA' not in df.columns:
        df = calculate_ma(df)

    df['MA_Bullish'] = (df['5MA'] > df['10MA']) & (df['10MA'] > df['20MA'])
    return df

def check_above_monthly_line(df):
    """
    Check if Close > 20MA.
    """
    if '20MA' not in df.columns:
        df = calculate_ma(df)

    df['Above_20MA'] = df['Close'] > df['20MA']
    return df

def apply_strategy(df, institutional_history_list, short_ma=20, long_ma=60, sl_percent=10):
    """
    Apply the selection logic:
    - Price > Short MA > Long MA
    - SITC continuous net buy >= 3 days
    - Volume expansion (Today > 5-day avg volume)
    Returns: (bool, risk_metrics)
    """
    max_ma = max(short_ma, long_ma)
    if len(df) < max_ma:
        return False, {}

    df = calculate_ma(df, windows=[short_ma, long_ma])
    short_col = f'{short_ma}MA'
    long_col = f'{long_ma}MA'

    latest = df.iloc[-1]

    # 1. Price > Short MA > Long MA
    alignment = latest['Close'] > latest[short_col] > latest[long_col]

    # 2. SITC continuous net buy >= 3 days
    if len(institutional_history_list) < 3:
        sitc_cont_buy = False
    else:
        sitc_cont_buy = all(d.get('SITC', 0) > 0 for d in institutional_history_list[:3])

    # 3. Volume expansion
    vol_5ma = df['Volume'].tail(5).mean()
    vol_expansion = latest['Volume'] > vol_5ma

    is_matched = alignment and sitc_cont_buy and vol_expansion

    risk_metrics = {}
    if is_matched:
        buy_price = latest['Close']
        stop_loss = buy_price * (1 - sl_percent/100)
        target_price = buy_price + (buy_price - stop_loss) * 2
        risk_metrics = {
            'buy_price': buy_price,
            'stop_loss': stop_loss,
            'target_price': target_price
        }

    return is_matched, risk_metrics

def strong_rebound_screening(df, institutional_history_list):
    """
    Technical:
    - Today's Close = 20-day High
    - Volume > 1.5 * 5-day average Volume
    Chip:
    - SITC continuous net buy > 3 days
    - Foreign Net Buy today (and was selling before, but the request says '轉賣為買',
      we will simplify to 'Today Foreign > 0 and Yesterday Foreign < 0')
    Filter:
    - 5-day average Volume > 500 sheets (500,000 shares)
    """
    if len(df) < 20:
        return False

    # 1. Technical
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    is_20d_high = latest['Close'] >= df['Close'].tail(20).max()

    vol_5ma = df['Volume'].tail(5).mean()
    vol_spike = latest['Volume'] > 1.5 * vol_5ma

    # Filter low volume (500 sheets = 500,000 shares)
    is_not_cold = vol_5ma > 500 * 1000

    # 2. Chip (institutional_history_list is list of daily_data for the stock)
    # [{date1: {SITC: x, Foreign: y}}, {date2: ...}] - latest to oldest
    if len(institutional_history_list) < 3:
        return False

    sitc_cont_buy = all(d.get('SITC', 0) > 0 for d in institutional_history_list[:3])

    foreign_turn_buy = (institutional_history_list[0].get('Foreign', 0) > 0 and
                        institutional_history_list[1].get('Foreign', 0) < 0)

    if is_20d_high and vol_spike and is_not_cold and sitc_cont_buy and foreign_turn_buy:
        return True

    return False

if __name__ == "__main__":
    # Small test
    data = {'Close': [100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120, 118, 116, 114, 112, 110, 108, 106, 104, 102, 100]}
    df = pd.DataFrame(data)
    df = calculate_ma(df)
    df = calculate_bollinger_bands(df)
    print(df.tail())
