import os
import threading
import subprocess
import schedule
import time
import asyncio
from datetime import datetime
from data_acquisition import sync_stock_list
from tg_bot_v3 import get_application

def run_streamlit():
    """Launch Streamlit dashboard."""
    subprocess.Popen([
        "streamlit", "run", "dashboard.py",
        "--server.port", os.getenv("PORT", "8501"),
        "--server.address", "0.0.0.0"
    ])

def run_scheduler():
    """Daily automated tasks at 15:30."""
    def job():
        print(f"[{datetime.now()}] Running daily post-market scan...")
        # Implementation for automated push would go here

    schedule.every().day.at("15:30").do(job)
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    # 1. Sync data at startup
    try:
        sync_stock_list()
    except Exception as e:
        print(f"Startup Sync Error: {e}")

    # 2. Start services
    print("Starting Streamlit...")
    threading.Thread(target=run_streamlit, daemon=True).start()
    print("Starting Scheduler...")
    threading.Thread(target=run_scheduler, daemon=True).start()

    # 3. Start Telegram Bot (Main Process)
    token = os.getenv('TG_TOKEN')
    if not token:
        print("CRITICAL ERROR: TG_TOKEN not found in environment.")
    else:
        print(f"Starting Telegram Bot with token: {token[:10]}...")
        app = get_application()
        print("Bot is now polling...")
        app.run_polling(drop_pending_updates=True)
