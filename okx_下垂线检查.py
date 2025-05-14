"""
任务名称
name: 下垂线检查
定时规则
cron: 55 14,29,44,59 * * * *
"""

import os
import requests
import json
from datetime import datetime
import concurrent.futures
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hanging_man_monitor.log'),
        logging.StreamHandler()
    ]
)

# 环境变量配置
BARK_KEY = 'oZaeqGLJzRLSxW7dJqeACn'
if not BARK_KEY:
    logging.warning("Bark API密钥未配置，通知功能将被禁用")
    BARK_KEY = None

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
        "limit": 1
    }

    try:
        response = requests.get(OKX_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data["code"] == "0" and len(data["data"]) > 0:
            return (symbol, data["data"][0])
        else:
            logging.warning(f"获取{symbol} K线数据失败: {data}")
            return (symbol, None)
    except Exception as e:
        logging.error(f"请求{symbol} K线数据时出错: {e}")
        return (symbol, None)


def is_hanging_man(kline):
    """判断是否为下垂线（Hammer）形态"""
    if not kline:
        return False

    # 解析K线数据
    # 根据实际返回的数据结构，调整字段索引
    # 假设返回的数据格式为 [时间戳, 开盘价, 最高价, 最低价, 收盘价, 成交量, ...]
    try:
        # 提取前6个字段
        timestamp, open_price, high_price, low_price, close_price, volume = kline[:6]
    except ValueError as e:
        logging.error(f"解析K线数据失败: {e}, 数据: {kline}")
        # 打印完整数据
        logging.debug(f"完整K线数据: {kline}")
        return False

    # 转换为浮点数
    try:
        open_price = float(open_price)
        high_price = float(high_price)
        low_price = float(low_price)
        close_price = float(close_price)
        volume = float(volume) if volume else 0.0
    except ValueError as e:
        logging.error(f"转换K线数据为浮点数失败: {e}, 数据: {kline}")
        return False

    # 计算上下影线
    upper_shadow = high_price - max(open_price, close_price)
    lower_shadow = min(open_price, close_price) - low_price

    # 计算实体大小
    body_size = abs(close_price - open_price)

    # 判断条件：
    # 1. 下影线至少是实体的2倍
    # 2. 上影线不超过实体的1倍
    # 3. 收盘价高于或低于开盘价均可接受
    if body_size == 0:
        return False

    lower_shadow_ratio = lower_shadow / body_size
    upper_shadow_ratio = upper_shadow / body_size

    return lower_shadow_ratio >= 2.0 and upper_shadow_ratio <= 1.0


def send_bark_notification(message):
    """通过Bark发送通知"""
    if not BARK_KEY:
        logging.warning("Bark API密钥未配置")
        return

    url = f"https://api.day.app/{BARK_KEY}"
    payload = {
        "title": "OKX K线形态检测",
        "body": message
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        logging.info(f"Bark 通知发送成功: {message}")
    except Exception as e:
        logging.error(f"发送通知失败: {e}")


def format_notification_message(matching_symbols):
    """格式化通知消息"""
    if not matching_symbols:
        return "没有检测到符合条件的下垂线形态"

    message = "以下标的出现下垂线形态：\n\n"
    for symbol, kline in matching_symbols:
        timestamp, open_price, high_price, low_price, close_price, volume = kline[:6]
        formatted_time = datetime.fromtimestamp(int(timestamp) / 1000).strftime('%Y-%m-%d %H:%M:%S')
        message += f"🔹 {symbol}\n"
        message += f"   时间: {formatted_time}\n"
        message += f"   开盘价: {open_price}\n"
        message += f"   最高价: {high_price}\n"
        message += f"   最低价: {low_price}\n"
        message += f"   收盘价: {close_price}\n"
        message += f"   成交量: {volume}\n\n"
    return message


def main():
    logging.info("开始检测多个OKX标的的K线形态...")
    matching_symbols = []

    # 使用线程池并行获取所有标的数据
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(TARGET_SYMBOLS)) as executor:
        # 提交所有任务到线程池
        future_to_symbol = {executor.submit(get_okx_kline, symbol): symbol for symbol in TARGET_SYMBOLS}

        # 收集所有结果
        for future in concurrent.futures.as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                symbol, kline = future.result()
                if kline:
                    # 检查是否为下垂线形态
                    if is_hanging_man(kline):
                        logging.info(f"检测到{symbol}的下垂线形态!")
                        matching_symbols.append((symbol, kline))
                    else:
                        logging.info(f"{symbol}当前K线不是下垂线形态")
                else:
                    logging.warning(f"未能获取{symbol}的有效K线数据")
            except Exception as e:
                logging.error(f"获取{symbol}数据时发生异常: {e}")

    # 汇总通知
    if matching_symbols:
        message = format_notification_message(matching_symbols)
        logging.info(f"检测到下垂线形态的标的:\n{message}")
        if BARK_KEY:
            send_bark_notification(message)
    else:
        logging.info("没有检测到符合条件的下垂线形态")


if __name__ == "__main__":
    main()
