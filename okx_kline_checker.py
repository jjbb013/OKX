import os
import requests
import json
from datetime import datetime, timedelta
import concurrent.futures

# 配置
BARK_KEY = os.getenv('BARK_KEY')

# OKX API配置
OKX_API_URL = "https://www.okx.com/api/v5/market/candles"
CANDLE_INTERVAL = "15m"  # 15分钟K线

# 需要检查的标的列表
TARGET_SYMBOLS = [
    "ETH-USDT-SWAP",
    "DOGE-USDT-SWAP",
    "BTC-USDT-SWAP",
    "VINE-USDT-SWAP",
    "TRUMP-USDT-SWAP",
    "ADA-USDT-SWAP"
]

def get_okx_kline(symbol):
    """获取OKX指定标的的最新15分钟K线数据"""
    params = {
        "instId": symbol,
        "bar": CANDLE_INTERVAL,
        "limit": "1"
    }
    
    try:
        response = requests.get(OKX_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data["code"] == "0" and len(data["data"]) > 0:
            return (symbol, data["data"][0])
        else:
            print(f"获取{symbol} K线数据失败: {data}")
            return (symbol, None)
    except Exception as e:
        print(f"请求{symbol} K线数据时出错: {e}")
        return (symbol, None)

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
    
    # 下影线至少是实体的2倍
    lower_shadow_ratio = lower_shadow / body_size
    
    # 上影线不超过实体的0.5倍
    upper_shadow_ratio = upper_shadow / body_size
    
    # 收盘价低于开盘价（绿色K线）
    is_bearish = close_price < open_price
    
    return lower_shadow_ratio > 2.0 and upper_shadow_ratio < 0.5

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
    print("开始检测多个OKX标的的K线形态...")
    matching_symbols = []
    
    # 使用线程池并行获取所有标的数据
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # 提交所有任务到线程池
        future_to_symbol = {executor.submit(get_okx_kline, symbol): symbol for symbol in TARGET_SYMBOLS}
        
        # 收集所有结果
        for future in concurrent.futures.as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                symbol, kline = future.result()
            except Exception as e:
                print(f"获取{symbol}数据时发生异常: {e}")
                continue
            
            if kline:
                print(f"获取到{symbol}的K线数据: {kline}")
                
                if is_hanging_man(kline):
                    print(f"检测到{symbol}的下垂线形态!")
                    matching_symbols.append((symbol, kline))
                else:
                    print(f"{symbol}当前K线不是下垂线形态")
            else:
                print(f"未能获取{symbol}的有效K线数据")
    
    # 汇总通知
    if matching_symbols:
        message = "以下标的出现下垂线形态：\n"
        for symbol, kline in matching_symbols:
            message += f"{symbol}: {kline}\n"
        send_bark_notification(message)
    else:
        print("没有检测到符合条件的下垂线形态")

if __name__ == "__main__":
    main()
