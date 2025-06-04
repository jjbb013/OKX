# trading_strategy.py
import os
import pandas as pd
import requests
import json
from datetime import datetime, timezone, timedelta
import okx.MarketData as MarketData
import okx.Trade as Trade

def get_beijing_time():
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")

def send_bark_notification(title, message):
    """发送Bark通知"""
    bark_key = os.getenv("BARK_KEY")
    if not bark_key:
        print(f"[{get_beijing_time()}] [ERROR] 缺少BARK_KEY环境变量")
        return
    
    group = os.getenv("BARK_GROUP", "OKX自动交易通知")
    payload = {
        'title': title,
        'body': message,
        'group': group,
        'sound': 'minuet'
    }
    headers = {'Content-Type': 'application/json'}
    
    try:
        response = requests.post(bark_key, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"[{get_beijing_time()}] [BARK] 通知发送成功")
        else:
            print(f"[{get_beijing_time()}] [BARK] 发送失败: {response.text}")
    except Exception as e:
        print(f"[{get_beijing_time()}] [BARK] 异常: {str(e)}")

def run_strategy(df):
    # 计算振幅
    df['changePerc'] = abs(df['close'] - df['open']) / df['open'] * 100
    df['inRange1'] = (df['changePerc'] >= 0.7) & (df['changePerc'] <= 1.8)
    df['inRange2'] = ((df['high'] - df['low']) / df['low'] * 100) > 1.8
    df['isGreen'] = df['close'] > df['open']
    df['isRed'] = df['close'] < df['open']

    latest = df.iloc[-1]
    signal = entry_price = None

    if latest['inRange1'] or latest['inRange2']:
        if latest['inRange1']:
            entry_price = (latest['high'] + latest['low']) / 2
            signal = 'LONG' if latest['isGreen'] else 'SHORT'
        elif latest['inRange2']:
            entry_price = latest['high'] if latest['isGreen'] else latest['low']
            signal = 'SHORT' if latest['isGreen'] else 'LONG'

    return signal, entry_price

if __name__ == "__main__":
    # 从环境变量获取账户信息
    API_KEY = os.getenv("OKX_API_KEY")
    SECRET_KEY = os.getenv("OKX_SECRET_KEY")
    PASSPHRASE = os.getenv("OKX_PASSPHRASE")
    FLAG = os.getenv("OKX_FLAG", "0")  # 默认实盘

    if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
        print(f"[{get_beijing_time()}] [ERROR] 缺少环境变量: OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE")
        exit(1)

    # 初始化API
    market_api = MarketData.MarketAPI(API_KEY, SECRET_KEY, PASSPHRASE, False, FLAG)
    trade_api = Trade.TradeAPI(API_KEY, SECRET_KEY, PASSPHRASE, False, FLAG)
    instId = "TRUMP-USDT-SWAP"

    # 获取K线数据
    result = market_api.get_candlesticks(instId=instId, bar="1m", limit="1")
    if not result or 'data' not in result:
        print(f"[{get_beijing_time()}] [ERROR] K线数据获取失败")
        exit(0)

    # 解析数据
    df = pd.DataFrame(result['data'], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'volCcyQuote', 'volCcyAsset', 'confirm'])
    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
    for col in ['open', 'high', 'low', 'close']:
        df[col] = df[col].astype(float)

    # 执行策略
    signal, entry_price = run_strategy(df)
    
    if signal:
        # 下单逻辑
        margin = 5
        size = round((margin * 10) / entry_price, 4)
        order_params = {
            "instId": instId,
            "tdMode": "cross",
            "side": "buy" if signal == "LONG" else "sell",
            "ordType": "limit",
            "px": str(entry_price),
            "sz": str(size),
            "posSide": "long" if signal == "LONG" else "short",
            "tpTriggerPx": str(round(entry_price * 1.02, 6)),
            "tpOrdPx": "-1",
            "slTriggerPx": str(round(entry_price * 0.986, 6)),
            "slOrdPx": "-1"
        }
        
        # 发送订单
        order_result = trade_api.place_order(**order_params)
        
        # 发送Bark通知
        title = f"TRUMP交易信号: {signal}"
        message = (
            f"信号类型: {signal}\n"
            f"入场价格: {entry_price}\n"
            f"委托数量: {size}\n"
            f"止盈价: {round(entry_price*1.02,4)}\n"
            f"止损价: {round(entry_price*0.986,4)}"
        )
        send_bark_notification(title, message)
        
        # 日志输出（青龙面板自动捕获）
        print(f"[{get_beijing_time()}] [SIGNAL] {signal}@{entry_price}")
        print(f"[{get_beijing_time()}] [ORDER] {json.dumps(order_params)}")
        print(f"[{get_beijing_time()}] [RESULT] {json.dumps(order_result)}")
    else:
        print(f"[{get_beijing_time()}] [INFO] 未检测到交易信号")
