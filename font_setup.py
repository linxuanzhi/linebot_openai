import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import os
import requests

def setup_chinese_font():
    """
    Download and setup Chinese font for matplotlib/mplfinance.
    """
    font_url = "https://github.com/adobe-fonts/source-han-sans/raw/release/OTF/TraditionalChinese/SourceHanSansTC-Regular.otf"
    font_path = "SourceHanSansTC-Regular.otf"

    if not os.path.exists(font_path):
        print("Downloading Chinese font...")
        try:
            r = requests.get(font_url)
            with open(font_path, "wb") as f:
                f.write(r.content)
            print("Font downloaded.")
        except Exception as e:
            print(f"Failed to download font: {e}")
            return

    # Register font
    fm.fontManager.addfont(font_path)
    plt.rcParams['font.sans-serif'] = ['Source Han Sans TC']
    plt.rcParams['axes.unicode_minus'] = False
    print(f"Font setup complete: Source Han Sans TC")

if __name__ == "__main__":
    setup_chinese_font()
