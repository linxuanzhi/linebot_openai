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
    sync_stock_list()

    # 2. Start services
    threading.Thread(target=run_streamlit, daemon=True).start()
    threading.Thread(target=run_scheduler, daemon=True).start()

    # 3. Start Telegram Bot (Main Process)
    print("Starting Telegram Bot...")
    app = get_application()
    app.run_polling()
