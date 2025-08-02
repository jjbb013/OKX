"""
任务名称
name: OKX Doge 布林带大振幅反向策略 QA
定时规则
cron: 1 */5 * * * *
"""

import os
import sys
import math
import numpy as np
from typing import List, Dict, Optional

# 添加utils目录
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))
from okx_utils import (
    get_shanghai_time, build_order_params, send_bark_notification
)

# 导入OKX API
import okx.Trade as Trade
import okx.MarketData as MarketData

# ---------- 配置参数 ----------
STRATEGY_PARAMS = {                  # 策略核心参数
    'leverage': 20,                  # 杠杆倍数
    'take_profit_perc': 0.03,        # 止盈比例 (3%)
    'stop_loss_perc': 0.02,          # 止损比例 (2%)
    'wick_threshold': 0.003,         # 影线阈值 (0.3%)
    'bb_length': 20,                 # 布林带周期
    'bb_mult': 2.0,                  # 布林带标准差倍数
    'order_value': 10,               # 每单保证金 (USDT)
    'pyramiding': 10                 # 最大叠加仓位
}

# ========================
# 数据管理模块 (已简化)
# ========================
def filter_completed_klines(klines: list) -> list:
    """
    过滤未完结K线。
    对于 get_mark_price_candlesticks 返回的数据，完结标记在第6位(index 5)。
    """
    # 标记价格K线数据有6个字段: [ts, o, h, l, c, confirm]
    return [kline for kline in klines if len(kline) >= 6 and kline[5] == '1']

def get_kline_data(inst_id: str, bar: str, limit: int, flag: str) -> list:
    """
    从OKX实时获取K线数据 (使用标记价格)
    :param inst_id: 交易品种 (如DOGE-USDT-SWAP)
    :param bar: K线周期 (如5m)
    :param limit: 获取数量
    :param flag: 账户类型 (0实盘/1模拟盘)
    :return: 已过滤的完结K线数据列表
    """
    result = None  # 初始化result
    try:
        print(f"[DEBUG] 准备初始化 MarketAPI, flag={flag}")
        market_api = MarketData.MarketAPI(flag=flag)
        print(f"[DEBUG] MarketAPI 初始化成功, 准备获取K线...")
        # ⚠️ 使用 get_mark_price_candlesticks 替换旧接口
        result = market_api.get_mark_price_candlesticks(instId=inst_id, bar=bar, limit=str(limit))
        print(f"[DEBUG] OKX API 原始返回: {result}") # 打印完整原始返回
    except Exception as e:
        import traceback
        print(f"[ERROR] 调用OKX API时发生异常: {e}")
        print(traceback.format_exc())
        return []

    if result and result.get('code') == '0':
        completed_klines = filter_completed_klines(result['data'])
        print(f"[DEBUG] API成功返回 {len(result['data'])} 条K线, 过滤后得到 {len(completed_klines)} 条已完结K线。")
        return completed_klines
    
    # 如果代码不是'0'或result为空
    err_msg = result.get('msg', '无有效错误信息') if result else 'API无返回'
    print(f"[ERROR] 获取K线数据失败: {err_msg}")
    return []

# ========================
# 核心策略类
# ========================
class BollingerStrategy:
    def __init__(self):
        self.inst_id = "DOGE-USDT-SWAP"  # 合约ID
        self.bar = "5m"                 # K线周期
        self.params = STRATEGY_PARAMS    # 策略参数
        self.accounts = self._get_accounts()  # 加载账户配置
        self.position_counters = {acc['name']: 0 for acc in self.accounts}  # 初始化仓位计数器
        self.last_signal_ts = 0          # 上次信号时间戳（防重）

    def _get_accounts(self) -> List[Dict]:
        """从环境变量加载OKX账户配置"""
        accounts = []
        # 账户1配置
        if name := os.environ.get("OKX1_ACCOUNT_NAME"):
            accounts.append({
                'name': name,
                'api_key': os.environ.get("OKX1_API_KEY", ""),
                'secret_key': os.environ.get("OKX1_SECRET_KEY", ""),
                'passphrase': os.environ.get("OKX1_PASSPHRASE", ""),
                'flag': os.environ.get("OKX1_FLAG", "0"),
            })
        # 账户2配置
        if name := os.environ.get("OKX2_ACCOUNT_NAME"):
            accounts.append({
                'name': name,
                'api_key': os.environ.get("OKX2_API_KEY", ""),
                'secret_key': os.environ.get("OKX2_SECRET_KEY", ""),
                'passphrase': os.environ.get("OKX2_PASSPHRASE", ""),
                'flag': os.environ.get("OKX2_FLAG", "0"),
            })
        return accounts

    def init_trade_api(self, account: Dict) -> Trade.TradeAPI:
        """初始化交易API对象"""
        # 按照官方示例，使用位置参数以保证兼容性
        # 参数顺序: api_key, secret_key, passphrase, debug, flag
        return Trade.TradeAPI(
            account['api_key'],
            account['secret_key'],
            account['passphrase'],
            False,  # debug
            account['flag']
        )

    def log(self, message: str, account_name: str = ""):
        """记录带时间戳的日志"""
        timestamp = get_shanghai_time()
        prefix = f"[{account_name}] " if account_name else ""
        print(f"[{timestamp}] {prefix}{message}")

    # ---------- 策略计算函数 ----------
    def calculate_bollinger_bands(self, closes: List[float]) -> tuple:
        """
        计算布林带上轨、中轨、下轨
        :param closes: 收盘价列表（最新数据在前）
        :return: (上轨, 中轨, 下轨)
        """
        if len(closes) < self.params['bb_length']:
            return 0.0, 0.0, 0.0
            
        # 使用向量化计算提高性能
        basis = np.mean(closes[-self.params['bb_length']:])  # 中轨(SMA)
        dev = np.std(closes[-self.params['bb_length']:]) * self.params['bb_mult']
        return basis + dev, basis, basis - dev  # (上轨, 中轨, 下轨)

    def adjust_quantity(self, raw_qty: float) -> float:
        """
        ⚠️ 数量精度调整：对齐到0.01的整数倍（DOGE合约要求）
        :param raw_qty: 原始计算数量
        :return: 调整后的合约张数 (0.01的整数倍)
        """
        min_lot = 0.01  # 最小交易单位
        adjusted = math.ceil(raw_qty / min_lot) * min_lot  # 向上取整到最近0.01
        return round(adjusted, 2)  # 保留两位小数

    def format_price(self, price: float) -> float:
        """
        ⚠️ 价格精度调整：限制到小数点后5位（OKX要求）
        :param price: 原始价格
        :return: 格式化后价格
        """
        return round(price, 5)

    def generate_signal(self, kline_data: list) -> Optional[dict]:
        """
        生成交易信号
        :param kline_data: K线数据（最新在前）
        :return: 信号字典（无信号时返回None）
        """
        if len(kline_data) < self.params['bb_length']:
            self.log(f"K线数据不足 ({len(kline_data)}/{self.params['bb_length']})，无法计算布林带")
            return None
            
        # 解析最新K线
        latest = kline_data[0]
        ts, o, h, l, c = latest[0], float(latest[1]), float(latest[2]), float(latest[3]), float(latest[4])
        
        # ⚠️ 防重复信号：同一根K线不重复触发
        current_ts = int(ts) // 1000
        if current_ts <= self.last_signal_ts:
            self.log(f"信号已在时间戳 {current_ts} 处理过，跳过")
            return None
            
        # 计算布林带
        closes = [float(k[4]) for k in kline_data]  # 提取收盘价
        upper, basis, lower = self.calculate_bollinger_bands(closes)
        
        # 计算影线与实体
        upper_wick = h - max(o, c)  # 上影线高度
        lower_wick = min(o, c) - l   # 下影线高度
        body = abs(c - o)            # K线实体高度
        
        # 信号条件判断
        short_signal = (
            upper_wick >= self.params['wick_threshold'] and  # 上影线超过阈值
            h > upper and                                  # 最高价突破上轨
            max(o, c) < upper                              # 收盘价低于上轨
        )
        long_signal = (
            lower_wick >= self.params['wick_threshold'] and  # 下影线超过阈值
            l < lower and                                  # 最低价突破下轨
            min(o, c) > lower                               # 收盘价高于下轨
        )
        
        # 只有当至少有一个信号为True时，才返回信号字典
        if short_signal or long_signal:
            self.log(f"发现信号: 做多={long_signal}, 做空={short_signal}")
            # 计算入场价（影线顶端/底端+实体）
            entry_short = max(o, c) + body
            entry_long = min(o, c) - body
            
            # 返回信号字典
            return {
                'short_signal': short_signal,
                'long_signal': long_signal,
                'entry_short': entry_short,
                'entry_long': entry_long,
                'tp_short': entry_short * (1 - self.params['take_profit_perc']),  # 空单止盈价
                'sl_short': entry_short * (1 + self.params['stop_loss_perc']),     # 空单止损价
                'tp_long': entry_long * (1 + self.params['take_profit_perc']),    # 多单止盈价
                'sl_long': entry_long * (1 - self.params['stop_loss_perc']),      # 多单止损价
                'timestamp': ts  # K线时间戳
            }

        # 如果没有任何信号，则返回None
        return None

    # ---------- 仓位计算函数 ----------
    def calculate_position_size(self, entry_price: float, account_name: str) -> float:
        """
        ⚠️ 计算合约张数（考虑合约面值）
        :param entry_price: 入场价格
        :param account_name: 账户名（用于日志）
        :return: 调整后的合约张数（0.01的整数倍）
        """
        # 计算公式：合约张数 = (保证金 × 杠杆) / (价格 × 合约面值)
        # ⚠️ DOGE-USDT-SWAP合约面值 = 10（每张合约代表10 DOGE）
        contract_face_value = 10
        raw_size = (self.params['order_value'] * self.params['leverage']) / (entry_price * contract_face_value)
        
        # 精度调整
        adjusted_size = self.adjust_quantity(raw_size)
        
        # 检查是否低于最小交易量
        if adjusted_size < 0.01:
            self.log(f"计算数量{adjusted_size}小于0.01张，跳过下单", account_name)
            return 0.0
            
        return adjusted_size

    # ---------- 交易执行函数 ----------
    def execute_trade(self, signal: dict):
        """执行交易信号"""
        self.log(f"执行交易信号: {signal}")
        if not signal or (not signal.get('short_signal') and not signal.get('long_signal')):
            self.log("信号字典无效或不包含任何交易方向，跳过执行")
            return
            
        # 更新信号时间戳（防重）
        self.last_signal_ts = int(signal['timestamp']) // 1000
        
        for account in self.accounts:  # 遍历所有账户
            acc_name = account['name']
            try:
                # 检查仓位限制
                if self.position_counters[acc_name] >= self.params['pyramiding']:
                    self.log(f"已达最大仓位数({self.params['pyramiding']})，跳过", acc_name)
                    continue
                    
                # 初始化API
                trade_api = self.init_trade_api(account)
                
                # 处理空单信号
                if signal['short_signal']:
                    # ⚠️ 关键步骤：价格格式化+仓位计算
                    entry = self.format_price(signal['entry_short'])
                    size = self.calculate_position_size(entry, acc_name)
                    if size > 0:
                        self.place_order(
                            trade_api,
                            acc_name,
                            "sell",  # 方向
                            "short", # 仓位
                            entry,
                            self.format_price(signal['tp_short']),
                            self.format_price(signal['sl_short']),
                            size,
                            account['flag']  # 传递flag
                        )
                        
                # 处理多单信号
                if signal['long_signal']:
                    entry = self.format_price(signal['entry_long'])
                    size = self.calculate_position_size(entry, acc_name)
                    if size > 0:
                        self.place_order(
                            trade_api,
                            acc_name,
                            "buy", 
                            "long",
                            entry,
                            self.format_price(signal['tp_long']),
                            self.format_price(signal['sl_long']),
                            size,
                            account['flag']  # 传递flag
                        )
            except Exception as e:
                self.log(f"账户处理异常: {str(e)}", acc_name)

    def place_order(
        self, 
        api: Trade.TradeAPI, 
        acc_name: str, 
        side: str, 
        pos_side: str, 
        entry: float, 
        tp: float, 
        sl: float,
        size: float,
        flag: str
    ):
        """
        ⚠️ 下单执行函数
        :param size: 已调整的合约张数
        :param flag: 账户模式 ('0'实盘, '1'模拟盘)
        """
        # 构建订单参数
        order_params = build_order_params(
            instId=self.inst_id,
            side=side,
            pos_side=pos_side,
            entry_price=entry,
            size=size,
            take_profit=tp,
            stop_loss=sl,
            prefix="DOGE-BB"
        )
        
        # 根据flag决定执行方式
        if flag == '0':  # 实盘模式
            result = api.place_order(**order_params)
            if result and result.get('code') == '0':
                self.position_counters[acc_name] += 1  # 更新仓位计数
                self.log(f"{side}单成功: 数量={size}张 @ {entry}", acc_name)
                self.send_notification(acc_name, side, entry, size, tp, sl)
            else:
                err = result.get('msg', '未知错误') if result else '无响应'
                self.log(f"下单失败: {err}", acc_name)
        else:  # 模拟盘模式
            self.log(f"[SIM] 忽略下单: {side} {size}张 @ {entry}", acc_name)
            self.send_notification(acc_name, side, entry, size, tp, sl) # 模拟盘也发通知

    def send_notification(self, acc_name: str, side: str, price: float, size: float, tp: float, sl: float):
        """发送Bark通知"""
        mode = "实盘" if os.getenv('TRADE_MODE') == 'real' else "模拟"
        title = f"DOGE {side.upper()}信号触发 ({mode})"
        content = f"""账户: {acc_name}
操作: {'做空' if side=='sell' else '做多'}
价格: {price:.6f}
数量: {size:.2f}张
止盈: {tp:.6f}
止损: {sl:.6f}
时间: {get_shanghai_time()}"""
        send_bark_notification(title, content)

# ========================
# 主执行流程
# ========================
def main():
    """策略主入口"""
    strategy = BollingerStrategy()
    if not strategy.accounts:
        strategy.log("未配置OKX账户，请设置环境变量")
        return

    # 增加日志，显示正在使用的账户信息
    active_account = strategy.accounts[0]
    strategy.log(f"准备为账户 {active_account.get('name', 'N/A')} 获取K线数据, flag={active_account.get('flag', 'N/A')}")
        
    # 实时获取K线数据
    klines = get_kline_data(
        inst_id=strategy.inst_id,
        bar=strategy.bar,
        limit=100,  # 获取100根K线，确保足够计算
        flag=active_account['flag']
    )
    
    if not klines:
        strategy.log("获取K线数据失败，无法继续执行")
        return
        
    # 生成并执行信号
    if signal := strategy.generate_signal(klines):
        strategy.log("生成交易信号，准备执行...")
        strategy.execute_trade(signal)
    else:
        strategy.log("未生成有效交易信号")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        err_msg = f"策略异常: {str(e)}\n{traceback.format_exc()}"
        print(err_msg)
        send_bark_notification("DOGE策略崩溃", err_msg)
