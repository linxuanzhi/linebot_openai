import mplfinance as mpf
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import os
import requests
from strategy import calculate_ma, calculate_bollinger_bands

def setup_chinese_font():
    """
    Download and register a Chinese font for Render/Linux environments.
    """
    font_path = "SourceHanSansTC-Regular.otf"
    if not os.path.exists(font_path):
        url = "https://github.com/adobe-fonts/source-han-sans/raw/release/OTF/TraditionalChinese/SourceHanSansTC-Regular.otf"
        try:
            r = requests.get(url)
            with open(font_path, "wb") as f:
                f.write(r.content)
        except:
            return None

    fm.fontManager.addfont(font_path)
    plt.rcParams['font.sans-serif'] = ['Source Han Sans TC']
    plt.rcParams['axes.unicode_minus'] = False
    return "Source Han Sans TC"

def generate_stock_chart(df, symbol, name, ma_days=20):
    """
    Generate a candlestick chart with specified MA and Bollinger Bands.
    """
    setup_chinese_font()

    # Process indicators
    df = calculate_ma(df, windows=[ma_days])
    df = calculate_bollinger_bands(df)

    ma_col = f"{ma_days}MA"
    add_plots = [
        mpf.make_addplot(df[ma_col], color='blue', width=1),
        mpf.make_addplot(df['BB_Upper'], color='gray', linestyle='dash', width=0.8),
        mpf.make_addplot(df['BB_Lower'], color='gray', linestyle='dash', width=0.8)
    ]

    file_path = f"{symbol}_chart.png"
    mc = mpf.make_marketcolors(up='r', down='g', inherit=True)
    style = mpf.make_mpf_style(base_mpf_style='charles', marketcolors=mc)

    mpf.plot(
        df.tail(60),
        type='candle',
        style=style,
        addplot=add_plots,
        title=f"{name} ({symbol}) MA{ma_days}",
        savefig=file_path
    )
    return file_path
