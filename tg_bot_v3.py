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

# Global store for latest picked stocks to use in quick-link buttons
latest_picked_stocks = []

def generate_financial_chart(df, symbol, ma_days=20):
    df = calculate_ma(df, windows=[ma_days])
    df = calculate_bollinger_bands(df)
    file_path = f"{symbol}_{ma_days}_chart.png"
    mc = mpf.make_marketcolors(up='r', down='g', inherit=True)
    s = mpf.make_mpf_style(base_mpf_style='charles', marketcolors=mc)
    ma_col = f"{ma_days}MA"
    add_plots = [
        mpf.make_addplot(df[ma_col], color='blue', width=1),
        mpf.make_addplot(df['BB_Upper'], color='gray', linestyle='dash', width=0.8),
        mpf.make_addplot(df['BB_Lower'], color='gray', linestyle='dash', width=0.8)
    ]
    mpf.plot(df.tail(60), type='candle', style=s, addplot=add_plots,
             title=f"{symbol} MA{ma_days}", savefig=file_path)
    return file_path

def create_professional_keyboard(code):
    # Row 1: Core Indicators
    row1 = [
        InlineKeyboardButton("📊 基本面", callback_data=f"prof_fund_{code}"),
        InlineKeyboardButton("📈 20MA", callback_data=f"prof_chart_20_{code}"),
        InlineKeyboardButton("📉 60MA", callback_data=f"prof_chart_60_{code}"),
        InlineKeyboardButton("🗓️ 240MA", callback_data=f"prof_chart_240_{code}")
    ]
    # Row 2: Features
    row2 = [
        InlineKeyboardButton("🆕 最新分析", callback_data=f"prof_latest_{code}"),
        InlineKeyboardButton("🕵️ 三大法人", callback_data=f"prof_chips_{code}"),
        InlineKeyboardButton("➡️ 下一頁", callback_data=f"prof_next_{code}")
    ]
    # Row 3: Quick Links (Top 4 Picked)
    row3 = [InlineKeyboardButton(s, callback_data=f"prof_switch_{s}") for s in latest_picked_stocks[:4]]

    return InlineKeyboardMarkup([row1, row2, row3])

async def query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = context.args[0] if context.args else ""
    if not query_text:
        await update.message.reply_text("請輸入股票代碼或名稱。例如：/query 2330")
        return

    code = lookup_stock_code(query_text)
    if not code:
        await update.message.reply_text(f"❌ 找不到股票：{query_text}")
        return

    report = get_report_text(code)
    await update.message.reply_text(report, reply_markup=create_professional_keyboard(code))

def get_report_text(code):
    df = get_historical_data(code, period="3mo")
    latest = df.iloc[-1]
    fund = get_fundamental_data(code)
    sl_percent = 10
    stop_loss = latest['Close'] * (1 - sl_percent/100)
    target = latest['Close'] + (latest['Close'] - stop_loss) * 2

    report = f"🏛️ 【{fund.get('name', code)} ({code}) 分析報告】\n"
    report += f"━━━━━━━━━━━━━━\n"
    report += f"💰 現價：{latest['Close']:.2f}\n"
    report += f"🔴 停損價：{stop_loss:.2f}\n"
    report += f"🟢 目標價：{target:.2f}\n"
    report += f"━━━━━━━━━━━━━━\n"
    report += f"📊 PE: {fund['pe']} | 殖利率: {fund['yield'] if fund['yield'] == 'N/A' else f'{fund['yield']:.2f}%'}\n"
    report += f"📈 營收年增: {fund['revenue_growth'] if fund['revenue_growth'] == 'N/A' else f'{fund['revenue_growth']:.2f}%'}\n"
    report += f"🏢 市值: {fund['market_cap'] if fund['market_cap'] == 'N/A' else f'${fund['market_cap']/1e8:.1f}億'}"
    return report

async def handle_prof_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if not data.startswith("prof_"): return

    parts = data.split('_')
    action = parts[1]
    code = parts[-1]

    if action == "chart":
        ma_days = int(parts[2])
        df = get_historical_data(code, period="1y")
        path = generate_financial_chart(df, code, ma_days)
        report = get_report_text(code)
        await query.edit_message_media(media=InputMediaPhoto(media=open(path, 'rb'), caption=report),
                                      reply_markup=create_professional_keyboard(code))
        os.remove(path)

    elif action == "fund" or action == "latest":
        report = get_report_text(code)
        # If it was a photo, we might need to send text or update caption
        if query.message.photo:
            await query.edit_message_caption(caption=report, reply_markup=create_professional_keyboard(code))
        else:
            await query.edit_message_text(text=report, reply_markup=create_professional_keyboard(code))

    elif action == "chips":
        # Simplified chips report
        daily_inst = get_recent_institutional_data(3)
        net_sitc = sum(d.get(code, {}).get('SITC', 0) for d in daily_inst.values())
        msg = f"🕵️ 【{code} 法人籌碼】\n━━━━━━━━━━━━━━\n近三日投信累計買賣超：{net_sitc/1000:.1f} 張\n"
        if query.message.photo:
            await query.edit_message_caption(caption=msg, reply_markup=create_professional_keyboard(code))
        else:
            await query.edit_message_text(text=msg, reply_markup=create_professional_keyboard(code))

    elif action == "switch":
        report = get_report_text(code)
        if query.message.photo:
            await query.edit_message_caption(caption=report, reply_markup=create_professional_keyboard(code))
        else:
            await query.edit_message_text(text=report, reply_markup=create_professional_keyboard(code))

async def run_screening(limit=30, short_ma=20, long_ma=60):
    """
    Shared screening logic for /pick and scheduled push.
    """
    symbols = get_all_tsec_symbols()[:limit]
    daily_institutional_data = get_recent_institutional_data(5)
    sorted_dates = sorted(daily_institutional_data.keys(), reverse=True)

    results = []
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
            results.append((symbol, df, risk))
    return results

async def pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global latest_picked_stocks
    await update.message.reply_text("🔎 正在掃描強勢個股...")

    results = await run_screening(limit=30)

    if not results:
        await update.message.reply_text("今日無符合條件個股。")
        return

    latest_picked_stocks = [r[0] for r in results]

    summary = "🚀 【強勢轉折選股】\n━━━━━━━━━━━━━━\n"
    for symbol, df, risk in results[:5]:
        summary += f"📍 {symbol} | 💰 {risk['buy_price']:.2f}\n"

    await update.message.reply_text(summary, reply_markup=create_professional_keyboard(results[0][0]))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💎 台股專業分析系統\n\n指令：\n/query [代碼/名稱] - 深度報告\n/pick - 強勢選股")

if __name__ == '__main__':
    token = os.getenv('TG_TOKEN')
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('query', query))
    application.add_handler(CommandHandler('pick', pick))
    application.add_handler(CallbackQueryHandler(handle_prof_callback))
    application.run_polling()
