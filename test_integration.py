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

    # Simulate institutional history
    mock_history = [{'SITC': 1000, 'Foreign': 1000}] * 3

    is_matched, risk = apply_strategy(df, mock_history)
    print(f"Strategy applied, Matched: {is_matched}")
    if is_matched:
        print(f"Buy: {risk['buy_price']}, SL: {risk['stop_loss']}, Target: {risk['target_price']}")

    print("Integration test passed!")

if __name__ == "__main__":
    test_integration()
