# -*- coding: utf-8 -*-
"""
实盘交易策略脚本（简化版）
配置区域在代码顶部，请先填写账户信息再运行
"""

import os
import requests
import json
from datetime import datetime
import concurrent.futures
import logging

# ===================== 账户配置区域（请先填写） =====================
# OKX API 配置
API_KEY = "your_api_key"        # 替换为你的API Key
SECRET_KEY = "your_secret_key"  # 替换为你的Secret Key
PASSPHRASE = "your_passphrase"  # 替换为你的Passphrase（如果是合约账户）

# 合约配置
CONTRACT_ID = "BTC-USDT-SWAP"   # 监控的主力合约
LEVERAGE = 10                  # 杠杆倍数

# 交易参数
AMPLITUDE_THRESHOLD = 1.5       # 振幅阈值（百分比）
TRADE_VOLUME = 0.001            # 每次交易手数
# ======================================================================

# ===================== 系统配置（根据需要调整） =====================
LOG_FILE = 'quant_trading.log'
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
MAX_WORKERS = 5                 # 并发线程数
# ======================================================================

# 初始化日志系统
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

class TradingBot:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'OK-ACCESS-KEY': API_KEY})
        self.session.headers.update({'OK-ACCESS-SIGN': ''})  # 签名由SDK处理
        self.session.headers.update({'OK-ACCESS-TIMESTAMP': ''})
        self.session.headers.update({'OK-ACCESS-PASSPHRASE': PASSPHRASE})

    def get_market_data(self, symbol):
        """获取最新1分钟K线数据"""
        endpoint = "/api/v5/market/candles"
        params = {
            "instId": symbol,
            "bar": "1m",
            "limit": 1
        }
        try:
            response = self.session.get(
                f"https://www.okx.com{endpoint}",
                params=params,
                timeout=5
            )
            data = response.json()
            if data['code'] == '0' and data['data']:
                return data['data'][0]
            logging.warning(f"获取数据失败: {data.get('msg')}")
            return None
        except Exception as e:
            logging.error(f"请求异常: {str(e)}")
            return None

    def analyze_trend(self, kline):
        """分析价格趋势"""
        try:
            # 解析数据 [时间戳, 开盘价, 最高价, 最低价, 收盘价, 成交量]
            timestamp, open_, high, low, close, vol = kline
            open_ = float(open_)
            high = float(high)
            low = float(low)
            close = float(close)
            
            # 判断趋势
            trend = 'up' if close > open_ else 'down' if close < open_ else 'flat'
            
            # 计算振幅
            body = abs(close - open_)
            amplitude = ((high - low) / body) * 100 if body != 0 else 0
            
            return {
                'timestamp': timestamp,
                'open': open_,
                'high': high,
                'low': low,
                'close': close,
                'volume': vol,
                'trend': trend,
                'amplitude': amplitude
            }
        except Exception as e:
            logging.error(f"数据分析异常: {str(e)}")
            return None

    def generate_signal(self, analysis):
        """生成交易信号"""
        if analysis['amplitude'] <= AMPLITUDE_THRESHOLD:
            return None
            
        signal = None
        if analysis['trend'] == 'down':
            # 下跌趋势且振幅达标，开多单
            signal = {
                'action': 'OPEN_LONG',
                'price': analysis['close'],
                'reason': f"下跌趋势，振幅{analysis['amplitude']:.1f}%"
            }
        elif analysis['trend'] == 'up':
            # 上涨趋势且振幅达标，开空单
            signal = {
                'action': 'OPEN_SHORT',
                'price': analysis['close'],
                'reason': f"上涨趋势，振幅{analysis['amplitude']:.1f}%"
            }
        return signal

    def execute_trade(self, signal):
        """执行交易指令"""
        if not signal:
            return False
            
        try:
            # 此处应接入实际交易API，以下为模拟执行
            logging.info(f"执行交易: {signal['action']} @ {signal['price']}")
            # 实际交易代码示例：
            # resp = self.session.post(..., json={
            #     "instId": CONTRACT_ID,
            #     "tdMode": "cross",
            #     "side": "buy" if signal['action'] == 'OPEN_LONG' else 'sell',
            #     "ordType": "market",
            #     "sz": str(TRADE_VOLUME * LEVERAGE)
            # })
            return True
        except Exception as e:
            logging.error(f"交易执行失败: {str(e)}")
            return False

    def run(self):
        """主运行循环"""
        symbols = [CONTRACT_ID]  # 可扩展为多标的监控
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_symbol = {
                executor.submit(self.get_market_data, symbol): symbol 
                for symbol in symbols
            }
            
            for future in concurrent.futures.as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    raw_data = future.result()
                    if raw_data:
                        analysis = self.analyze_trend(raw_data)
                        if analysis:
                            signal = self.generate_signal(analysis)
                            if signal:
                                self.execute_trade(signal)
                except Exception as e:
                    logging.error(f"处理{symbol}时发生错误: {str(e)}")

if __name__ == "__main__":
    bot = TradingBot()
    bot.run()
