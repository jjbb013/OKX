"""
任务名称
name: 振幅检查 Air
定时规则
cron: 50 * * * * *
"""


import requests
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('amplitude_monitor.log'),
        logging.StreamHandler()
    ]
)

# OKX API 配置
OKX_API_URL = "https://www.okx.com/api/v5/market/candles"
SYMBOLS = {
    "btc-usdt-swap": {
        "symbol": "BTC-USDT-SWAP",
        "upper_threshold": 1.0,
        "lower_threshold": -1.0
    },
    "vine-usdt-swap": {
        "symbol": "VINE-USDT-SWAP",
        "upper_threshold": 1.0,
        "lower_threshold": -1.0
    },
    "trump-usdt-swap": {
        "symbol": "TRUMP-USDT-SWAP",
        "upper_threshold": 1.0,
        "lower_threshold": -1.0
    },
    "eth-usdt-swap": {
        "symbol": "ETH-USDT-SWAP",
        "upper_threshold": 1.0,
        "lower_threshold": -1.0
    },
    "ada-usdt-swap": {
        "symbol": "ADA-USDT-SWAP",
        "upper_threshold": 1.0,
        "lower_threshold": -1.0
    },
    "doge-usdt-swap": {
        "symbol": "DOGE-USDT-SWAP",
        "upper_threshold": 1.0,
        "lower_threshold": -1.0
    },
}

# Bark 推送配置
BARK_API_KEY = 'oZaeqGLJzRLSxW7dJqeACn'  # 替换为你的 Bark API Key

def get_kline(symbol, interval="1m", limit=1):
    """获取OKX的最新1根K线数据"""
    params = {
        "instId": symbol,
        "bar": interval,
        "limit": limit,
    }
    try:
        response = requests.get(OKX_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data["code"] != "0":
            logging.warning(f"获取 {symbol} K 线失败: {data['msg']}")
            return None

        if not data["data"]:
            logging.warning(f"{symbol} 未获取到 K 线数据")
            return None

        try:
            kline = data["data"][0]
            return [
                int(kline[0]),  # 时间戳
                float(kline[1]),  # 开盘价
                float(kline[2]),  # 最高价
                float(kline[3]),  # 最低价
                float(kline[4]),  # 收盘价
                float(kline[5]),  # 成交量
            ]
        except (IndexError, ValueError) as e:
            logging.error(f"解析 K 线数据错误: {e}, 数据: {kline}")
            return None

    except requests.exceptions.RequestException as e:
        logging.error(f"请求 OKX API 失败: {e}")
        return None

def calculate_amplitude(kline):
    """基于开盘价计算振幅"""
    if not kline:
        return None
    open_price = kline[1]  # 开盘价
    high_price = kline[2]  # 最高价
    low_price = kline[3]  # 最低价
    
    if open_price == 0:  # 避免除零错误
        return None
    
    # 新的振幅计算逻辑：基于开盘价和最新价的波动比例
    amplitude = ((high_price - low_price) / open_price) * 100
    return round(amplitude, 2)

def send_bark_notification(title, content):
    """通过Bark发送通知"""
    if not BARK_API_KEY:
        logging.warning("Bark API密钥未配置")
        return

    url = f"https://api.day.app/{BARK_API_KEY}"
    payload = {
        "title": title,
        "body": content
    }
    proxies = {}  # 显式禁用代理

    try:
        response = requests.post(
            url,
            json=payload
        )
        response.raise_for_status()
        logging.info(f"Bark 通知发送成功: {title}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Bark 推送失败: {e}")

def monitor_single_symbol(symbol_key, config):
    """监控单个标的的振幅"""
    symbol_name = config["symbol"]
    upper_threshold = config["upper_threshold"]
    lower_threshold = config["lower_threshold"]

    logging.info(f"正在检查 {symbol_name}...")
    kline = get_kline(symbol_name)

    if not kline:
        logging.warning(f"{symbol_name} 未获取到有效 K 线数据")
        return

    amplitude = calculate_amplitude(kline)

    if amplitude is None:
        logging.warning(f"{symbol_name} 振幅计算失败")
        return

    logging.info(f"{symbol_name} 当前振幅: {amplitude}%")

    # 判断振幅是否超过阈值（正负两个方向）
    if amplitude > upper_threshold or amplitude < lower_threshold:
        title = f"⚠️ {symbol_name} 振幅预警 Air"
        content = (
            f"当前振幅: {amplitude}%\n"
            f"阈值: {upper_threshold}%\n"
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"开盘价: {kline[1]}\n"
            f"最高价: {kline[2]}\n"
            f"最低价: {kline[3]}\n"
            f"最新价: {kline[4]}"
        )
        send_bark_notification(title, content)
    else:
        logging.info(f"{symbol_name} 振幅未超过阈值 ({amplitude}% <= {upper_threshold}% and {amplitude}% >= {lower_threshold}%)")

def monitor_amplitude():
    """监控K线振幅并发送通知"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"===== 开始监控 ({current_time}) =====")

    with ThreadPoolExecutor(max_workers=len(SYMBOLS)) as executor:
        futures = {
            executor.submit(monitor_single_symbol, symbol_key, config): symbol_key
            for symbol_key, config in SYMBOLS.items()
        }

        for future in as_completed(futures):
            symbol_key = futures[future]
            try:
                future.result()
            except Exception as e:
                logging.error(f"监控 {symbol_key} 时发生错误: {e}")

    logging.info(f"===== 监控结束 =====\n")

if __name__ == "__main__":
    monitor_amplitude()
