import os
import logging
import datetime
import difflib
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import mplfinance as mpf
from matplotlib import font_manager
from FinMind.data import DataLoader
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class DataFetcher:
    def __init__(self):
        self.dl = DataLoader()
        self.stock_list = pd.DataFrame()
        self.last_sync = None

    def sync_stock_list(self):
        """Sync Taiwan stock list (listed and OTC) from FinMind."""
        try:
            logger.info("Syncing stock list from FinMind...")
            df = self.dl.taiwan_stock_info()
            if not df.empty:
                self.stock_list = df[['stock_id', 'stock_name', 'type']]
                self.last_sync = datetime.datetime.now()
                logger.info(f"Synced {len(self.stock_list)} stocks.")
                return True
            return False
        except Exception as e:
            logger.error(f"Error syncing stock list: {e}")
            return False

    def get_stock_info(self, name_or_id):
        if self.stock_list.empty:
            self.sync_stock_list()

        res = self.stock_list[self.stock_list['stock_id'] == name_or_id]
        if not res.empty:
            row = res.iloc[0]
            ticker = f"{row['stock_id']}.TW" if row['type'] == 'twse' else f"{row['stock_id']}.TWO"
            return row['stock_id'], row['stock_name'], ticker, []

        res = self.stock_list[self.stock_list['stock_name'] == name_or_id]
        if not res.empty:
            row = res.iloc[0]
            ticker = f"{row['stock_id']}.TW" if row['type'] == 'twse' else f"{row['stock_id']}.TWO"
            return row['stock_id'], row['stock_name'], ticker, []

        names = self.stock_list['stock_name'].tolist()
        matches = difflib.get_close_matches(name_or_id, names, n=3, cutoff=0.4)
        return None, None, None, matches

    def fetch_price_data(self, ticker, period="1y"):
        try:
            df = yf.download(ticker, period=period, progress=False)
            if df.empty:
                return pd.DataFrame()
            return df
        except Exception as e:
            logger.error(f"Error fetching price data for {ticker}: {e}")
            return pd.DataFrame()

    def fetch_institutional_data(self, stock_id, days=5):
        try:
            end_date = datetime.date.today().strftime('%Y-%m-%d')
            start_date = (datetime.date.today() - datetime.timedelta(days=days*3)).strftime('%Y-%m-%d')
            df = self.dl.taiwan_stock_institutional_investors(
                stock_id=stock_id,
                start_date=start_date,
                end_date=end_date
            )
            if df.empty:
                return "無籌碼資料"
            df = df.tail(days)
            summary = ""
            for _, row in df.iterrows():
                date = row['date']
                total = int(row['Foreign_Investor_Net_Buy'] + row['Investment_Trust_Net_Buy'] + row['Dealer_Net_Buy'])
                summary += f"📅 {date}: {'🔴' if total > 0 else '🟢'} {total/1000:,.1f}張\n"
            return summary
        except Exception as e:
            logger.error(f"Error fetching institutional data for {stock_id}: {e}")
            return "獲取籌碼資料失敗"

class Plotter:
    def __init__(self, font_path="NotoSansTC.ttf"):
        self.font_path = font_path
        if os.path.exists(self.font_path):
            font_manager.fontManager.addfont(self.font_path)
            plt.rcParams['font.sans-serif'] = ['Noto Sans TC']
            plt.rcParams['axes.unicode_minus'] = False
        else:
            logger.warning(f"Font file {self.font_path} not found.")

    def plot_k_line(self, df, stock_name, ticker, highlight_ma=None):
        try:
            if df.empty:
                return None
            data = df.copy()
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                if col in data.columns:
                    if isinstance(data[col], pd.DataFrame):
                        data[col] = data[col].iloc[:, 0]
                    data[col] = pd.to_numeric(data[col], errors='coerce')

            data.index = pd.to_datetime(data.index)
            data = data.sort_index()
            data['MA20'] = data['Close'].rolling(window=20).mean()
            data['MA60'] = data['Close'].rolling(window=60).mean()
            data['MA240'] = data['Close'].rolling(window=240).mean()
            std = data['Close'].rolling(window=20).std()
            data['BB_upper'] = data['MA20'] + (std * 2)
            data['BB_lower'] = data['MA20'] - (std * 2)

            plot_df = data.tail(100)
            apds = []

            # MAs
            ma_configs = [('MA20', 'blue', 20), ('MA60', 'orange', 60), ('MA240', 'red', 240)]
            for col, color, days in ma_configs:
                if not plot_df[col].isna().all():
                    width = 2.0 if highlight_ma == days else 0.7
                    apds.append(mpf.make_addplot(plot_df[col], color=color, width=width))

            # Bollinger Bands
            if not plot_df['BB_upper'].isna().all():
                apds.append(mpf.make_addplot(plot_df['BB_upper'], color='gray', width=0.5, linestyle='--'))
            if not plot_df['BB_lower'].isna().all():
                apds.append(mpf.make_addplot(plot_df['BB_lower'], color='gray', width=0.5, linestyle='--'))

            filename = f"chart_{ticker}.png"
            mc = mpf.make_marketcolors(up='r', down='g', inherit=True)
            s = mpf.make_mpf_style(marketcolors=mc, gridstyle='--')

            mpf.plot(
                plot_df,
                type='candle',
                addplot=apds,
                title=f"\n{stock_name} ({ticker})",
                style=s,
                volume=True,
                savefig=filename,
                figratio=(16, 9),
                tight_layout=True
            )
            return filename
        except Exception as e:
            logger.error(f"Error plotting K-line: {e}")
            return None

class BotHandler:
    def __init__(self, token):
        self.fetcher = DataFetcher()
        self.plotter = Plotter()
        self.token = token
        self.pick_stocks = ["2330", "2317", "2454"]

    def get_keyboard(self, stock_id):
        keyboard = [
            [
                InlineKeyboardButton("📊 基本面", callback_query_data=f"fundamental_{stock_id}"),
                InlineKeyboardButton("📈 20MA", callback_query_data=f"ma_20_{stock_id}"),
                InlineKeyboardButton("📉 60MA", callback_query_data=f"ma_60_{stock_id}"),
                InlineKeyboardButton("🗓️ 240MA", callback_query_data=f"ma_240_{stock_id}")
            ],
            [
                InlineKeyboardButton("🆕 最新分析", callback_query_data=f"analysis_{stock_id}"),
                InlineKeyboardButton("🕵️ 三大法人", callback_query_data=f"chip_{stock_id}"),
                InlineKeyboardButton("➡️ 下一頁", callback_query_data=f"next_{stock_id}")
            ],
            [
                InlineKeyboardButton(f"[{s}]", callback_query_data=f"search_{s}") for s in self.pick_stocks[:3]
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    def get_risk_text(self, current_price):
        try:
            price = float(current_price)
            sl = price * 0.9
            tp = price + (price - sl) * 2
            return f"\n\n💡 風險控管建議：\n✅ 建議買入價: {price:.2f}\n🚨 10% 停損價: {sl:.2f}\n🎯 目標獲利價 (1:2): {tp:.2f}"
        except: return ""

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("歡迎使用台股分析機器人 V3！\n請輸入股票名稱或代碼（例如：鴻海 或 2317）")

    async def pick(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(f"當前熱門選股：{', '.join(self.pick_stocks)}")

    async def process_stock_query(self, query_text, update: Update, context: ContextTypes.DEFAULT_TYPE, is_callback=False):
        stock_id, stock_name, ticker, matches = self.fetcher.get_stock_info(query_text)
        target = update.callback_query.message if is_callback else update.message

        if stock_id:
            df = self.fetcher.fetch_price_data(ticker)
            if df.empty:
                await target.reply_text(f"找不到 {stock_name} 的價格資料。")
                return

            chart_path = self.plotter.plot_k_line(df, stock_name, ticker)
            price = df['Close'].iloc[-1]
            if isinstance(price, pd.Series): price = price.iloc[0]

            caption = f"📈 {stock_name} ({ticker}) 分析報告\n當前價格: {price:.2f}{self.get_risk_text(price)}"
            with open(chart_path, 'rb') as photo:
                if is_callback:
                    await update.callback_query.edit_message_media(media=InputMediaPhoto(media=photo, caption=caption), reply_markup=self.get_keyboard(stock_id))
                else:
                    await update.message.reply_photo(photo=photo, caption=caption, reply_markup=self.get_keyboard(stock_id))
            if os.path.exists(chart_path): os.remove(chart_path)
        elif matches:
            await target.reply_text("找不到該股票，您是否是指：\n" + "\n".join([f"• {m}" for m in matches]))
        else:
            await target.reply_text("找不到相關股票，請重新輸入。")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.process_stock_query(update.message.text.strip(), update, context)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data.split('_')
        action, stock_id = data[0], data[-1]

        if action == "search":
            await self.process_stock_query(stock_id, update, context, is_callback=True)
            return

        _, stock_name, ticker, _ = self.fetcher.get_stock_info(stock_id)
        df = self.fetcher.fetch_price_data(ticker)
        price = df['Close'].iloc[-1]
        if isinstance(price, pd.Series): price = price.iloc[0]
        risk = self.get_risk_text(price)

        highlight_ma = int(data[1]) if action == "ma" else None
        chart_path = self.plotter.plot_k_line(df, stock_name, ticker, highlight_ma=highlight_ma)

        if action == "chip":
            caption = f"🕵️ {stock_name} ({ticker}) 三大法人籌碼 (近5日)\n{self.fetcher.fetch_institutional_data(stock_id)}{risk}"
        elif action == "ma":
            caption = f"📈 {stock_name} ({ticker}) - {highlight_ma}MA 分析\n當前價格: {price:.2f}{risk}"
        else:
            caption = f"📈 {stock_name} ({ticker}) 分析報告\n當前價格: {price:.2f}{risk}"

        if chart_path:
            with open(chart_path, 'rb') as photo:
                await query.edit_message_media(media=InputMediaPhoto(media=photo, caption=caption), reply_markup=self.get_keyboard(stock_id))
            if os.path.exists(chart_path): os.remove(chart_path)

    def run(self):
        if not self.token:
            logger.error("TELEGRAM_BOT_TOKEN not found.")
            return
        application = Application.builder().token(self.token).build()
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("pick", self.pick))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        application.add_handler(CallbackQueryHandler(self.handle_callback))
        self.fetcher.sync_stock_list()
        application.run_polling()

if __name__ == "__main__":
    handler = BotHandler(os.getenv("TELEGRAM_BOT_TOKEN"))
    handler.run()
