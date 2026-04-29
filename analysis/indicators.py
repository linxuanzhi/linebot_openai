import pandas as pd
import numpy as np
import ta

def calculate_indicators(df):
    if df.empty or len(df) < 20:
        return df

    # MACD
    macd = ta.trend.MACD(close=df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_diff'] = macd.macd_diff()

    # KDJ
    stoch = ta.momentum.StochasticOscillator(high=df['high'], low=df['low'], close=df['close'], n=14, d_n=3)
    df['k'] = stoch.stoch()
    df['d'] = stoch.stoch_signal()
    df['j'] = 3 * df['k'] - 2 * df['d']

    # 均線 (MA)
    df['ma5'] = ta.trend.sma_indicator(df['close'], n=5)
    df['ma10'] = ta.trend.sma_indicator(df['close'], n=10)
    df['ma20'] = ta.trend.sma_indicator(df['close'], n=20)
    df['ma60'] = ta.trend.sma_indicator(df['close'], n=60)

    # RSI
    df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], n=14).rsi()

    # 布林通道 (Bollinger Bands)
    bb = ta.volatility.BollingerBands(close=df['close'], n=20, ndev=2)
    df['bb_h'] = bb.bollinger_hband()
    df['bb_l'] = bb.bollinger_lband()
    df['bb_m'] = bb.bollinger_mavg()

    # 威廉指標 (Williams %R)
    df['wr'] = ta.momentum.WilliamsRIndicator(high=df['high'], low=df['low'], close=df['close'], lbp=14).wr()

    # 乖離率 (Bias)
    df['bias'] = (df['close'] - df['ma20']) / df['ma20'] * 100

    # VOL (Volume MA)
    df['vol_ma5'] = ta.trend.sma_indicator(df['volume'], n=5)

    # 寶塔線 (Pagoda Line)
    df['pagoda'] = 0
    for i in range(3, len(df)):
        prev_max = df['high'].iloc[i-3:i].max()
        prev_min = df['low'].iloc[i-3:i].min()
        if df['close'].iloc[i] > prev_max:
            df.loc[df.index[i], 'pagoda'] = 1
        elif df['close'].iloc[i] < prev_min:
            df.loc[df.index[i], 'pagoda'] = -1
        else:
            df.loc[df.index[i], 'pagoda'] = df['pagoda'].iloc[i-1]

    return df

def calculate_risk_metrics(df, market_df=None):
    """
    計算風險係數：波動率與 Beta。
    如果沒有提供大盤數據，則 Beta 默認為 1.0。
    """
    if df.empty or len(df) < 30:
        return {"volatility": 0.0, "beta": 1.0}

    # 波動率 (Volatility)
    close_prices = df['close'].astype(float)
    returns = close_prices.pct_change().dropna()
    volatility = returns.std() * np.sqrt(252)

    beta = 1.0
    if market_df is not None and not market_df.empty:
        # 簡易 Beta 計算：Cov(r_s, r_m) / Var(r_m)
        market_returns = market_df['close'].pct_change().dropna()
        # 對齊時間
        combined = pd.concat([returns, market_returns], axis=1).dropna()
        if len(combined) > 20:
            cov_matrix = np.cov(combined.iloc[:, 0], combined.iloc[:, 1])
            beta = cov_matrix[0, 1] / cov_matrix[1, 1]

    return {
        "volatility": float(volatility) if not np.isnan(volatility) else 0.0,
        "beta": float(beta) if not np.isnan(beta) else 1.0
    }
