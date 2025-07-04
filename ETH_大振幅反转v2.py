"""
任务名称: ETH大振幅反转 v2
定时规则
cron: 3 */5 * * * *
K线等级: 5m
止盈 1.4%，止损 0.9%，振幅 1.7%，滑点 0.01
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
MARGIN = 5  # 保证金(USDT)
ORDER_USDT = 50  # 下单金额(USDT)
CONTRACT_FACE_VALUE = 0.01  # 合约面值
TAKE_PROFIT_PERC = 1.4  # 止盈百分比
STOP_LOSS_PERC = 0.9  # 止损百分比
AMPLITUDE_PERC = 1.7  # 振幅阈值
SLIPPAGE = 0.01  # 滑点
MIN_QTY = 0.01  # 最小下单数量
ACCOUNT_SUFFIXES = ["", "1"]  # 支持多账户

notification_service = NotificationService()

# ========== 测试用假K线数据 ==========
TEST_MODE = False  # 测试时为True，实盘请设为False
FAKE_KLINE_LONG = [
    ["1709999990000", "2650", "2660", "2645", "2650", "100", "100", "100", "1"],   # new
    ["1710000000000", "2650", "2700", "2640", "2654", "100", "100", "100", "1"]  # pre

]

def calc_qty(entry_price):
    # 动态计算下单数量（保证金*杠杆/合约面值/价格），再乘以10，保留2位小数
    trade_value = MARGIN * LEVERAGE
    raw_qty = trade_value / entry_price
    qty = round(raw_qty * 10, 2)
    return qty

def main():
    for suffix in ACCOUNT_SUFFIXES:
        account_name = get_env_var("OKX_ACCOUNT_NAME", suffix, f"账户{suffix}" if suffix else "默认账户")
        api_key = get_env_var("OKX_API_KEY", suffix)
        secret_key = get_env_var("OKX_SECRET_KEY", suffix)
        passphrase = get_env_var("OKX_PASSPHRASE", suffix)
        flag = get_env_var("OKX_FLAG", suffix, "0")
        if not all([api_key, secret_key, passphrase]):
            print(f"[{get_shanghai_time()}] [ERROR] 账户信息不完整: {account_name}")
            continue
        try:
            trade_api = init_trade_api(api_key, secret_key, passphrase, flag, suffix)
        except Exception as e:
            print(f"[{get_shanghai_time()}] [ERROR] API初始化失败: {account_name} {e}")
            continue
        # 1. 获取K线
        if TEST_MODE:
            kline_data = FAKE_KLINE_LONG
            print(f"[{get_shanghai_time()}] [INFO] 使用假K线数据进行测试: {kline_data}")
        else:
            kline_data = get_kline_data(api_key, secret_key, passphrase, INST_ID, BAR, limit=LIMIT, flag=flag, suffix=suffix)
        if not kline_data or len(kline_data) < 2:
            print(f"[{get_shanghai_time()}] [ERROR] 未获取到足够K线数据: {account_name}")
            continue
        # 只用第二根K线做信号判断
        k = kline_data[1]
        open_, high, low, close = float(k[1]), float(k[2]), float(k[3]), float(k[4])
        range_perc = (high - low) / low * 100
        is_green = close > open_
        is_red = close < open_
        print(f"[{get_shanghai_time()}] [INFO] {account_name} 用于判断的K线: open={open_}, close={close}, high={high}, low={low}, 振幅={range_perc:.2f}%")
        # 2. 检查未成交委托
        orders = get_orders_pending(trade_api, INST_ID)
        need_skip = False
        if orders:
            for order in orders:
                side = order.get('side')
                pos_side = order.get('posSide')
                price = float(order.get('px'))
                attach_algo = order.get('attachAlgoOrds', [])
                tp_price = None
                for algo in attach_algo:
                    if 'tpTriggerPx' in algo:
                        tp_price = float(algo['tpTriggerPx'])
                if side == 'buy' and pos_side == 'long' and tp_price:
                    if close >= tp_price:
                        print(f"[{get_shanghai_time()}] [INFO] 多单委托止盈已到，撤销委托: {order['ordId']}")
                        cancel_pending_open_orders(trade_api, INST_ID, order_ids=order['ordId'])
                        need_skip = True
                if side == 'sell' and pos_side == 'short' and tp_price:
                    if close <= tp_price:
                        print(f"[{get_shanghai_time()}] [INFO] 空单委托止盈已到，撤销委托: {order['ordId']}")
                        cancel_pending_open_orders(trade_api, INST_ID, order_ids=order['ordId'])
                        need_skip = True
            if need_skip:
                print(f"[{get_shanghai_time()}] [INFO] 撤单后跳过本轮开仓: {account_name}")
                continue
        if orders:
            print(f"[{get_shanghai_time()}] [INFO] 存在未成交委托，跳过本轮: {account_name}")
            continue
        # 3. 检查K线形态，准备开仓
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
            else:
                print(f"[{get_shanghai_time()}] [INFO] K线无方向，不开仓: {account_name}")
                continue
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
                prefix="ETHv2"
            )
            print(f"[{get_shanghai_time()}] [INFO] {account_name} 下单参数: {order_params}")
            try:
                order_result = trade_api.place_order(**order_params)
                print(f"[{get_shanghai_time()}] [INFO] {account_name} 下单结果: {order_result}")
            except Exception as e:
                order_result = {"error": str(e)}
                print(f"[{get_shanghai_time()}] [ERROR] {account_name} 下单异常: {e}")
            # 组装Bark通知内容
            cl_ord_id = order_params.get('clOrdId', '')
            sh_time = get_shanghai_time()
            title = "ETH 大振幅反转 v2 信号开仓"
            # 错误信息优先取data[0]['sMsg']，其次取sMsg字段
            sMsg = ''
            if isinstance(order_result, dict):
                if 'data' in order_result and isinstance(order_result['data'], list) and order_result['data']:
                    sMsg = order_result['data'][0].get('sMsg', '')
                if not sMsg:
                    sMsg = order_result.get('sMsg', '')
            msg = order_result.get('msg', '') if isinstance(order_result, dict) else ''
            code = order_result.get('code', '') if isinstance(order_result, dict) else ''
            bark_content = (
                f"账户: {account_name}\n"
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
            qty = calc_qty(close)
            print(f"[{get_shanghai_time()}] [INFO] {account_name} 当前无信号，理论下单数量: {qty:.2f}")

if __name__ == "__main__":
    main() 