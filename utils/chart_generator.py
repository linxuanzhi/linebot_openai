import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import os

# 設定字體，避免中文亂碼 (在 Linux 環境可能需要特定設定)
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def generate_stock_chart(df, stock_id, output_path='static/tmp/chart.png'):
    if df.empty:
        return None

    # 準備 mplfinance 格式
    df_plot = df.copy()
    df_plot.set_index('date', inplace=True)
    df_plot.index = pd.to_datetime(df_plot.index)

    # 技術指標線圖
    apds = []
    if 'ma5' in df_plot.columns:
        apds.append(mpf.make_addplot(df_plot['ma5'], color='blue', width=0.7))
    if 'ma20' in df_plot.columns:
        apds.append(mpf.make_addplot(df_plot['ma20'], color='orange', width=0.7))
    if 'bb_h' in df_plot.columns:
        apds.append(mpf.make_addplot(df_plot[['bb_h', 'bb_l']], color='gray', alpha=0.3))

    # 繪製 K 線圖
    # 使用 binance 風格 (綠漲紅跌)
    mc = mpf.make_marketcolors(up='green', down='red', inherit=True)
    s = mpf.make_mpf_style(marketcolors=mc)

    mpf.plot(df_plot, type='candle', style=s, addplot=apds,
             title=f'Stock {stock_id}', volume=True,
             savefig=output_path, figsize=(12, 8))

    return output_path
