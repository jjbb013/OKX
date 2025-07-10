"""
任务名称
name: OKX VINE K7趋势策略
定时规则
cron: 3 */5 * * * *
"""

from utils.okx_utils import (
    get_env_var, get_trade_api, get_kline_data,
    get_orders_pending, cancel_pending_open_orders,
    build_order_params, send_bark_notification, get_shanghai_time
)
import os
import json

# ============== 可配置参数区域 ==============
INST_ID = "VINE-USDT-SWAP"
BAR = "5m"
LIMIT = 7  # 获取7根K线
LEVERAGE = 10
MARGIN = 10  # 保证金(USDT)
CONTRACT_FACE_VALUE = 10  # 合约系数
ACCOUNT_SUFFIXES = ["", "1"]
TAKE_PROFIT_PERCENT = 0.016  # 止盈1.6%
STOP_LOSS_PERCENT = 0.02     # 止损2%
MIN_BODY1 = 0.01  # K2最小实体振幅(1%)
MAX_BODY1 = 0.04  # K2最大实体振幅(4%)
MAX_TOTAL_RANGE = 0.02  # K3~K6总单向振幅上限(2%)
LOG_FILE = "logs/vine_k1k2_signals.log"


def analyze_kline(kline_list):
    """
    分析K线，判断是否产生交易信号。
    kline_list: 最新在前，K1=0, K2=1, ..., K7=6
    返回: (信号, 入场价, 分析详情字典)
    """
    print(f"[DEBUG] 开始分析K线数据，共{len(kline_list)}根")
    if len(kline_list) < 7:
        print("[WARN] K线数量不足7根，无法分析")
        return None, None, None
    o2 = float(kline_list[1][1])
    c2 = float(kline_list[1][4])
    body2 = abs(c2 - o2) / o2
    is_long = c2 > o2
    is_short = c2 < o2
    total_range = 0.0
    for i in range(2, 6):
        oi = float(kline_list[i][1])
        ci = float(kline_list[i][4])
        rng = abs(ci - oi) / oi
        total_range += rng
    can_entry = (body2 > MIN_BODY1) and (body2 < MAX_BODY1) and (total_range < MAX_TOTAL_RANGE)
    entry_price = c2
    signal = None
    if can_entry:
        if is_long:
            signal = "LONG"
        elif is_short:
            signal = "SHORT"
    return signal, entry_price, {
        "body2": body2,
        "total_range": total_range,
        "is_long": is_long,
        "is_short": is_short,
        "can_entry": can_entry
    }


def process_account_trading(suffix, signal, entry_price, amp_info):
    account_name = get_env_var("OKX_ACCOUNT_NAME", suffix, default="未命名账户")
    account_prefix = f"[ACCOUNT-{account_name}]"
    # 获取TradeAPI
    api_key = get_env_var("OKX_API_KEY", suffix)
    secret_key = get_env_var("OKX_SECRET_KEY", suffix)
    passphrase = get_env_var("OKX_PASSPHRASE", suffix)
    flag = get_env_var("OKX_FLAG", suffix, "0")
    if not all([api_key, secret_key, passphrase]):
        print(f"[{get_shanghai_time()}] {account_prefix} [ERROR] 账户信息不完整或未配置")
        return
    trade_api = get_trade_api()
    # 撤销未成交订单
    cancel_pending_open_orders(trade_api, INST_ID)
    # 动态计算下单数量
    trade_value = MARGIN * LEVERAGE
    raw_qty = trade_value / (entry_price * CONTRACT_FACE_VALUE)
    qty = int((raw_qty + 9) // 10 * 10)
    if qty == 0:
        send_bark_notification(f"{account_prefix} 交易失败", f"计算数量为0，放弃交易\n入场价格: {entry_price:.4f}\n保证金: {MARGIN} USDT\n杠杆: {LEVERAGE}倍")
        return
    # 止盈止损
    if signal == "LONG":
        tp = round(entry_price * (1 + TAKE_PROFIT_PERCENT), 5)
        sl = round(entry_price * (1 - STOP_LOSS_PERCENT), 5)
        side, pos_side = "buy", "long"
    else:
        tp = round(entry_price * (1 - TAKE_PROFIT_PERCENT), 5)
        sl = round(entry_price * (1 + STOP_LOSS_PERCENT), 5)
        side, pos_side = "sell", "short"
    order_params = build_order_params(INST_ID, side, entry_price, qty, pos_side, tp, sl, prefix="VINE")
    # 下单
    order_result = None
    for attempt in range(1):
        try:
            order_result = trade_api.place_order(**order_params)
            break
        except Exception as e:
            print(f"[{get_shanghai_time()}] {account_prefix} [ORDER] 下单异常 (尝试 {attempt+1}/3): {str(e)}")
    # 日志
    os.makedirs("logs", exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "time": get_shanghai_time(),
            "account": account_name,
            "signal": signal,
            "entry_price": entry_price,
            "qty": qty,
            "order_params": order_params,
            "amp_info": amp_info,
            "order_result": order_result
        }, ensure_ascii=False) + "\n")
    # 通知
    send_bark_notification(
        f"{account_prefix} VINE K7趋势策略开仓",
        f"信号: {signal}\n账户: {account_name}\n入场价: {entry_price}\n数量: {qty}\n止盈: {tp}\n止损: {sl}\n参数: {json.dumps(order_params, ensure_ascii=False)}\n结果: {json.dumps(order_result, ensure_ascii=False)}"
    )


def main():
    print(f"[{get_shanghai_time()}] [INFO] 开始VINE K7 趋势策略 多账号模式")
    suffix = ACCOUNT_SUFFIXES[0] if ACCOUNT_SUFFIXES else ""
    api_key = get_env_var("OKX_API_KEY", suffix)
    secret_key = get_env_var("OKX_SECRET_KEY", suffix)
    passphrase = get_env_var("OKX_PASSPHRASE", suffix)
    flag = get_env_var("OKX_FLAG", suffix, "0")
    kline_data = get_kline_data(api_key, secret_key, passphrase, INST_ID, BAR, limit=LIMIT, flag=flag)
    if not kline_data or len(kline_data) < 7:
        print(f"[{get_shanghai_time()}] [ERROR] 获取K线数据失败或数据不足")
        return
    signal, entry_price, amp_info = analyze_kline(kline_data)
    if not signal:
        print(f"[{get_shanghai_time()}] [INFO] 未检测到交易信号")
        # 新增：无信号时也计算下单数量并写日志
        entry_price = float(kline_data[1][4])  # K2收盘价
        for suffix in ACCOUNT_SUFFIXES:
            account_name = get_env_var("OKX_ACCOUNT_NAME", suffix, default="未命名账户")
            account_prefix = f"[ACCOUNT-{account_name}]"
            trade_value = MARGIN * LEVERAGE
            raw_qty = trade_value / (entry_price * CONTRACT_FACE_VALUE)
            qty = int((raw_qty + 9) // 10 * 10)
            print(f"[{get_shanghai_time()}] [INFO] 无信号时，{account_prefix} 计算下单数量: {qty}")
            os.makedirs("logs", exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "time": get_shanghai_time(),
                    "account": account_name,
                    "signal": "NO_SIGNAL",
                    "entry_price": entry_price,
                    "qty": qty,
                    "note": "无信号时的下单数量估算"
                }, ensure_ascii=False) + "\n")
        return
    print(f"[{get_shanghai_time()}] [INFO] 检测到信号: {signal}, 开始处理所有账户交易")
    for suffix in ACCOUNT_SUFFIXES:
        process_account_trading(suffix, signal, entry_price, amp_info)
    print(f"[{get_shanghai_time()}] [INFO] 所有账户交易处理完成")

if __name__ == "__main__":
    main() 
