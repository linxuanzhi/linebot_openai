import os
import uuid
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

from database.db_manager import get_user_settings, update_user_settings, get_portfolio, update_portfolio
from data.fetcher import fetch_stock_data, fetch_institutional_investors
from analysis.indicators import calculate_indicators, calculate_risk_metrics
from analysis.ai_analyzer import analyze_with_ai, get_top5_recommendations
from utils.chart_generator import generate_stock_chart

load_dotenv()

# 確保暫存目錄存在
os.makedirs('static/tmp', exist_ok=True)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update, context, page=1)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, page=1):
    user_id = update.effective_user.id
    settings = get_user_settings(user_id)

    text = f"【台股分析系統】\n當前追蹤：{settings.stock_id}\n數據長度：{settings.data_length}天\n頁碼：{page}"

    keyboard = []
    if page == 1:
        keyboard = [
            [InlineKeyboardButton("顯示所有數據", callback_data='show_data'), InlineKeyboardButton("顯示 AI 點", callback_data='show_ai')],
            [InlineKeyboardButton("線圖", callback_data='show_chart'), InlineKeyboardButton("推薦股票", callback_data='recommend')],
            [InlineKeyboardButton("模擬倉位管理", callback_data='portfolio_mgmt')],
            [InlineKeyboardButton("下一頁", callback_data='page_2')]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("設定搜尋個股", callback_data='set_stock')],
            [InlineKeyboardButton("設定數據長度", callback_data='set_length')],
            [InlineKeyboardButton("上一頁", callback_data='page_1')]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        except:
            await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    settings = get_user_settings(user_id)

    if query.data == 'page_1':
        await show_main_menu(update, context, page=1)
    elif query.data == 'page_2':
        await show_main_menu(update, context, page=2)
    elif query.data == 'show_data':
        df = fetch_stock_data(settings.stock_id, settings.data_length)
        df = calculate_indicators(df)
        if df.empty:
            await query.message.reply_text("獲取數據失敗")
            return

        last = df.iloc[-1]
        msg = f"【{settings.stock_id} 數據摘要】\n收盤: {last['close']:.2f}\nMACD: {last['macd']:.2f}\nRSI: {last['rsi']:.2f}\nK: {last['k']:.2f} D: {last['d']:.2f}\nBIAS: {last['bias']:.2f}%"

        # 加入三大法人
        inst_df = fetch_institutional_investors(settings.stock_id)
        if not inst_df.empty:
            recent_inst = inst_df.tail(3)
            msg += "\n\n【最近三大法人買賣超】"
            for _, row in recent_inst.iterrows():
                msg += f"\n{row['date']}: {row['buy'] - row['sell']:.0f}"

        await query.message.reply_text(msg)
    elif query.data == 'show_chart':
        df = fetch_stock_data(settings.stock_id, settings.data_length)
        df = calculate_indicators(df)
        # 使用唯一檔名避免競爭
        unique_filename = f"static/tmp/chart_{uuid.uuid4()}.png"
        path = generate_stock_chart(df, settings.stock_id, output_path=unique_filename)
        if path:
            with open(path, 'rb') as photo:
                await query.message.reply_photo(photo)
            os.remove(path) # 發送後刪除
        else:
            await query.message.reply_text("生成線圖失敗")
    elif query.data == 'show_ai':
        df = fetch_stock_data(settings.stock_id, settings.data_length)
        df = calculate_indicators(df)
        summary = df.iloc[-5:].to_string()
        analysis = analyze_with_ai(settings.stock_id, summary)
        await query.message.reply_text(analysis)
    elif query.data == 'recommend':
        top5 = get_top5_recommendations()
        msg = "【推薦股票 TOP5】\n"
        for item in top5:
            msg += f"代號: {item['id']} | 分數: {item['score']} | 收盤: {item['price']:.2f}\n"
        await query.message.reply_text(msg)
    elif query.data == 'portfolio_mgmt':
        await show_portfolio_menu(update, context)
    elif query.data == 'set_stock':
        await query.message.reply_text("請輸入股票代號（例如：2330）：")
        context.user_data['action'] = 'set_stock'
    elif query.data == 'set_length':
        await query.message.reply_text("請輸入數據長度（天數）：")
        context.user_data['action'] = 'set_length'
    elif query.data.startswith('set_p_'):
        slot = int(query.data.split('_')[-1])
        await query.message.reply_text(f"請輸入倉位 {slot} 資訊 (格式: 股票代號 股數 進價):")
        context.user_data['action'] = f'set_portfolio_{slot}'
    elif query.data == 'calc_p':
        await calculate_portfolio_performance(update, context)

async def show_portfolio_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    items = get_portfolio(user_id)

    text = "【模擬倉位管理】\n"
    for i in range(1, 6):
        item = next((x for x in items if x.slot == i), None)
        if item:
            text += f"倉位 {i}: {item.stock_id} | {item.shares}股 | 進價: {item.entry_price:.2f}\n"
        else:
            text += f"倉位 {i}: 未設定\n"

    keyboard = [
        [InlineKeyboardButton(f"設定 {i}", callback_data=f'set_p_{i}') for i in range(1, 4)],
        [InlineKeyboardButton(f"設定 {i}", callback_data=f'set_p_{i}') for i in range(4, 6)],
        [InlineKeyboardButton("計算損益", callback_data='calc_p')],
        [InlineKeyboardButton("回主選單", callback_data='page_1')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

async def calculate_portfolio_performance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    items = get_portfolio(user_id)
    if not items:
        await update.callback_query.message.reply_text("目前沒有倉位資料")
        return

    report = "【損益報告】\n"
    total_cost = 0
    total_value = 0

    for item in items:
        df = fetch_stock_data(item.stock_id, 5)
        if df.empty: continue
        current_price = float(df.iloc[-1]['close'])
        cost = item.entry_price * item.shares
        value = current_price * item.shares
        profit = value - cost
        profit_pct = (profit / cost) * 100 if cost > 0 else 0

        df_long = fetch_stock_data(item.stock_id, 60)
        risk = calculate_risk_metrics(df_long)

        report += f"{item.stock_id}: {profit_pct:.2f}% | 風險: {risk['volatility']:.2f}\n"
        total_cost += cost
        total_value += value

    total_profit_pct = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0
    report += f"\n總損益比: {total_profit_pct:.2f}%"
    await update.callback_query.message.reply_text(report)

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    action = context.user_data.get('action', '')
    user_id = update.effective_user.id
    text = update.message.text

    if action == 'set_stock':
        update_user_settings(user_id, stock_id=text)
        await update.message.reply_text(f"已更新追蹤個股為：{text}")
        context.user_data['action'] = None
    elif action == 'set_length':
        try:
            length = int(text)
            update_user_settings(user_id, data_length=length)
            await update.message.reply_text(f"已更新數據長度為：{length}天")
        except:
            await update.message.reply_text("請輸入有效數字")
        context.user_data['action'] = None
    elif action.startswith('set_portfolio_'):
        slot = int(action.split('_')[-1])
        try:
            parts = text.split()
            if len(parts) == 3:
                s_id, shares, price = parts[0], int(parts[1]), float(parts[2])

                # 實作平均進價邏輯：如果該倉位已有相同股票，則平均。
                # 或是依據 slot 來區分。使用者要求「同支股票不同價位買入的情況請依使用者輸入去平均」
                # 這裡採取的策略是：如果使用者在同一個 slot 輸入，就覆寫。
                # 但若我們要實作真正的平均進價，我們應該檢查 user 是否在其他 slot 也有同支股票。

                # 為了符合「依輸入去平均」，我們改進 db_manager 或在此處計算
                current_p = get_portfolio(user_id, slot=slot)
                if current_p and current_p.stock_id == s_id:
                    new_shares = current_p.shares + shares
                    new_price = (current_p.entry_price * current_p.shares + price * shares) / new_shares
                    update_portfolio(user_id, slot, s_id, new_price, new_shares)
                    await update.message.reply_text(f"倉位 {slot} ({s_id}) 已更新並計算平均進價: {new_price:.2f}")
                else:
                    update_portfolio(user_id, slot, s_id, price, shares)
                    await update.message.reply_text(f"倉位 {slot} 已設定為 {s_id}")
            else:
                await update.message.reply_text("格式錯誤，請重新輸入 (股票 股數 進價)")
        except Exception as e:
            await update.message.reply_text(f"輸入錯誤: {e}")
        context.user_data['action'] = None

if __name__ == '__main__':
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if token:
        app = ApplicationBuilder().token(token).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_input))
        print("Bot 啟動中...")
        app.run_polling()
    else:
        print("請設定 TELEGRAM_BOT_TOKEN")
