import os
import asyncio
import logging
import mplfinance as mpf
import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from data_acquisition import get_all_tsec_symbols, get_historical_data, get_recent_institutional_data, lookup_stock_code, get_fundamental_data
from strategy import apply_strategy, calculate_ma, calculate_bollinger_bands
from dotenv import load_dotenv
from font_setup import setup_chinese_font

load_dotenv()
setup_chinese_font()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def generate_mpf_chart(df, symbol, ma_days=20):
    """
    Generate chart with specific MA and Bollinger Bands.
    """
    df = calculate_ma(df, windows=[ma_days])
    df = calculate_bollinger_bands(df)

    file_path = f"{symbol}_{ma_days}_chart.png"

    # Render-friendly style
    mc = mpf.make_marketcolors(up='r', down='g', inherit=True)
    s = mpf.make_mpf_style(base_mpf_style='charles', marketcolors=mc)

    ma_col = f"{ma_days}MA"
    add_plots = [
        mpf.make_addplot(df[ma_col], color='blue', width=1),
        mpf.make_addplot(df['BB_Upper'], color='gray', linestyle='dash', width=0.8),
        mpf.make_addplot(df['BB_Lower'], color='gray', linestyle='dash', width=0.8)
    ]

    # We will handle font issue in a later step, for now just plot
    mpf.plot(df.tail(60), type='candle', style=s, addplot=add_plots,
             title=f"{symbol} MA{ma_days}", savefig=file_path)
    return file_path

def get_stock_report(symbol, code):
    """
    Generate the text report for a stock.
    """
    df = get_historical_data(code, period="3mo")
    latest = df.iloc[-1]
    fund = get_fundamental_data(code)

    sl_percent = 10
    stop_loss = latest['Close'] * (1 - sl_percent/100)
    target = latest['Close'] + (latest['Close'] - stop_loss) * 2

    report = f"📄 【{symbol} ({code}) 整合報告】\n"
    report += f"━━━━━━━━━━━━━━\n"
    report += f"💰 現價：{latest['Close']:.2f}\n"
    report += f"🔴 10% 停損價：{stop_loss:.2f}\n"
    report += f"🟢 目標價：{target:.2f}\n"
    report += f"━━━━━━━━━━━━━━\n"
    report += f"📊 本益比 (PE)：{fund['pe']}\n"
    report += f"🔹 殖利率：{fund['yield'] if fund['yield'] == 'N/A' else f'{fund['yield']:.2f}%'}\n"
    report += f"🔹 營收年增率：{fund['revenue_growth'] if fund['revenue_growth'] == 'N/A' else f'{fund['revenue_growth']:.2f}%'}"
    return report

async def query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /query command.
    """
    if not context.args:
        await update.message.reply_text("請輸入股票代碼或名稱。例如：/query 台積電 或 /query 2330")
        return

    query_text = context.args[0]
    code = lookup_stock_code(query_text)

    if not code:
        await update.message.reply_text(f"❌ 找不到股票：{query_text}")
        return

    report = get_stock_report(query_text, code)

    keyboard = [
        [
            InlineKeyboardButton("看 20MA 圖", callback_data=f"upd_20_{code}"),
            InlineKeyboardButton("看 60MA 圖", callback_data=f"upd_60_{code}"),
            InlineKeyboardButton("看 120MA 圖", callback_data=f"upd_120_{code}")
        ]
    ]

    await update.message.reply_text(report, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle Inline Keyboard updates (Callback Query).
    """
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("upd_"):
        return

    # upd_days_code
    parts = data.split('_')
    ma_days = int(parts[1])
    code = parts[2]

    df = get_historical_data(code, period="1y")
    chart_path = generate_mpf_chart(df, code, ma_days=ma_days)

    report = get_stock_report(code, code) # Simplified

    # Update message with photo and text
    await query.edit_message_media(
        media=InputMediaPhoto(media=open(chart_path, 'rb'), caption=report),
        reply_markup=query.message.reply_markup
    )
    os.remove(chart_path)

async def pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /pick [short] [long]
    """
    short_ma = 20
    long_ma = 60

    if len(context.args) >= 2:
        try:
            short_ma = int(context.args[0])
            long_ma = int(context.args[1])
        except:
            pass

    await update.message.reply_text(f"正在執行選股分析 (MA{short_ma} > MA{long_ma})，請稍候...")

    symbols = get_all_tsec_symbols()[:50]
    daily_institutional_data = get_recent_institutional_data(5)
    sorted_dates = sorted(daily_institutional_data.keys(), reverse=True)

    matched_results = []
    for symbol in symbols:
        df = get_historical_data(symbol, period="1y")
        if df is None or df.empty:
            continue

        history_list = []
        for d_key in sorted_dates:
            if symbol in daily_institutional_data[d_key]:
                history_list.append(daily_institutional_data[d_key][symbol])

        is_matched, risk = apply_strategy(df, history_list, short_ma=short_ma, long_ma=long_ma)
        if is_matched:
            matched_results.append((symbol, risk))

    if not matched_results:
        await update.message.reply_text("無符合條件的股票。")
        return

    summary = f"🚀 【選股結果 MA{short_ma} > MA{long_ma}】\n"
    for symbol, risk in matched_results:
        summary += f"\n📍 {symbol}\n💰 現價：{risk['buy_price']:.2f}\n🚨 停損：{risk['stop_loss']:.2f}\n"

    await update.message.reply_text(summary)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("台股分析系統 V2\n指令：\n/query [代碼/名稱] - 查詢報告與圖表\n/pick [短MA] [長MA] - 自動選股")

if __name__ == '__main__':
    token = os.getenv('TG_TOKEN')
    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('query', query))
    application.add_handler(CommandHandler('pick', pick))
    application.add_handler(CallbackQueryHandler(handle_callback))

    application.run_polling()
