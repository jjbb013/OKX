import os
import requests
import json
from datetime import datetime, timedelta

# 配置
BARK_KEY = os.getenv('BARK_KEY')

# OKX API配置
OKX_API_URL = "https://www.okx.com/api/v5/market/candles"
INSTRUMENT_ID = "ETH-USDT-SWAP"
CANDLE_INTERVAL = "15min"

def get_okx_kline():
    """获取OKX的最新15分钟K线数据"""
    end_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    start_time = (datetime.utcnow() - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    params = {
        "instId": INSTRUMENT_ID,
        "bar": CANDLE_INTERVAL,
        "after": start_time,
        "before": end_time,
        "limit": "1"
    }
    
    try:
        response = requests.get(OKX_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data["code"] == "0" and len(data["data"]) > 0:
            return data["data"][0]
        else:
            print(f"获取K线数据失败: {data}")
            return None
    except Exception as e:
        print(f"请求K线数据时出错: {e}")
        return None

def is_hanging_man(kline):
    """判断是否为下垂线（倒锤子线）形态"""
    if not kline:
        return False
    
    # 解析K线数据
    # [开盘时间, 开, 高, 低, 收, 交易量, 交易额, 最大买入价, 最大卖出价]
    open_time, open_price, high_price, low_price, close_price, _, _, _, _ = kline
    
    # 转换为浮点数
    open_price = float(open_price)
    high_price = float(high_price)
    low_price = float(low_price)
    close_price = float(close_price)
    
    # 计算上下影线
    upper_shadow = high_price - max(open_price, close_price)
    lower_shadow = min(open_price, close_price) - low_price
    
    # 计算实体大小
    body_size = abs(close_price - open_price)
    
    # 判断条件：下影线明显长于实体，且上影线较短
    if body_size == 0:
        return False
    
    # 下影线至少是实体的3倍
    lower_shadow_ratio = lower_shadow / body_size
    # 上影线不超过实体的0.5倍
    upper_shadow_ratio = upper_shadow / body_size
    
    # 收盘价低于开盘价（绿色K线）
    is_bearish = close_price < open_price
    
    return lower_shadow_ratio > 3.0 and upper_shadow_ratio < 0.5 and is_bearish

def send_bark_notification(message):
    """通过Bark发送通知"""
    if not BARK_KEY:
        print("Bark API密钥未配置")
        return
    
    url = f"https://api.day.app/{BARK_KEY}"
    payload = {
        "title": "OKX K线形态检测",
        "body": message
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(f"通知已发送: {response.status_code}")
    except Exception as e:
        print(f"发送通知失败: {e}")

def main():
    print("开始检测OKX K线形态...")
    
    kline = get_okx_kline()
    if not kline:
        print("未能获取有效K线数据")
        return
    
    print(f"获取到K线数据: {kline}")
    
    if is_hanging_man(kline):
        print("检测到下垂线形态!")
        message = f"检测到ETH-USDT 15分钟K线呈现下垂线形态\nK线数据: {kline}"
        send_bark_notification(message)
    else:
        print("当前K线不是下垂线形态")

if __name__ == "__main__":
    main()
