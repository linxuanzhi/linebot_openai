import openai
import os
from data.fetcher import fetch_stock_data, get_hot_stocks
from analysis.indicators import calculate_indicators

def get_llama_client():
    api_key = os.getenv('LLAMA_API_KEY')
    base_url = os.getenv('LLAMA_BASE_URL', 'https://api.groq.com/openai/v1')
    return openai.OpenAI(api_key=api_key, base_url=base_url)

def analyze_with_ai(stock_id, data_summary, market_context=""):
    client = get_llama_client()

    prompt = f"""
你是一位專業的台股分析師。請分析以下數據並提供點評。
股票代號: {stock_id}
數據摘要: {data_summary}
市場狀況: {market_context}

請針對以下項目進行分析：
1. 技術指標綜合點評
2. 市場分析
3. 建議進價與停損價（請給出具體數字）

請用繁體中文回覆，語氣專業且精簡。
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI 分析錯誤: {e}"

def get_top5_recommendations():
    """
    從熱門股中篩選出技術指標較優的 TOP5
    """
    hot_list = get_hot_stocks()
    candidates = []

    for s_id in hot_list:
        df = fetch_stock_data(s_id, days=60)
        if df.empty or len(df) < 20: continue
        df = calculate_indicators(df)
        last = df.iloc[-1]

        # 簡單評分邏輯：RSI 在 40-60 之間，且收盤價高於 MA20
        score = 0
        if 40 < last['rsi'] < 60: score += 1
        if last['close'] > last['ma20']: score += 1
        if last['k'] > last['d']: score += 1

        candidates.append({'id': s_id, 'score': score, 'price': last['close']})

    # 按分數排序並取前 5
    top5 = sorted(candidates, key=lambda x: x['score'], reverse=True)[:5]
    return top5
