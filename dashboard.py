import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from data_acquisition import get_historical_data, get_recent_institutional_data
from strategy import calculate_ma, calculate_bollinger_bands, apply_strategy, calculate_rsi, calculate_macd

st.set_page_config(page_title="台股分析系統", layout="wide")

st.title("專屬台股分析系統")

# Sidebar
st.sidebar.header("設定")
stock_code = st.sidebar.text_input("輸入股票代號", value="2330")
period = st.sidebar.selectbox("選擇時間範圍", ["6mo", "1y", "2y", "5y"], index=1)

if st.sidebar.button("開始分析"):
    with st.spinner("載入資料中..."):
        # 1. Fetch data
        full_stock_code = f"{stock_code}.TW"
        df = get_historical_data(full_stock_code, period=period)

        if df is not None:
            # 2. Get institutional data
            with st.status("正在抓取法人籌碼資料..."):
                institutional_data = get_recent_institutional_data(3)
                # Aggregate net buy across all fetched dates for this stock
                net_buy_3d = sum(
                    data.get(stock_code, {}).get('Total', 0)
                    for data in institutional_data.values()
                )

            # 3. Calculate indicators and strategy
            df = calculate_ma(df)
            df = calculate_bollinger_bands(df)
            df = calculate_rsi(df)
            df = calculate_macd(df)
            df = apply_strategy(df, net_buy_3d)

            # 4. Fetch additional info
            stock_info = {}
            try:
                ticker = yf.Ticker(full_stock_code)
                info = ticker.info
                stock_info['pe'] = info.get('trailingPE', 'N/A')
                stock_info['yield'] = info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 'N/A'
            except:
                stock_info['pe'] = 'N/A'
                stock_info['yield'] = 'N/A'

            # 5. Display Info
            latest_price = df['Close'].iloc[-1]
            price_change = latest_price - df['Close'].iloc[-2]

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("最新收盤價", f"{latest_price:.2f}", f"{price_change:.2f}")
            col2.metric("三大法人(3日)", f"{net_buy_3d/1000:.0f} 張")

            signal = "符合條件" if df['Strategy_Signal'].iloc[-1] else "不符合"
            col3.metric("策略信號", signal)

            pe_val = stock_info['pe']
            col4.metric("本益比", f"{pe_val if pe_val == 'N/A' else f'{pe_val:.2f}'}")

            yield_val = stock_info['yield']
            col5.metric("殖利率", f"{yield_val if yield_val == 'N/A' else f'{yield_val:.2f}%'}")

            # 5. Candlestick Chart
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df.index,
                            open=df['Open'],
                            high=df['High'],
                            low=df['Low'],
                            close=df['Close'],
                            name='K線'))

            # Add MAs
            for ma in ['5MA', '10MA', '20MA']:
                fig.add_trace(go.Scatter(x=df.index, y=df[ma], name=ma, line=dict(width=1.5)))

            # Add Bollinger Bands
            fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], name='布林上軌', line=dict(dash='dash', color='gray')))
            fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], name='布林下軌', line=dict(dash='dash', color='gray')))

            fig.update_layout(title=f"{stock_code} 歷史K線圖",
                            yaxis_title="價格",
                            xaxis_title="日期",
                            height=600)
            st.plotly_chart(fig, use_container_width=True)

            # 6. Basic Info Table
            st.subheader("近期數據")
            st.write(df.tail(10))
        else:
            st.error(f"無法獲取股票 {stock_code} 的資料，請檢查代號是否正確。")

else:
    st.info("請在左側輸入股票代號並點擊「開始分析」。")
