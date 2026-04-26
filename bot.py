import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from data_acquisition import find_stock, get_historical_data, get_fundamental_data, get_recent_institutional_data, STOCK_LIST_DF
from visualizer import generate_stock_chart
from strategy import apply_strategy

# Global state for quick picks
LATEST_PICKED = []

logging.basicConfig(level=logging.INFO)

def create_main_keyboard(code):
    """
    3-row professional Inline Keyboard.
    """
    row1 = [
        InlineKeyboardButton("📊 基本面", callback_data=f"v3_fund_{code}"),
        InlineKeyboardButton("📈 20MA", callback_data=f"v3_chart_20_{code}"),
        InlineKeyboardButton("📉 60MA", callback_data=f"v3_chart_60_{code}"),
        InlineKeyboardButton("🗓️ 240MA", callback_data=f"v3_chart_240_{code}")
    ]
    row2 = [
        InlineKeyboardButton("🆕 最新分析", callback_data=f"v3_report_{code}"),
        InlineKeyboardButton("🕵️ 三大法人", callback_data=f"v3_chips_{code}"),
        InlineKeyboardButton("➡️ 下一頁", callback_data=f"v3_next_{code}")
    ]
    # Quick picks row
    row3 = [InlineKeyboardButton(c, callback_data=f"v3_query_{c}") for c in LATEST_PICKED[:4]]

    return InlineKeyboardMarkup([row1, row2, row3])

def get_formatted_report(code, name, full_code):
    df = get_historical_data(full_code, period="3mo")
    if df is None or df.empty: return "無法取得數據"

    latest = df.iloc[-1]
    fund = get_fundamental_data(full_code)

    sl_percent = 10
    stop_loss = latest['Close'] * (1 - sl_percent/100)
    target = latest['Close'] + (latest['Close'] - stop_loss) * 2

    report = f"🏢 【{name} ({code}) 分析報告】\n"
    report += f"━━━━━━━━━━━━━━\n"
    report += f"💰 現價：{latest['Close']:.2f}\n"
    report += f"🔴 10% 停損價：{stop_loss:.2f}\n"
    report += f"🟢 目標價：{target:.2f}\n"
    report += f"━━━━━━━━━━━━━━\n"
    report += f"📊 PE: {fund['pe']} | 殖利率: {fund['yield'] if fund['yield'] == 'N/A' else f'{fund['yield']:.2f}%'}\n"
    report += f"📈 營收增長: {fund['revenue_growth'] if fund['revenue_growth'] == 'N/A' else f'{fund['revenue_growth']:.2f}%'}\n"
    report += f"🏦 市值: {fund['market_cap'] if fund['market_cap'] == 'N/A' else f'${fund['market_cap']/1e8:.1f}億'}"
    return report

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💎 台股分析 V3 啟動！\n輸入股票代碼或名稱進行查詢。\n範例：2330 或 台積電")

async def handle_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    code, name, full_code = find_stock(query)

    if not code:
        # Fuzzy suggestions
        suggestions = name # name contains suggestions in this case
        if suggestions:
            btn_row = [InlineKeyboardButton(s, callback_data=f"v3_query_{s}") for s in suggestions]
            await update.message.reply_text(f"❌ 找不到『{query}』，您是指：", reply_markup=InlineKeyboardMarkup([btn_row]))
        else:
            await update.message.reply_text(f"❌ 找不到股票：{query}")
        return

    report = get_formatted_report(code, name, full_code)
    await update.message.reply_text(report, reply_markup=create_main_keyboard(code))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("v3_"): return

    parts = data.split("_")
    action = parts[1]
    code = parts[-1]

    _, name, full_code = find_stock(code)

    if action == "query" or action == "report":
        report = get_formatted_report(code, name, full_code)
        if query.message.photo:
            await query.edit_message_caption(caption=report, reply_markup=create_main_keyboard(code))
        else:
            await query.edit_message_text(text=report, reply_markup=create_main_keyboard(code))

    elif action == "chart":
        ma_days = int(parts[2])
        df = get_historical_data(full_code, period="1y")
        path = generate_stock_chart(df, code, name, ma_days)
        report = get_formatted_report(code, name, full_code)

        await query.edit_message_media(
            media=InputMediaPhoto(media=open(path, 'rb'), caption=report),
            reply_markup=create_main_keyboard(code)
        )
        os.remove(path)

    elif action == "chips":
        daily_inst = get_recent_institutional_data(3)
        net_sitc = sum(d.get(code, {}).get('SITC', 0) for d in daily_inst.values())
        msg = f"🕵️ 【{name} ({code}) 籌碼分析】\n━━━━━━━━━━━━━━\n近三日投信累計買賣超：{net_sitc/1000:.1f} 張\n"
        if query.message.photo:
            await query.edit_message_caption(caption=msg, reply_markup=create_main_keyboard(code))
        else:
            await query.edit_message_text(text=msg, reply_markup=create_main_keyboard(code))

async def run_screening(limit=30, short_ma=20, long_ma=60):
    """
    Scan the market for stocks matching the strategy.
    """
    global STOCK_LIST_DF
    if STOCK_LIST_DF.empty:
        from data_acquisition import sync_stock_list
        sync_stock_list()

    symbols = STOCK_LIST_DF['Code'].tolist()[:limit]
    inst_data = get_recent_institutional_data(5)
    sorted_dates = sorted(inst_data.keys(), reverse=True)

    results = []
    for s in symbols:
        try:
            code, name, full_code = find_stock(s)
            df = get_historical_data(full_code, period="1y")
            if df is None or df.empty: continue

            history = [inst_data[d][s] for d in sorted_dates if s in inst_data[d]]
            matched, risk = apply_strategy(df, history, short_ma=short_ma, long_ma=long_ma)
            if matched:
                results.append((s, df, risk))
        except:
            continue
    return results

async def pick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global LATEST_PICKED
    await update.message.reply_text("🕵️ 正在掃描全市場強勢個股 (約需 1 分鐘)，請稍候...")

    # Simple all-market scan (limited for demo)
    results = await run_screening(limit=50)

    if results:
        LATEST_PICKED = [r[0] for r in results]
        summary = f"🚀 今日強勢股：{', '.join(LATEST_PICKED[:4])}\n已更新至快捷選單。"
        await update.message.reply_text(summary, reply_markup=create_main_keyboard(LATEST_PICKED[0]))
    else:
        await update.message.reply_text("今日無符合條件個股。")

def get_application():
    token = os.getenv('TG_TOKEN')
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('pick', pick_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_query))
    app.add_handler(CallbackQueryHandler(handle_callback))
    return app
