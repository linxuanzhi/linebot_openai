import schedule
import time
import datetime
from data_acquisition import get_all_tsec_symbols, get_historical_data, get_recent_institutional_data
from strategy import strong_rebound_screening
from notifier import send_line_notify, format_stock_message

def run_stock_bot():
    print(f"[{datetime.datetime.now()}] Starting Stock Bot...")

    # 1. Get all symbols (limit for demo to avoid rate limiting)
    symbols = get_all_tsec_symbols()
    if not symbols:
        return

    print(f"Total symbols found: {len(symbols)}")

    # 2. Fetch recent institutional data (last 5 days to be safe for continuous checks)
    daily_institutional_data = get_recent_institutional_data(5)

    # Sort dates to get latest to oldest
    sorted_dates = sorted(daily_institutional_data.keys(), reverse=True)

    matched_stocks = []

    # 3. Screen stocks (limit to first 100 for demo efficiency)
    for symbol in symbols[:100]:
        try:
            full_code = f"{symbol}.TW"
            df = get_historical_data(full_code, period="1mo")

            if df is None or df.empty:
                continue

            # Extract historical institutional data for this specific stock
            history_list = []
            for d_key in sorted_dates:
                if symbol in daily_institutional_data[d_key]:
                    history_list.append(daily_institutional_data[d_key][symbol])

            if strong_rebound_screening(df, history_list):
                latest_price = df['Close'].iloc[-1]
                matched_stocks.append({
                    'code': symbol,
                    'name': '股票', # Could fetch name if needed
                    'price': f"{latest_price:.2f}",
                    'reason': "20日新高 + 量增 + 投信連買 + 外資轉買",
                    'time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
                })
        except Exception as e:
            print(f"Error processing {symbol}: {e}")

        time.sleep(0.5) # Prevent blocking

    # 4. Notify
    if matched_stocks:
        print(f"Found {len(matched_stocks)} matched stocks.")
        for stock in matched_stocks:
            msg = format_stock_message(stock)
            send_line_notify(msg)
    else:
        print("No matches found today.")

def job():
    # Only run on weekdays
    if datetime.datetime.now().weekday() < 5:
        run_stock_bot()

# Schedule for 15:30 daily
schedule.every().day.at("15:30").do(job)

if __name__ == "__main__":
    print("Stock Bot is running and scheduled for 15:30...")
    # For testing: run once immediately
    # job()

    while True:
        schedule.run_pending()
        time.sleep(60)
