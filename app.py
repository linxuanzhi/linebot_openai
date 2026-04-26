import os
import subprocess
import time
import schedule
import threading
from datetime import datetime
from tg_bot import start, pick, run_screening, generate_chart
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler
from dotenv import load_dotenv

load_dotenv()

def run_streamlit():
    """Run the Streamlit dashboard."""
    subprocess.Popen(["streamlit", "run", "dashboard.py", "--server.port", os.getenv("PORT", "8501"), "--server.address", "0.0.0.0"])

def run_tg_bot():
    """Run the Telegram Bot."""
    token = os.getenv('TG_TOKEN')
    if not token:
        print("TG_TOKEN not found, skipping bot.")
        return

    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('pick', pick))

    # Run polling in the background
    application.run_polling()

def scheduled_task():
    """Task to run every day at 15:30."""
    print(f"[{datetime.now()}] Running scheduled screening...")
    token = os.getenv('TG_TOKEN')
    chat_id = os.getenv('CHAT_ID')
    if not token or not chat_id:
        return
        
    async def run():
        from telegram import Bot
        bot = Bot(token)
        results = await run_screening(limit=50)
        if not results:
            await bot.send_message(chat_id, "今日盤後掃描：無符合條件個股。")
            return

        await bot.send_message(chat_id, f"🔔 盤後自動推播：今日共選出 {len(results)} 檔個股")
        for symbol, df, risk in results:
            chart_path = generate_chart(df, symbol)
            msg = f"📍 股票：{symbol}\n💰 買入價：{risk['buy_price']:.2f}\n🚨 停損價：{risk['stop_loss']:.2f}\n📈 目標價：{risk['target_price']:.2f}"
            keyboard = [[InlineKeyboardButton("查看基本面", url=f"https://tw.stock.yahoo.com/quote/{symbol}")]]
            await bot.send_photo(chat_id, photo=open(chart_path, 'rb'), caption=msg, reply_markup=InlineKeyboardMarkup(keyboard))
            os.remove(chart_path)

    asyncio.run(run())

def run_scheduler():
    schedule.every().day.at("15:30").do(scheduled_task)
    while True:
        schedule.run_pending()
        time.sleep(60)

import asyncio

if __name__ == "__main__":
    # Start Streamlit in a separate process
    threading.Thread(target=run_streamlit, daemon=True).start()

    # Start Scheduler in a separate thread
    threading.Thread(target=run_scheduler, daemon=True).start()

    # Start TG Bot (blocking)
    run_tg_bot()
