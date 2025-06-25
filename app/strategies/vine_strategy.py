import os
import pandas as pd
import requests
import json
import random
import string
from datetime import datetime, timezone, timedelta
import okx.MarketData as MarketData
import okx.Trade as Trade

class VineStrategy:
    def __init__(self):
        # 交易标的参数
        self.INST_ID = "TRUMP-USDT-SWAP"
        self.BAR = "5m"
        self.LIMIT = 2
        self.LEVERAGE = 10
        self.SizePoint = 2

        # 振幅阈值参数
        self.RANGE1_MIN = 0.8
        self.RANGE1_MAX = 1.8

    def run(self):
        # 模拟策略运行，返回一个状态字符串
        # 实际应用中，这里会包含复杂的交易逻辑
        return "Vine Strategy Run Successfully"
        self.RANGE2_THRESHOLD = 2

        # 交易执行参数
        self.MARGIN = 5
        self.TAKE_PROFIT_PERCENT = 0.015
        self.STOP_LOSS_PERCENT = 0.03

        # API配置
        self.API_KEY = os.getenv("OKX_API_KEY")
        self.SECRET_KEY = os.getenv("OKX_SECRET_KEY")
        self.PASSPHRASE = os.getenv("OKX_PASSPHRASE")
        self.FLAG = os.getenv("OKX_FLAG", "0")

        # 初始化API客户端
        self.market_api = MarketData.MarketAPI(
            api_key=self.API_KEY,
            api_secret_key=self.SECRET_KEY,
            passphrase=self.PASSPHRASE,
            flag=self.FLAG,
            debug=False
        )

        self.trade_api = Trade.TradeAPI(
            api_key=self.API_KEY,
            api_secret_key=self.SECRET_KEY,
            passphrase=self.PASSPHRASE,
            flag=self.FLAG,
            debug=False
        )

        # 状态追踪
        self.last_run_time = None
        self.last_error = None
        self.is_running = True

    def get_beijing_time(self):
        """获取北京时间"""
        beijing_tz = timezone(timedelta(hours=8))
        return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")

    def update_parameters(self, **kwargs):
        """更新策略参数"""
        for key, value in kwargs.items():
            if hasattr(self, key.upper()):
                setattr(self, key.upper(), value)

    def get_status(self):
        """获取策略运行状态"""
        return {
            "is_running": self.is_running,
            "last_run_time": self.last_run_time,
            "last_error": self.last_error,
            "parameters": {
                "range1_min": self.RANGE1_MIN,
                "range1_max": self.RANGE1_MAX,
                "range2_threshold": self.RANGE2_THRESHOLD,
                "take_profit_percent": self.TAKE_PROFIT_PERCENT,
                "stop_loss_percent": self.STOP_LOSS_PERCENT,
                "margin": self.MARGIN
            }
        }

    def get_orders(self):
        """获取当前订单信息"""
        try:
            result = self.trade_api.get_order_list(instId=self.INST_ID)
            if result and result.get('code') == '0':
                return result.get('data', [])
            return []
        except Exception as e:
            self.last_error = str(e)
            return []

    def get_performance(self):
        """获取策略表现数据"""
        try:
            # 获取最近的成交记录
            result = self.trade_api.get_orders_history(instId=self.INST_ID, limit='100')
            if result and result.get('code') == '0':
                orders = result.get('data', [])
                
                # 计算收益统计
                total_pnl = 0
                win_count = 0
                loss_count = 0
                
                for order in orders:
                    if order.get('state') == 'filled':
                        pnl = float(order.get('pnl', 0))
                        total_pnl += pnl
                        if pnl > 0:
                            win_count += 1
                        elif pnl < 0:
                            loss_count += 1
                
                total_trades = win_count + loss_count
                win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
                
                return {
                    "total_pnl": total_pnl,
                    "win_count": win_count,
                    "loss_count": loss_count,
                    "win_rate": win_rate,
                    "total_trades": total_trades
                }
            
            return {
                "error": "Failed to fetch orders history"
            }
        except Exception as e:
            self.last_error = str(e)
            return {
                "error": str(e)
            }
