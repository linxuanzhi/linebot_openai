import requests
import os

def send_line_notify(message, token=None):
    """
    Send message via LINE Notify.
    """
    if token is None:
        token = os.getenv('LINE_NOTIFY_TOKEN')

    if not token:
        print("LINE_NOTIFY_TOKEN not set.")
        return

    url = "https://notify-api.line.me/api/notify"
    headers = {
        "Authorization": "Bearer " + token
    }
    data = {
        "message": message
    }
    try:
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200:
            print("Message sent successfully!")
        else:
            print(f"Failed to send message: {response.status_code}")
    except Exception as e:
        print(f"Error sending message: {e}")

def format_stock_message(stock_info):
    """
    Format stock info for notification.
    stock_info: dict with code, name, price, reason
    """
    msg = f"\n🚀 【台股強勢轉折選股】\n"
    msg += f"━━━━━━━━━━━━━━\n"
    msg += f"📍 股票：{stock_info['code']} {stock_info['name']}\n"
    msg += f"💰 收盤價：{stock_info['price']}\n"
    msg += f"🔥 觸發原因：{stock_info['reason']}\n"
    msg += f"━━━━━━━━━━━━━━\n"
    msg += f"⏰ 系統時間：{stock_info['time']}"
    return msg

if __name__ == "__main__":
    # Test message
    test_info = {
        'code': '2330',
        'name': '台積電',
        'price': '1000',
        'reason': '創20日新高 + 投信連買',
        'time': '2025/05/20 15:30'
    }
    print(format_stock_message(test_info))
