from data_acquisition import get_historical_data
from strategy import calculate_ma, calculate_bollinger_bands, apply_strategy
import pandas as pd

def test_integration():
    print("Testing integration...")
    symbol = "2330.TW"
    df = get_historical_data(symbol, period="6mo")
    if df is None:
        print("Failed to fetch data")
        return

    print(f"Data fetched for {symbol}, rows: {len(df)}")

    df = calculate_ma(df)
    df = calculate_bollinger_bands(df)
    from strategy import calculate_rsi, calculate_macd
    df = calculate_rsi(df)
    df = calculate_macd(df)
    print("Indicators calculated")
    print(f"RSI: {df['RSI'].iloc[-1]}, MACD: {df['MACD'].iloc[-1]}")

    # Simulate institutional net buy
    mock_net_buy = 2000000
    df = apply_strategy(df, mock_net_buy)
    print("Strategy applied")

    latest = df.iloc[-1]
    print(f"Latest Close: {latest['Close']}")
    print(f"5MA: {latest['5MA']}, 10MA: {latest['10MA']}, 20MA: {latest['20MA']}")
    print(f"Strategy Signal: {latest['Strategy_Signal']}")

    print("Integration test passed!")

if __name__ == "__main__":
    test_integration()
