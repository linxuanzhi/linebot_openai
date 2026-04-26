import os
import asyncio
import logging
import mplfinance as mpf
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from data_acquisition import get_all_tsec_symbols, get_historical_data, get_recent_institutional_data
from strategy import apply_strategy, calculate_ma, calculate_bollinger_bands
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def generate_chart(df, symbol):
    """
    Generate a candlestick chart with MA20 and Bollinger Bands.
    """
    df = calculate_ma(df, windows=[20])
    df = calculate_bollinger_bands(df)

    # Save to buffer
    file_path = f"{symbol}_chart.png"

    # Custom style
    mc = mpf.make_marketcolors(up='r', down='g', inherit=True)
    s = mpf.make_mpf_style(base_mpf_style='charles', marketcolors=mc)

    # Add plots
    add_plots = [
        mpf.make_addplot(df['20MA'], color='blue', width=1),
        mpf.make_addplot(df['BB_Upper'], color='gray', linestyle='dash', width=0.8),
        mpf.make_addplot(df['BB_Lower'], color='gray', linestyle='dash', width=0.8)
    ]

    mpf.plot(df.tail(60), type='candle', style=s, addplot=add_plots,
             title=f"{symbol} Analysis", savefig=file_path)
    return file_path

async def run_screening(limit=30):
    """
    Shared screening logic for /pick and scheduled push.
    """
    symbols = get_all_tsec_symbols()[:limit]
    daily_institutional_data = get_recent_institutional_data(5)
    sorted_dates = sorted(daily_institutional_data.keys(), reverse=True)

    results = []
    for symbol in symbols:
        df = get_historical_data(symbol, period="3mo")
        if df is None or df.empty:
            continue

        history_list = []
        for d_key in sorted_dates:
            if symbol in daily_institutional_data[d_key]:
                history_list.append(daily_institutional_data[d_key][symbol])

        is_matched, risk = apply_strategy(df, history_list)
        if is_matched:
            results.append((symbol, df, risk))
    return results

async def pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /pick command.
    """
    await update.message.reply_text("正在進行選股分析 (約需 1 分鐘)，請稍候...")

    matched_results = await run_screening(limit=20) # Limit for speed

    if not matched_results:
        await update.message.reply_text("今日無符合條件的股票。")
        return

    for symbol, df, risk in matched_results:
        chart_path = generate_chart(df, symbol)

        msg = f"📍 股票：{symbol}\n"
        msg += f"💰 買入價：{risk['buy_price']:.2f}\n"
        msg += f"🚨 停損價：{risk['stop_loss']:.2f}\n"
        msg += f"📈 目標價：{risk['target_price']:.2f}\n"
        msg += "━━━━━━━━━━━━━━\n"
        msg += "⚠️ 提示：股價跌破停損價請即時出場！"

        keyboard = [[InlineKeyboardButton("查看基本面", url=f"https://tw.stock.yahoo.com/quote/{symbol}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_photo(photo=open(chart_path, 'rb'), caption=msg, reply_markup=reply_markup)
        os.remove(chart_path)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("歡迎使用台股分析機器人！輸入 /pick 開始選股。")

if __name__ == '__main__':
    token = os.getenv('TG_TOKEN')
    if not token:
        print("Please set TG_TOKEN in .env file")
    else:
        application = ApplicationBuilder().token(token).build()

        start_handler = CommandHandler('start', start)
        pick_handler = CommandHandler('pick', pick)

        application.add_handler(start_handler)
        application.add_handler(pick_handler)

        application.run_polling()
