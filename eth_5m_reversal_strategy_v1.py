"""
任务名称: ETH大振幅反转 v1
定时规则
cron: 3 */5 * * * *
K线等级: 5m
止盈 1.2%，止损 2.8%，振幅 0.9%，滑点 0.01
最小下单数量：0.0001 ETH
下单金额 50 USDT，保证金 5 USDT，杠杆 10 倍
交易标的：ETH-USDT-SWAP
"""
import os
import time
from datetime import datetime, timezone, timedelta
from utils.okx_utils import (
    get_env_var, get_kline_data, get_orders_pending, cancel_pending_open_orders,
    build_order_params, generate_clord_id, send_bark_notification, init_trade_api, get_shanghai_time
)
from utils.notification_service import NotificationService

# ========== 策略参数 ==========
INST_ID = "ETH-USDT-SWAP"
BAR = "5m"
LIMIT = 2
LEVERAGE = 10
MARGIN = 10  # 保证金(USDT)
ORDER_USDT = 50  # 下单金额(USDT)
CONTRACT_FACE_VALUE = 0.01  # 合约面值
TAKE_PROFIT_PERC = 1.2  # 止盈百分比
STOP_LOSS_PERC = 2.8  # 止损百分比
AMPLITUDE_PERC = 0.9  # 振幅阈值
SLIPPAGE = 0.01  # 滑点
MIN_QTY = 0.01  # 最小下单数量
ACCOUNT_SUFFIXES = ["", "1"]  # 支持多账户

notification_service = NotificationService()

# ========== 测试用假K线数据 ==========
TEST_MODE = False  # 测试时为True，实盘请设为False
FAKE_KLINE_LONG = [
    ["1709999990000", "2650", "2660", "2645", "2650", "100", "100", "100", "1"],   # new
    ["1710000000000", "2650", "2680", "2640", "2654", "100", "100", "100", "1"],  # pre

]

def calc_qty(entry_price):
    # 动态计算下单数量（保证金*杠杆/合约面值/价格），再乘以10，保留2位小数
    trade_value = MARGIN * LEVERAGE
    raw_qty = trade_value / entry_price
    qty = round(raw_qty * 10, 2)
    return qty


def main():
    # 统一获取K线数据
    api_key = get_env_var("OKX_API_KEY", "", None)
    secret_key = get_env_var("OKX_SECRET_KEY", "", None)
    passphrase = get_env_var("OKX_PASSPHRASE", "", None)
    flag = get_env_var("OKX_FLAG", "", "0")
    if TEST_MODE:
        kline_data = FAKE_KLINE_LONG
        print(f"[{get_shanghai_time()}] [INFO] 使用假K线数据进行测试: {kline_data}")
    else:
        kline_data = get_kline_data(api_key, secret_key, passphrase, INST_ID, BAR, limit=LIMIT, flag=flag)
    if not kline_data or len(kline_data) < 2:
        print(f"[{get_shanghai_time()}] [ERROR] 未获取到足够K线数据，跳过全部账号")
        return
    k = kline_data[1]
    open_, high, low, close = float(k[1]), float(k[2]), float(k[3]), float(k[4])
    range_perc = (high - low) / low * 100
    is_green = close > open_
    is_red = close < open_
    # 信号判定
    entry_price = None
    direction = None
    pos_side = None
    side = None
    tp = None
    sl = None
    if range_perc > AMPLITUDE_PERC:
        if is_green:
            entry_price = (close + high) / 2
            order_price = entry_price - SLIPPAGE
            direction = "做空"
            pos_side = "short"
            side = "sell"
            tp = entry_price * (1 - TAKE_PROFIT_PERC / 100)
            sl = entry_price * (1 + STOP_LOSS_PERC / 100)
        elif is_red:
            entry_price = (close + low) / 2
            order_price = entry_price + SLIPPAGE
            direction = "做多"
            pos_side = "long"
            side = "buy"
            tp = entry_price * (1 + TAKE_PROFIT_PERC / 100)
            sl = entry_price * (1 - STOP_LOSS_PERC / 100)
    # 再循环账号，做账户相关操作
    for suffix in ACCOUNT_SUFFIXES:
        account_name = get_env_var("OKX_ACCOUNT_NAME", suffix, f"账号{suffix}" if suffix else "默认账号")
        api_key = get_env_var("OKX_API_KEY", suffix)
        secret_key = get_env_var("OKX_SECRET_KEY", suffix)
        passphrase = get_env_var("OKX_PASSPHRASE", suffix)
        flag = get_env_var("OKX_FLAG", suffix, "0")
        if not all([api_key, secret_key, passphrase]):
            print(f"[{get_shanghai_time()}] [ERROR] 账号信息不完整: {account_name}")
            continue
        try:
            trade_api = init_trade_api(api_key, secret_key, passphrase, flag, suffix)
        except Exception as e:
            print(f"[{get_shanghai_time()}] [ERROR] API初始化失败: {account_name} {e}")
            continue
        # 检查未成交委托
        orders = get_orders_pending(trade_api, INST_ID)
        need_skip = False
        if orders:
            for order in orders:
                side_ = order.get('side')
                pos_side_ = order.get('posSide')
                price = float(order.get('px'))
                attach_algo = order.get('attachAlgoOrds', [])
                tp_price = None
                for algo in attach_algo:
                    if 'tpTriggerPx' in algo:
                        tp_price = float(algo['tpTriggerPx'])
                if side_ == 'buy' and pos_side_ == 'long' and tp_price:
                    if close >= tp_price:
                        print(f"[{get_shanghai_time()}] [INFO] 多单委托止盈已到，撤销委托: {order['ordId']}")
                        cancel_pending_open_orders(trade_api, INST_ID, order_ids=order['ordId'])
                        need_skip = True
                if side_ == 'sell' and pos_side_ == 'short' and tp_price:
                    if close <= tp_price:
                        print(f"[{get_shanghai_time()}] [INFO] 空单委托止盈已到，撤销委托: {order['ordId']}")
                        cancel_pending_open_orders(trade_api, INST_ID, order_ids=order['ordId'])
                        need_skip = True
            # 撤单后不再 continue，直接进入下单逻辑
        if orders and not need_skip:
            print(f"[{get_shanghai_time()}] [INFO] 存在未成交委托，跳过本轮: {account_name}")
            continue
        # 下单逻辑
        if entry_price and direction and tp is not None and sl is not None and order_price is not None:
            qty = calc_qty(entry_price)
            print(f"[{get_shanghai_time()}] [INFO] {account_name} 本次计算下单数量: {qty:.2f}")
            if qty < MIN_QTY:
                print(f"[{get_shanghai_time()}] [INFO] 下单数量过小(<{MIN_QTY})，跳过: {account_name}")
                continue
            order_params = build_order_params(
                inst_id=INST_ID,
                side=side,
                entry_price=round(order_price, 4),
                size=qty,
                pos_side=pos_side,
                take_profit=round(tp, 4),
                stop_loss=round(sl, 4),
                prefix="ETHv1"
            )
            print(f"[{get_shanghai_time()}] [INFO] {account_name} 下单参数: {order_params}")
            try:
                order_result = trade_api.place_order(**order_params)
                print(f"[{get_shanghai_time()}] [INFO] {account_name} 下单结果: {order_result}")
            except Exception as e:
                order_result = {"error": str(e)}
                print(f"[{get_shanghai_time()}] [ERROR] {account_name} 下单异常: {e}")
            # Bark 通知
            cl_ord_id = order_params.get('clOrdId', '')
            sh_time = get_shanghai_time()
            title = "ETH 大振幅反转 v1 信号开仓"
            sMsg = ''
            if isinstance(order_result, dict):
                if 'data' in order_result and isinstance(order_result['data'], list) and order_result['data']:
                    sMsg = order_result['data'][0].get('sMsg', '')
                if not sMsg:
                    sMsg = order_result.get('sMsg', '')
            msg = order_result.get('msg', '') if isinstance(order_result, dict) else ''
            code = order_result.get('code', '') if isinstance(order_result, dict) else ''
            bark_content = (
                f"账号: {account_name}\n"
                f"交易标的: {INST_ID}\n"
                f"信号类型: {direction}\n"
                f"入场价格: {entry_price:.4f}\n"
                f"委托数量: {qty:.2f}\n"
                f"保证金: {MARGIN} USDT\n"
                f"止盈价格: {tp:.4f}\n"
                f"止损价格: {sl:.4f}\n"
                f"客户订单ID: {cl_ord_id}\n"
                f"时间: {sh_time}\n"
            )
            if not (order_result and order_result.get('code', '1') == '0'):
                bark_content += f"\n⚠️ 下单失败 ⚠️\n错误: {sMsg}\n"
            bark_content += f"服务器响应代码: {code}\n服务器响应消息: {msg}"
            notification_service.send_bark_notification(title, bark_content, group="OKX自动交易")
        else:
            qty = calc_qty(close) if close else 0
            print(f"[{get_shanghai_time()}] [INFO] {account_name} 当前无信号，理论下单数量: {qty:.2f}")

if __name__ == "__main__":
    main() 
