#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务名称
name: VINE-K8趋势策略-V4
定时规则
cron: 1 */5 * * * *
"""

import os
import sys
import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pandas as pd

# 添加utils目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from okx_utils import (
    get_shanghai_time, get_orders_pending, cancel_pending_open_orders,
    build_order_params, send_bark_notification
)

# 导入okx库
import okx.Trade as Trade
import okx.MarketData as MarketData

def get_kline_data(inst_id: str, bar: str, limit: int, flag: str) -> List:
    """直接从OKX API获取K线数据 (V4修正：使用get_candlesticks)"""
    print(f"[DEBUG] 直接从OKX拉取K线: inst_id={inst_id}, bar={bar}, limit={limit}")
    try:
        marketDataAPI = MarketData.MarketAPI(flag=flag)
        # V4修正：调用正确的API接口以获取包含状态位的K线数据
        result = marketDataAPI.get_candlesticks(instId=inst_id, bar=bar, limit=str(limit))
        if result and result.get('code') == '0' and result.get('data'):
            print(f"[DEBUG] 成功从OKX拉取到 {len(result['data'])} 条K线")
            return result['data']
        else:
            print(f"[ERROR] 从OKX拉取K线失败: {result}")
            return []
    except Exception as e:
        print(f"[ERROR] 拉取K线时发生异常: {e}")
        return []

class VINEK8StrategyV4:
    def __init__(self):
        # 策略参数
        self.inst_id = "VINE-USDT-SWAP"
        self.bar = "5m"
        self.kline_limit = 100
        self.leverage = 5
        self.contract_face_value = 10
        
        # 风控参数
        self.margin = 2
        self.take_profit_percent = 0.02
        self.stop_loss_percent = 0.015
        
        # 信号过滤参数
        self.min_body1 = 0.009
        self.max_body1 = 0.035
        self.max_total_range = 0.02
        
        # EMA趋势过滤参数
        self.ema_short = 13
        self.ema_mid = 34
        self.ema_long = 89
        self.enable_trend_filter = True
        
        # 交易参数
        self.enable_strategy = True
        
        # 获取账户配置
        self.accounts = self._get_accounts()
        
    def _get_accounts(self) -> List[Dict]:
        """获取所有账户配置"""
        accounts = []
        for i in range(1, 10):
            account_name = os.environ.get(f"OKX{i}_ACCOUNT_NAME")
            if account_name:
                accounts.append({
                    'name': account_name,
                    'api_key': os.environ.get(f"OKX{i}_API_KEY", ""),
                    'secret_key': os.environ.get(f"OKX{i}_SECRET_KEY", ""),
                    'passphrase': os.environ.get(f"OKX{i}_PASSPHRASE", ""),
                    'flag': os.environ.get(f"OKX{i}_FLAG", "0"),
                })
        return accounts
    
    def init_trade_api(self, api_key, secret_key, passphrase, flag="0"):
        """初始化交易API"""
        return Trade.TradeAPI(str(api_key), str(secret_key), str(passphrase), False, str(flag))
    
    def log(self, message: str, account_name: str = ""):
        """日志记录"""
        timestamp = get_shanghai_time()
        account_prefix = f"[{account_name}] " if account_name else ""
        print(f"[{timestamp}] {account_prefix}{message}")
    
    def analyze_kline(self, kline_data: List) -> Optional[Dict]:
        """K线分析函数 (V4更新：基于K线完结状态判断)"""
        
        # V4核心逻辑：寻找第一根已完结的K线作为k0
        k0_idx = -1
        for i, k in enumerate(kline_data):
            if k[8] == '1': # K线状态在第9个位置，索引为8
                k0_idx = i
                break
        
        if k0_idx == -1:
            self.log("[ERROR] 未在返回数据中找到任何已完结的K线。")
            return None
            
        # 确保有足够的数据进行分析 (k0, k1, ..., k5)
        if len(kline_data) <= k0_idx + 6:
            self.log(f"[ERROR] 数据不足，无法进行完整的K1~K5分析。需要 {k0_idx + 7} 根K线，实际 {len(kline_data)} 根。")
            return None

        k0_raw = kline_data[k0_idx]
        k1_raw = kline_data[k0_idx + 1]
        
        k0_ts_str = datetime.fromtimestamp(int(k0_raw[0]) / 1000).strftime('%Y-%m-%d %H:%M:%S')
        k1_ts_str = datetime.fromtimestamp(int(k1_raw[0]) / 1000).strftime('%Y-%m-%d %H:%M:%S')
        self.log(f"分析基准K线 k0 (最新已完结): {k0_ts_str}, k1: {k1_ts_str}")

        klines = [{'open': float(k[1]), 'high': float(k[2]), 'low': float(k[3]), 'close': float(k[4])} for k in kline_data]
        
        k0, k1 = klines[k0_idx], klines[k0_idx + 1]
        o0, c0 = k0['open'], k0['close']
        body0 = abs(c0 - o0) / o0
        k0_is_long, k0_is_short = c0 > o0, c0 < o0
        
        o1, c1 = k1['open'], k1['close']
        k1_is_long, k1_is_short = c1 > o1, c1 < o1
        
        same_direction = (k0_is_long and k1_is_long) or (k0_is_short and k1_is_short)
        
        total_range = sum(abs(klines[i]['close'] - klines[i]['open']) / klines[i]['open'] for i in range(k0_idx + 1, k0_idx + 6))
        
        can_entry = self.min_body1 < body0 < self.max_body1 and total_range < self.max_total_range and same_direction
        
        signal = ""
        if can_entry:
            signal = "LONG" if k0_is_long else "SHORT"
        
        return {
            'signal': signal, 'entry_price': c0, 'body0': body0, 'total_range': total_range,
            'k0_is_long': k0_is_long, 'k0_is_short': k0_is_short,
            'k1_is_long': k1_is_long, 'k1_is_short': k1_is_short,
            'same_direction': same_direction
        }
    
    def check_trend_with_pandas(self, kline_data: List) -> Tuple[bool, bool, Optional[Dict]]:
        """使用Pandas检查趋势"""
        if len(kline_data) < self.ema_long:
            self.log(f"[DEBUG] K线数量 {len(kline_data)} 不足以计算最长EMA周期 {self.ema_long}")
            return False, False, None

        df = pd.DataFrame(kline_data, columns=['ts', 'open', 'high', 'low', 'close', 'vol', 'volCcy', 'volCcyQuote', 'confirm'])
        df['close'] = df['close'].astype(float)
        df = df.iloc[::-1].reset_index(drop=True)

        ema_short_val = df['close'].ewm(span=self.ema_short, adjust=False).mean().iloc[-1]
        ema_mid_val = df['close'].ewm(span=self.ema_mid, adjust=False).mean().iloc[-1]
        ema_long_val = df['close'].ewm(span=self.ema_long, adjust=False).mean().iloc[-1]

        bullish_trend = ema_short_val > ema_mid_val and ema_mid_val > ema_long_val
        bearish_trend = ema_short_val < ema_mid_val and ema_mid_val < ema_long_val
        
        ema_values = {
            f"ema{self.ema_short}": ema_short_val,
            f"ema{self.ema_mid}": ema_mid_val,
            f"ema{self.ema_long}": ema_long_val,
        }
        return bullish_trend, bearish_trend, ema_values

    def check_and_cancel_orders(self, trade_api, account_name: str, latest_price: float) -> bool:
        """检查并撤销已超过止盈价格的委托"""
        self.log(f"检查账户委托状态", account_name)
        orders = get_orders_pending(trade_api, self.inst_id, account_prefix=account_name)
        if not orders:
            self.log(f"账户无未成交委托", account_name)
            return True
        
        cancel_needed = False
        for order in orders:
            if order.get('ordType') == 'limit':
                tp_price_str = order.get('attachAlgoOrds', [{}])[0].get('tpTriggerPx')
                if not tp_price_str: continue
                
                take_profit_price = float(tp_price_str)
                if order.get('side') == 'buy' and latest_price >= take_profit_price:
                    self.log(f"做多委托已超过止盈价格，准备撤销: {order['ordId']}", account_name)
                    cancel_needed = True
                elif order.get('side') == 'sell' and latest_price <= take_profit_price:
                    self.log(f"做空委托已超过止盈价格，准备撤销: {order['ordId']}", account_name)
                    cancel_needed = True
        
        if cancel_needed:
            return cancel_pending_open_orders(trade_api, self.inst_id, account_prefix=account_name)
        return True
    
    def calculate_order_size(self, latest_price: float) -> float:
        contract_value = self.contract_face_value * latest_price
        order_size = (self.margin * self.leverage) / contract_value
        return max(10, int(order_size // 10) * 10)
    
    def place_order(self, trade_api, account_name: str, signal: str, entry_price: float, size: float) -> Optional[Dict]:
        """下单"""
        side = "buy" if signal == "LONG" else "sell"
        pos_side = "long" if signal == "LONG" else "short"
        
        if signal == "LONG":
            tp_price = round(entry_price * (1 + self.take_profit_percent), 5)
            sl_price = round(entry_price * (1 - self.stop_loss_percent), 5)
        else:
            tp_price = round(entry_price * (1 - self.take_profit_percent), 5)
            sl_price = round(entry_price * (1 + self.stop_loss_percent), 5)
        
        order_params = build_order_params(
            inst_id=self.inst_id, side=side, entry_price=entry_price, size=size,
            pos_side=pos_side, take_profit=tp_price, stop_loss=sl_price, prefix="VINEV4"
        )
        self.log(f"准备下单: {signal} {size}张 @ {entry_price}", account_name)
        self.log(f"[DEBUG] 提交OKX下单参数: {order_params}", account_name)
        
        result = trade_api.place_order(**order_params)
        self.log(f"[DEBUG] OKX下单返回: {result}", account_name)
        
        if result and result.get('code') == '0':
            order_data = result.get('data', [{}])[0]
            self.log(f"下单成功: {order_data.get('ordId')}", account_name)
            self._send_order_notification(account_name, signal, entry_price, size, tp_price, sl_price, order_params['clOrdId'])
            return order_data
        else:
            error_msg = result.get('data', [{}])[0].get('sMsg', '未知错误') if result and result.get('data') else 'API返回格式错误'
            self.log(f"下单失败: {error_msg}", account_name)
            self._send_error_notification(account_name, signal, entry_price, size, error_msg, result)
            return None
    
    def _send_order_notification(self, account_name, signal, entry_price, size, tp_price, sl_price, cl_ord_id):
        title = "VINE-K8趋势策略-V4信号开仓"
        content = f"""账户: {account_name}
交易标的: {self.inst_id}
信号类型: {'做多' if signal == 'LONG' else '做空'}
入场价格: {entry_price:.4f}
委托数量: {size:.2f}
保证金: {self.margin} USDT
止盈价格: {tp_price:.4f}
止损价格: {sl_price:.4f}
客户订单ID: {cl_ord_id}
时间: {get_shanghai_time()}"""
        send_bark_notification(title, content)
    
    def _send_error_notification(self, account_name, signal, entry_price, size, error_msg, result):
        title = "VINE-K8趋势策略-V4信号开仓"
        content = f"""账户: {account_name}
交易标的: {self.inst_id}
信号类型: {'做多' if signal == 'LONG' else '做空'}
入场价格: {entry_price:.4f}
委托数量: {size:.2f}
保证金: {self.margin} USDT
时间: {get_shanghai_time()}

⚠️ 下单失败 ⚠️
错误: {error_msg}
服务器响应代码: {result.get('code', 'N/A')}
服务器响应消息: {result.get('msg', 'N/A')}"""
        send_bark_notification(title, content)
    
    def run_strategy(self):
        if not self.enable_strategy:
            self.log("策略已禁用")
            return
        if not self.accounts:
            self.log("未配置任何账户")
            return

        kline_data = get_kline_data(self.inst_id, self.bar, self.kline_limit, self.accounts[0]['flag'])
        if not kline_data:
            self.log("获取K线数据失败，终止策略")
            return
        
        latest_price = float(kline_data[0][4])
        self.log(f"最新合约价格: {latest_price}")
        
        analysis = self.analyze_kline(kline_data)
        if not analysis:
            self.log("K线分析失败，终止策略")
            return
        
        bullish_trend, bearish_trend, ema_values = self.check_trend_with_pandas(kline_data)
        if ema_values:
            trend_str = "多头趋势" if bullish_trend else "空头趋势" if bearish_trend else "震荡/无明显趋势"
            self.log(f"[DEBUG] EMA({self.ema_short})={ema_values[f'ema{self.ema_short}']:.5f}, EMA({self.ema_mid})={ema_values[f'ema{self.ema_mid}']:.5f}, EMA({self.ema_long})={ema_values[f'ema{self.ema_long}']:.5f}, 趋势判断: {trend_str}")
        
        self.log(f"K0振幅: {analysis['body0']*100:.2f}%, K1~K5总振幅: {analysis['total_range']*100:.2f}%, 方向一致性: {'是' if analysis['same_direction'] else '否'}")
        
        long_condition = analysis['signal'] == "LONG" and (not self.enable_trend_filter or bullish_trend)
        short_condition = analysis['signal'] == "SHORT" and (not self.enable_trend_filter or bearish_trend)
        
        order_size = self.calculate_order_size(latest_price)
        self.log(f"根据最新价格 {latest_price} 计算的下单数量: {order_size} 张")
        
        if not (long_condition or short_condition):
            self.log("无交易信号")
            return

        for account in self.accounts:
            account_name = account['name']
            self.log(f"开始处理账户: {account_name}")
            try:
                trade_api = self.init_trade_api(**account)
                if not self.check_and_cancel_orders(trade_api, account_name, latest_price):
                    self.log(f"账户 {account_name} 撤销委托失败，跳过处理")
                    continue
                
                signal = "LONG" if long_condition else "SHORT"
                self.place_order(trade_api, account_name, signal, analysis['entry_price'], order_size)
            except Exception as e:
                self.log(f"处理账户 {account_name} 时发生异常: {str(e)}")

def main():
    strategy = VINEK8StrategyV4()
    print(f"VINE-K8趋势策略V4启动")
    strategy.run_strategy()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"[FATAL] 主程序异常: {e}\n{traceback.format_exc()}")
