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
    "btc-usdt-swap": {"symbol": "BTC-USDT-SWAP", "threshold": 1.0},
    "vine-usdt-swap": {"symbol": "VINE-USDT-SWAP", "threshold": 5.0},
    "trump-usdt-swap": {"symbol": "TRUMP-USDT-SWAP", "threshold": 5.0},
    "eth-usdt-swap": {"symbol": "ETH-USDT-SWAP", "threshold": 1.0},
    "ada-usdt-swap": {"symbol": "ADA-USDT-SWAP", "threshold": 1.0},
    "doge-usdt-swap": {"symbol": "DOGE-USDT-SWAP", "threshold": 1.0},
}

# Bark 推送配置
BARK_API_KEY = 'oZaeqGLJzRLSxW7dJqeACn'  # 替换为你的 Bark API Key
BARK_PUSH_URL = f"https://api.day.app/{BARK_API_KEY}/{{}}"

def get_kline(symbol, interval="1m", limit=2):
    """获取OKX的K线数据"""
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

        klines = []
        for candle in data["data"]:
            try:
                klines.append([
                    int(candle[0]),  # 时间戳
                    float(candle[1]),  # 开盘价
                    float(candle[2]),  # 最高价
                    float(candle[3]),  # 最低价
                    float(candle[4]),  # 收盘价
                    float(candle[5]),  # 成交量
                ])
            except (IndexError, ValueError) as e:
                logging.error(f"解析 K 线数据错误: {e}, 数据: {candle}")
                continue
        return klines

    except requests.exceptions.RequestException as e:
        logging.error(f"请求 OKX API 失败: {e}")
        return None

def calculate_amplitude(kline):
    """计算K线振幅"""
    if not kline or len(kline) < 4:
        return None
    high = kline[2]  # 最高价
    low = kline[3]   # 最低价
    if low == 0:  # 避免除零错误
        return None
    amplitude = (high - low) / low * 100
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
    threshold = config["threshold"]

    logging.info(f"正在检查 {symbol_name}...")
    klines = get_kline(symbol_name)

    if not klines or len(klines) < 1:
        logging.warning(f"{symbol_name} 未获取到有效 K 线数据")
        return

    latest_kline = klines[-1]
    amplitude = calculate_amplitude(latest_kline)

    if amplitude is None:
        logging.warning(f"{symbol_name} 振幅计算失败")
        return

    logging.info(f"{symbol_name} 当前振幅: {amplitude}%")

    if amplitude > threshold:
        title = f"⚠️ {symbol_name} 振幅预警"
        content = (
            f"当前振幅: {amplitude}% (阈值: {threshold}%)\n"
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"最新价: {latest_kline[4]}\n"
            f"最高价: {latest_kline[2]}\n"
            f"最低价: {latest_kline[3]}"
        )
        send_bark_notification(title, content)
    else:
        logging.info(f"{symbol_name} 振幅未超过阈值 ({amplitude}% <= {threshold}%)")

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
