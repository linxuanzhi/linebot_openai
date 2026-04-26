# Taiwan Stock Analysis System - System Architecture

## Overview
The Taiwan Stock Analysis System is designed to provide users with tools for data acquisition, technical analysis, and visualization of Taiwan stocks.

## Modules

### 1. Data Engine (Data Acquisition)
- **Historical Price Data**: Fetched using `yfinance`.
- **Institutional Investor Data**: Crawled from the Taiwan Stock Exchange (TWSE) website.
- **Data Processing**: Handles "Minguo to Gregorian" date conversion and data cleaning.
- **Storage**: Currently using memory-based processing with Pandas DataFrames.

### 2. Analytics Engine (Strategy & Indicators)
- **Technical Indicators**: Calculates Moving Averages (5MA, 10MA, 20MA), RSI, MACD, and Bollinger Bands.
- **Selection Strategy**: Implements "MA Bullish Alignment + Institutional Net Buy" logic.
- **Performance Optimization**: Vectorized operations using Pandas for efficient analysis of multiple stocks.

### 3. UI/UX Dashboard
- **Framework**: Built with `Streamlit`.
- **Visualization**: Interactive Candlestick charts with technical indicator overlays using `Plotly`.
- **User Input**: Sidebar for selecting stock codes and analysis periods.

## Technical Stack
- **Language**: Python 3
- **Data Manipulation**: `pandas`
- **Visualization**: `plotly`, `streamlit`
- **Data Sources**: `yfinance`, TWSE (crawler)
- **HTTP Requests**: `requests`, `beautifulsoup4`
