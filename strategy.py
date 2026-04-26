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

def apply_strategy(df, institutional_net_buy_3d=0):
    """
    Apply the selection logic:
    - 5MA > 10MA > 20MA
    - Close > 20MA
    - Institutional Net Buy (3 days) > 1000 sheets (1,000,000 shares)
    Note: TWSE data is in shares, 1 sheet = 1000 shares.
    """
    df = calculate_ma(df)
    df = check_ma_bullish_alignment(df)
    df = check_above_monthly_line(df)

    # 1000 sheets = 1,000,000 shares
    institutional_threshold = 1000 * 1000

    df['Strategy_Signal'] = (
        df['MA_Bullish'] &
        df['Above_20MA'] &
        (institutional_net_buy_3d > institutional_threshold)
    )
    return df

if __name__ == "__main__":
    # Small test
    data = {'Close': [100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120, 118, 116, 114, 112, 110, 108, 106, 104, 102, 100]}
    df = pd.DataFrame(data)
    df = calculate_ma(df)
    df = calculate_bollinger_bands(df)
    print(df.tail())
