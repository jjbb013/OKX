#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务名称
name: VINE-K8趋势策略
定时规则
cron: 1 */5 * * * *
"""


import os
import sys
import time
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import csv
from glob import glob

# 添加utils目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from okx_utils import (
    get_shanghai_time, get_orders_pending, cancel_pending_open_orders,
    generate_clord_id, build_order_params, send_bark_notification
)

# 导入okx库
import okx.Trade as Trade
import okx.MarketData as MarketData

DATA_DIR = '/ql/data/VINE-5M-DATA/'
CSV_PREFIX = 'VINE-5M'
MAX_ROWS = 1000
MIN_ROWS = 150

def get_latest_csv_file(dir_path, prefix):
    print(f"[DEBUG] 查找最新CSV文件: 目录={dir_path}, 前缀={prefix}")
    files = sorted(glob(os.path.join(dir_path, f"{prefix}-*.csv")))
    print(f"[DEBUG] 找到文件: {files}")
    if not files:
        return None
    return files[-1]

def load_kline_from_csv(filepath):
    print(f"[DEBUG] 读取CSV文件: {filepath}")
    if not filepath or not os.path.exists(filepath):
        print(f"[DEBUG] 文件不存在: {filepath}")
        return []
    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        data = list(reader)
    print(f"[DEBUG] 读取到{len(data)}条K线数据")
    return data

def save_kline_to_csv(filepath, kline_data):
    print(f"[DEBUG] 保存{len(kline_data)}条K线到CSV: {filepath}")
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(kline_data)
    print(f"[DEBUG] 保存完成")

def append_kline_to_csv(filepath, kline_data):
    print(f"[DEBUG] 追加K线到CSV: {filepath}")
    existing = load_kline_from_csv(filepath)
    existing_ts = set(row[0] for row in existing)
    new_rows = [row for row in kline_data if row[0] not in existing_ts]
    print(f"[DEBUG] 新增{len(new_rows)}条K线")
    if not new_rows:
        return
    with open(filepath, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(new_rows)
    print(f"[DEBUG] 追加完成")

def fetch_kline_from_okx(inst_id, bar, limit, flag):
    print(f"[DEBUG] 拉取OKX K线: inst_id={inst_id}, bar={bar}, limit={limit}, flag={flag}")
    marketDataAPI = MarketData.MarketAPI(flag=flag)
    result = marketDataAPI.get_mark_price_candlesticks(instId=inst_id, bar=bar, limit=str(limit))
    print(f"[DEBUG] OKX返回: {result}")
    if result and result.get('code') == '0':
        return result['data']
    return []

def rotate_csv_file_if_needed(dir_path, prefix, max_rows):
    latest_file = get_latest_csv_file(dir_path, prefix)
    if not latest_file:
        new_file = os.path.join(dir_path, f"{prefix}-1.csv")
        print(f"[DEBUG] 新建CSV文件: {new_file}")
        return new_file
    rows = load_kline_from_csv(latest_file)
    if len(rows) < max_rows:
        return latest_file
    idx = int(latest_file.split('-')[-1].replace('.csv', '')) + 1
    new_file = os.path.join(dir_path, f"{prefix}-{idx}.csv")
    print(f"[DEBUG] 文件超{max_rows}条，轮换新文件: {new_file}")
    return new_file

def get_kline_data_with_cache(inst_id, bar, min_rows=MIN_ROWS, max_rows=MAX_ROWS, flag='0'):
    print(f"[DEBUG] 开始获取K线数据，目标最少{min_rows}条")
    os.makedirs(DATA_DIR, exist_ok=True)
    latest_csv = get_latest_csv_file(DATA_DIR, CSV_PREFIX)
    kline_data = load_kline_from_csv(latest_csv) if latest_csv else []
    print(f"[DEBUG] 当前本地K线数量: {len(kline_data)}")
    if len(kline_data) < min_rows:
        fetch_count = max(min_rows - len(kline_data), min_rows)
        print(f"[DEBUG] 本地K线不足，需拉取{fetch_count}条")
        new_data = fetch_kline_from_okx(inst_id, bar, fetch_count, flag)
        all_data = {row[0]: row for row in (kline_data + new_data)}
        kline_data = [all_data[ts] for ts in sorted(all_data.keys())]
        csv_path = rotate_csv_file_if_needed(DATA_DIR, CSV_PREFIX, max_rows)
        save_kline_to_csv(csv_path, kline_data[-max_rows:])
        latest_csv = csv_path
    new_data = fetch_kline_from_okx(inst_id, bar, 5, flag)
    append_kline_to_csv(latest_csv, new_data)
    if len(load_kline_from_csv(latest_csv)) > max_rows:
        csv_path = rotate_csv_file_if_needed(DATA_DIR, CSV_PREFIX, max_rows)
        save_kline_to_csv(csv_path, load_kline_from_csv(latest_csv)[-max_rows:])
        latest_csv = csv_path
    final_data = load_kline_from_csv(latest_csv)[-min_rows:]
    print(f"[DEBUG] 最终返回K线数量: {len(final_data)}")
    return final_data

class VINEK8Strategy:
    def __init__(self):
        # 策略参数
        self.inst_id = "VINE-USDT-SWAP"
        self.bar = "5m"
        self.limit = 8
        self.leverage = 5
        self.contract_face_value = 10  # VINE-USDT-SWAP合约面值为10美元
        
        # 风控参数
        self.margin = 1  # 保证金(USDT)
        self.take_profit_percent = 0.02  # 止盈2%
        self.stop_loss_percent = 0.015   # 止损1.5%
        
        # 信号过滤参数
        self.min_body1 = 0.009  # K0最小实体振幅(0.9%)
        self.max_body1 = 0.035  # K0最大实体振幅(3.5%)
        self.max_total_range = 0.02  # K1~K5总振幅上限(2%)
        
        # EMA趋势过滤参数
        self.ema21 = 21
        self.ema60 = 60
        self.ema144 = 144
        self.enable_trend_filter = True
        
        # 交易参数
        self.trade_qty = 3000  # 交易数量(张)
        self.enable_strategy = True
        
        # 获取账户配置
        self.accounts = self._get_accounts()
        
    def _get_accounts(self) -> List[Dict]:
        """获取所有账户配置"""
        accounts = []
        
        # 检查OKX1_ACCOUNT_NAME
        account1_name = os.environ.get("OKX1_ACCOUNT_NAME")
        if account1_name:
            accounts.append({
                'name': account1_name,
                'api_key': os.environ.get("OKX1_API_KEY", ""),
                'secret_key': os.environ.get("OKX1_SECRET_KEY", ""),
                'passphrase': os.environ.get("OKX1_PASSPHRASE", ""),
                'flag': os.environ.get("OKX1_FLAG", "0"),
                'suffix': ""
            })
        
        # 检查OKX2_ACCOUNT_NAME
        account2_name = os.environ.get("OKX2_ACCOUNT_NAME")
        if account2_name:
            accounts.append({
                'name': account2_name,
                'api_key': os.environ.get("OKX2_API_KEY", ""),
                'secret_key': os.environ.get("OKX2_SECRET_KEY", ""),
                'passphrase': os.environ.get("OKX2_PASSPHRASE", ""),
                'flag': os.environ.get("OKX2_FLAG", "0"),
                'suffix': ""
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
    
    def calculate_ema(self, prices: List[float], period: int) -> Optional[float]:
        """计算EMA"""
        if len(prices) < period:
            return None
        
        alpha = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = alpha * price + (1 - alpha) * ema
        
        return ema
    
    def analyze_kline(self, kline_data: List) -> Optional[Dict]:
        """K线分析函数"""
        if len(kline_data) < 6:
            return None
        
        # 解析K线数据 (时间戳, 开盘价, 最高价, 最低价, 收盘价, 成交量, 成交额)
        klines = []
        for kline in kline_data:
            klines.append({
                'open': float(kline[1]),
                'high': float(kline[2]),
                'low': float(kline[3]),
                'close': float(kline[4])
            })
        
        # 使用前一根K线进行判断（因为最新K线是未收盘K线）
        k0 = klines[1]  # 前一根K线
        o0 = k0['open']
        c0 = k0['close']
        body0 = abs(c0 - o0) / o0
        k0_is_long = c0 > o0
        k0_is_short = c0 < o0
        
        # 获取K1数据 (前两根K线)
        k1 = klines[2]
        o1 = k1['open']
        c1 = k1['close']
        k1_is_long = c1 > o1
        k1_is_short = c1 < o1
        
        # 判断K0和K1是否同方向
        both_long = k0_is_long and k1_is_long
        both_short = k0_is_short and k1_is_short
        same_direction = both_long or both_short
        
        # 确定开仓方向
        is_long = both_long
        is_short = both_short
        
        # 计算K1~K5总振幅 (前5根K线) 来观察
        total_range = 0.0
        for i in range(2, 7):  # 从第2根到第6根K线
            if i < len(klines):
                oi = klines[i]['open']
                ci = klines[i]['close']
                rng = abs(ci - oi) / oi
                total_range += rng
        
        # 判断入场条件：振幅符合 + 方向一致
        can_entry = (body0 > self.min_body1 and 
                    body0 < self.max_body1 and 
                    total_range < self.max_total_range and 
                    same_direction)
        
        entry_price = c0
        
        # 确定信号
        signal = ""
        if can_entry:
            if is_long:
                signal = "LONG"
            elif is_short:
                signal = "SHORT"
        
        return {
            'signal': signal,
            'entry_price': entry_price,
            'body0': body0,
            'total_range': total_range,
            'is_long': is_long,
            'is_short': is_short,
            'can_entry': can_entry,
            'same_direction': same_direction,
            'k0_is_long': k0_is_long,
            'k0_is_short': k0_is_short,
            'k1_is_long': k1_is_long,
            'k1_is_short': k1_is_short
        }
    
    def check_trend(self, kline_data: List) -> Tuple[bool, bool]:
        """检查趋势"""
        if len(kline_data) < self.ema144:
            return False, False
        
        # 获取收盘价列表
        closes = [float(kline[4]) for kline in kline_data]
        closes.reverse()  # 反转列表，使最新的在前面
        
        # 计算EMA
        ema21_value = self.calculate_ema(closes, self.ema21)
        ema60_value = self.calculate_ema(closes, self.ema60)
        ema144_value = self.calculate_ema(closes, self.ema144)
        
        if ema21_value is None or ema60_value is None or ema144_value is None:
            return False, False
        
        # 趋势判断
        bullish_trend = ema21_value > ema60_value and ema60_value > ema144_value
        bearish_trend = ema21_value < ema60_value and ema60_value < ema144_value
        
        return bullish_trend, bearish_trend
    
    def check_and_cancel_orders(self, trade_api, account_name: str, latest_price: float) -> bool:
        """检查并撤销已超过止盈价格的委托"""
        self.log(f"检查账户委托状态", account_name)
        
        # 获取未成交订单
        orders = get_orders_pending(trade_api, self.inst_id, account_prefix=account_name)
        if not orders:
            self.log(f"账户无未成交委托", account_name)
            return True
        
        cancel_needed = False
        for order in orders:
            if order.get('ordType') == 'limit':
                # 检查做多委托
                if order.get('side') == 'buy' and order.get('posSide') == 'long':
                    take_profit_price = float(order.get('attachAlgoOrds', [{}])[0].get('tpTriggerPx', 0))
                    if take_profit_price > 0 and latest_price >= take_profit_price:
                        self.log(f"做多委托已超过止盈价格，准备撤销: {order['ordId']}", account_name)
                        cancel_needed = True
                
                # 检查做空委托
                elif order.get('side') == 'sell' and order.get('posSide') == 'short':
                    take_profit_price = float(order.get('attachAlgoOrds', [{}])[0].get('tpTriggerPx', 0))
                    if take_profit_price > 0 and latest_price <= take_profit_price:
                        self.log(f"做空委托已超过止盈价格，准备撤销: {order['ordId']}", account_name)
                        cancel_needed = True
        
        if cancel_needed:
            success = cancel_pending_open_orders(trade_api, self.inst_id, account_prefix=account_name)
            if success:
                self.log(f"成功撤销超过止盈价格的委托", account_name)
            else:
                self.log(f"撤销委托失败", account_name)
                return False
        
        return True
    
    def calculate_order_size(self, latest_price: float) -> float:
        # VINE合约每张面值10 VINE
        contract_vine = 10
        contract_value = contract_vine * latest_price  # 每张合约价值（USDT）
        order_size = (self.margin * self.leverage) / contract_value
        order_size = max(10, int(order_size // 10) * 10)
        return order_size
    
    def place_order(self, trade_api, account_name: str, signal: str, entry_price: float, size: float) -> Optional[Dict]:
        """下单"""
        try:
            # 确定交易方向
            if signal == "LONG":
                side = "buy"
                pos_side = "long"
            elif signal == "SHORT":
                side = "sell"
                pos_side = "short"
            else:
                self.log(f"无效信号: {signal}", account_name)
                return None
            
            # 计算止盈止损价格
            if signal == "LONG":
                take_profit_price = entry_price * (1 + self.take_profit_percent)
                stop_loss_price = entry_price * (1 - self.stop_loss_percent)
            else:
                take_profit_price = entry_price * (1 - self.take_profit_percent)
                stop_loss_price = entry_price * (1 + self.stop_loss_percent)
            
            # 构建下单参数
            order_params = build_order_params(
                inst_id=self.inst_id,
                side=side,
                entry_price=entry_price,
                size=size,
                pos_side=pos_side,
                take_profit=take_profit_price,
                stop_loss=stop_loss_price,
                prefix="VINE"
            )
            self.log(f"[DEBUG] 提交OKX下单参数: {order_params}", account_name)
            self.log(f"准备下单: {signal} {size}张 @ {entry_price}", account_name)
            
            # 执行下单
            result = trade_api.place_order(**order_params)
            self.log(f"[DEBUG] OKX下单返回: {result}", account_name)
            
            if result and result.get('code') == '0':
                order_data = result.get('data', [{}])[0]
                self.log(f"下单成功: {order_data.get('ordId')}", account_name)
                
                # 发送Bark通知
                self._send_order_notification(
                    account_name=account_name,
                    signal=signal,
                    entry_price=entry_price,
                    size=size,
                    take_profit_price=take_profit_price,
                    stop_loss_price=stop_loss_price,
                    cl_ord_id=order_params['clOrdId'],
                    order_data=order_data
                )
                
                return order_data
            else:
                error_msg = "未知错误"
                if result and 'data' in result and result['data']:
                    error_msg = result['data'][0].get('sMsg', result['data'][0].get('msg', '未知错误'))
                
                self.log(f"下单失败: {error_msg}", account_name)
                
                # 发送错误通知
                self._send_error_notification(
                    account_name=account_name,
                    signal=signal,
                    entry_price=entry_price,
                    size=size,
                    error_msg=error_msg,
                    result=result
                )
                
                return None
                
        except Exception as e:
            self.log(f"下单异常: {str(e)}", account_name)
            return None
    
    def _send_order_notification(self, account_name: str, signal: str, entry_price: float, 
                                size: float, take_profit_price: float, stop_loss_price: float, 
                                cl_ord_id: str, order_data: Dict):
        """发送下单成功通知"""
        title = "VINE-K8趋势策略信号开仓"
        
        content = f"""账户: {account_name}
交易标的: {self.inst_id}
信号类型: {'做多' if signal == 'LONG' else '做空'}
入场价格: {entry_price:.4f}
委托数量: {size:.2f}
保证金: {self.margin} USDT
止盈价格: {take_profit_price:.4f}
止损价格: {stop_loss_price:.4f}
客户订单ID: {cl_ord_id}
时间: {get_shanghai_time()}"""
        
        send_bark_notification(title, content)
    
    def _send_error_notification(self, account_name: str, signal: str, entry_price: float, 
                                size: float, error_msg: str, result: Dict):
        """发送下单失败通知"""
        title = "VINE-K8趋势策略信号开仓"
        
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
        print("[DEBUG] 进入run_strategy方法")
        if not self.enable_strategy:
            print("[DEBUG] 策略已禁用")
            self.log("策略已禁用")
            return
        if not self.accounts:
            print("[DEBUG] 未配置任何账户")
            self.log("未配置任何账户")
            return
        print(f"[DEBUG] 当前账户数量: {len(self.accounts)}")
        # 1. 获取K线数据（本地缓存+自动拉取）
        kline_data = get_kline_data_with_cache(
            inst_id=self.inst_id,
            bar=self.bar,
            min_rows=150,
            max_rows=1000,
            flag=self.accounts[0]['flag'] if self.accounts else '0'
        )
        print(f"[DEBUG] 获取到K线数量: {len(kline_data)}")
        if not kline_data:
            print("[DEBUG] 获取K线数据失败")
            self.log("获取K线数据失败")
            return
        latest_price = float(kline_data[0][4])  # 最新K线收盘价
        print(f"[DEBUG] 最新合约价格: {latest_price}")
        self.log(f"最新合约价格: {latest_price}")
        
        # 2. 进行逻辑判断
        analysis = self.analyze_kline(kline_data)
        if not analysis:
            self.log("K线分析失败")
            return
        
        # 检查趋势
        bullish_trend, bearish_trend = self.check_trend(kline_data)
        # ====== 新增：EMA详细日志 ======
        closes = [float(k[4]) for k in kline_data]
        closes.reverse()
        ema21_value = self.calculate_ema(closes, self.ema21)
        ema60_value = self.calculate_ema(closes, self.ema60)
        ema144_value = self.calculate_ema(closes, self.ema144)
        if ema21_value is not None and ema60_value is not None and ema144_value is not None:
            if ema21_value > ema60_value and ema60_value > ema144_value:
                trend_str = "多头趋势"
            elif ema21_value < ema60_value and ema60_value < ema144_value:
                trend_str = "空头趋势"
            else:
                trend_str = "震荡/无明显趋势"
            self.log(f"[DEBUG] EMA21={ema21_value:.4f}, EMA60={ema60_value:.4f}, EMA144={ema144_value:.4f}, 趋势判断: {trend_str}")
        else:
            self.log(f"[DEBUG] EMA数据不足，无法判断趋势")
        
        # 记录分析结果
        self.log(f"K0方向: {'多头' if analysis['k0_is_long'] else '空头' if analysis['k0_is_short'] else '平盘'}")
        self.log(f"K1方向: {'多头' if analysis['k1_is_long'] else '空头' if analysis['k1_is_short'] else '平盘'}")
        self.log(f"方向一致性: {'一致' if analysis['same_direction'] else '不一致'}")
        self.log(f"K0振幅: {analysis['body0']*100:.2f}%")
        self.log(f"K1~K5总振幅: {analysis['total_range']*100:.2f}%")
        self.log(f"趋势: {'多头' if bullish_trend else '空头' if bearish_trend else '震荡'}")
        
        # 判断交易信号
        long_condition = (analysis['signal'] == "LONG" and 
                         (not self.enable_trend_filter or bullish_trend))
        short_condition = (analysis['signal'] == "SHORT" and 
                          (not self.enable_trend_filter or bearish_trend))
        
        # 计算下单数量
        order_size = self.calculate_order_size(latest_price)
        self.log(f"根据最新价格 {latest_price} 计算的下单数量: {order_size} 张")
        
        # 3. 对每个账户执行操作
        for account in self.accounts:
            account_name = account['name']
            self.log(f"开始处理账户: {account_name}")
            try:
                # 初始化交易API
                trade_api = self.init_trade_api(
                    api_key=account['api_key'],
                    secret_key=account['secret_key'],
                    passphrase=account['passphrase'],
                    flag=account['flag']
                )
                # 检查并撤销已超过止盈价格的委托
                if not self.check_and_cancel_orders(trade_api, account_name, latest_price):
                    self.log(f"账户 {account_name} 撤销委托失败，跳过处理")
                    continue
                # 如果有交易信号，执行下单
                if long_condition or short_condition:
                    signal = "LONG" if long_condition else "SHORT"
                    self.place_order(trade_api, account_name, signal, analysis['entry_price'], order_size)
                else:
                    self.log(f"账户 {account_name} 无交易信号", account_name)
            except Exception as e:
                self.log(f"处理账户 {account_name} 时发生异常: {str(e)}")
                continue

def main():
    """主函数"""
    strategy = VINEK8Strategy()
    
    # 检查配置
    if not strategy.accounts:
        print("请配置OKX账户信息")
        return
    
    print(f"VINE-K8趋势策略启动")
    print(f"交易标的: {strategy.inst_id}")
    print(f"交易数量: {strategy.trade_qty}张")
    print(f"止盈: {strategy.take_profit_percent*100}%")
    print(f"止损: {strategy.stop_loss_percent*100}%")
    print(f"配置账户数量: {len(strategy.accounts)}")
    for account in strategy.accounts:
        print(f"  - {account['name']}")
    
    # 运行策略
    strategy.run_strategy()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"[FATAL] 主程序异常: {e}")
        print(traceback.format_exc()) 
