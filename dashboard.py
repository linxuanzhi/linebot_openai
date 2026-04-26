import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from data_acquisition import get_historical_data, get_recent_institutional_data, find_stock
from strategy import calculate_ma, calculate_bollinger_bands, apply_strategy, calculate_rsi, calculate_macd

st.set_page_config(page_title="台股分析系統", layout="wide")

st.title("專屬台股分析系統")

# Sidebar
st.sidebar.header("設定")
stock_code = st.sidebar.text_input("輸入股票代號", value="2330")
period = st.sidebar.selectbox("選擇時間範圍", ["6mo", "1y", "2y", "5y"], index=1)
ma_days = st.sidebar.slider("均線天數 (MA)", 5, 60, 20)

st.sidebar.header("風險控管設定")
sl_ratio = st.sidebar.slider("停損比例 (%)", 5, 20, 10)

if 'tracking_list' not in st.session_state:
    st.session_state.tracking_list = []

if st.sidebar.button("開始分析"):
    with st.spinner("載入資料中..."):
        # 1. Fetch data
        code, name, full_code = find_stock(stock_code)
        if not full_code:
            st.error(f"找不到股票：{stock_code}")
            st.stop()

        df = get_historical_data(full_code, period=period)

        if df is not None:
            # 2. Get institutional data
            with st.status("正在抓取法人籌碼資料..."):
                institutional_data = get_recent_institutional_data(3)
                # Aggregate SITC + Foreign net buy across all fetched dates for this stock
                net_buy_3d = sum(
                    (data.get(stock_code, {}).get('SITC', 0) + data.get(stock_code, {}).get('Foreign', 0))
                    for data in institutional_data.values()
                )

            # 3. Calculate indicators and strategy
            # Extract historical institutional data for this stock
            sorted_dates = sorted(institutional_data.keys(), reverse=True)
            history_list = []
            for d_key in sorted_dates:
                if stock_code in institutional_data[d_key]:
                    history_list.append(institutional_data[d_key][stock_code])

            is_matched, risk = apply_strategy(df, history_list, short_ma=ma_days, sl_percent=sl_ratio)

            df = calculate_ma(df, windows=[ma_days])
            df = calculate_bollinger_bands(df)

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
            col2.metric("法人合計(3日)", f"{net_buy_3d/1000:.0f} 張")

            signal = "符合條件" if is_matched else "不符合"
            col3.metric("策略信號", signal)

            pe_val = stock_info['pe']
            col4.metric("本益比", f"{pe_val if pe_val == 'N/A' else f'{pe_val:.2f}'}")

            yield_val = stock_info['yield']
            col5.metric("殖利率", f"{yield_val if yield_val == 'N/A' else f'{yield_val:.2f}%'}")

            # 6. Risk Management Table
            st.subheader("交易策略建議 (風報比 1:2)")
            buy_price = latest_price
            stop_loss = buy_price * (1 - sl_ratio/100)
            # 風報比 1:2 -> (Target - Buy) = 2 * (Buy - StopLoss)
            take_profit = buy_price + (buy_price - stop_loss) * 2

            risk_df = pd.DataFrame({
                "項目": ["建議買入價", "停損價格 (Red)", "目標獲利價 (Green)"],
                "價格": [f"{buy_price:.2f}", f"{stop_loss:.2f}", f"{take_profit:.2f}"],
                "說明": ["當日收盤價", f"-{sl_ratio}% 停損", f"風報比 1:2"]
            })

            if st.button("加入模擬追蹤清單"):
                st.session_state.tracking_list.append({
                    'code': stock_code,
                    'buy_price': buy_price,
                    'stop_loss': stop_loss,
                    'target': take_profit
                })
                st.success(f"已將 {stock_code} 加入追蹤清單")

            def color_risk(row):
                if "停損" in row['項目']:
                    return ['color: red'] * len(row)
                elif "目標" in row['項目']:
                    return ['color: green'] * len(row)
                return [''] * len(row)

            st.table(risk_df.style.apply(color_risk, axis=1))

            # 7. Candlestick Chart
            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df.index,
                            open=df['Open'],
                            high=df['High'],
                            low=df['Low'],
                            close=df['Close'],
                            name='K線'))

            # Add MAs
            ma_col = f'{ma_days}MA'
            fig.add_trace(go.Scatter(x=df.index, y=df[ma_col], name=ma_col, line=dict(width=1.5)))

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

# Mock Tracking Display
if st.session_state.tracking_list:
    st.divider()
    st.subheader("📋 模擬追蹤清單")
    tracking_data = []
    for item in st.session_state.tracking_list:
        # Fetch current price
        try:
            curr_df = get_historical_data(item['code'], period="1d")
            curr_price = curr_df['Close'].iloc[-1]
            status = "正常"
            if curr_price <= item['stop_loss']:
                status = "🚨 觸及停損"
            elif curr_price >= item['target']:
                status = "✅ 觸及目標"

            tracking_data.append({
                "代號": item['code'],
                "買入價": f"{item['buy_price']:.2f}",
                "停損價": f"{item['stop_loss']:.2f}",
                "目標價": f"{item['target']:.2f}",
                "現價": f"{curr_price:.2f}",
                "狀態": status
            })
        except:
            continue

    st.table(pd.DataFrame(tracking_data))

else:
    st.info("請在左側輸入股票代號並點擊「開始分析」。")
