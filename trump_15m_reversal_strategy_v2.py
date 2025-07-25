"""
任务名称
name: OKX TRUMP 大振幅反转策略V2
定时规则
cron: 3 */15 * * * *
"""
import os
import json
from utils import okx_utils

def main():
    # 策略参数
    TAKE_PROFIT_PERC = 0.048
    STOP_LOSS_PERC = 0.027
    AMPLITUDE_PERC = 6.0
    SLIPPAGE = 0.16
    MARGIN = 5
    LEVERAGE = 10
    CONTRACT_FACE_VALUE = 0.1
    INST_ID = "TRUMP-USDT-SWAP"
    BAR = "15m"
    ACCOUNT_SUFFIXES = ["", "1"]  # 可扩展多账户

    # 统一获取K线数据
    api_key = okx_utils.get_env_var("OKX_API_KEY", "", None)
    secret_key = okx_utils.get_env_var("OKX_SECRET_KEY", "", None)
    passphrase = okx_utils.get_env_var("OKX_PASSPHRASE", "", None)
    kline = okx_utils.get_kline_data(api_key, secret_key, passphrase, INST_ID, BAR, limit=2)
    if not kline or len(kline) < 2:
        print(f"[{okx_utils.get_shanghai_time()}] [ERROR] 获取K线失败，跳过全部账号")
        return
    prev = kline[1]
    prev_close = float(prev[4])
    prev_high = float(prev[2])
    prev_low = float(prev[3])
    prev_open = float(prev[1])
    range_perc = (prev_high - prev_low) / prev_low * 100
    is_green = prev_close > prev_open
    is_red = prev_close < prev_open
    entry_price = None
    signal = None
    if range_perc > AMPLITUDE_PERC:
        if is_green:
            signal = 'SHORT'
            entry_price = round((prev_close + prev_high) / 2, 3)
        elif is_red:
            signal = 'LONG'
            entry_price = round((prev_close + prev_low) / 2, 3)
    # 再循环账号，做账户相关操作
    for suffix in ACCOUNT_SUFFIXES:
        account_name = okx_utils.get_env_var("OKX_ACCOUNT_NAME", suffix, f"账号{suffix or '默认'}")
        api_key = okx_utils.get_env_var("OKX_API_KEY", suffix)
        secret_key = okx_utils.get_env_var("OKX_SECRET_KEY", suffix)
        passphrase = okx_utils.get_env_var("OKX_PASSPHRASE", suffix)
        if not all([api_key, secret_key, passphrase]):
            print(f"[{okx_utils.get_shanghai_time()}] [ERROR] 账号{suffix or '默认'} API信息不完整，跳过")
            continue
        trade_api = okx_utils.init_trade_api(api_key, secret_key, passphrase, suffix=suffix)
        # 检查未成交委托
        pending_orders = okx_utils.get_orders_pending(trade_api, INST_ID, account_prefix=account_name)
        order_canceled = False
        for order in pending_orders:
            side = order.get('side')
            pos_side = order.get('posSide')
            order_price = float(order.get('px', 0))
            tp = None
            attach_algo_ords = order.get('attachAlgoOrds', [])
            if attach_algo_ords and isinstance(attach_algo_ords, list) and len(attach_algo_ords) > 0 and 'tpTriggerPx' in attach_algo_ords[0]:
                tp = float(attach_algo_ords[0]['tpTriggerPx'])
            if not tp:
                linked_algo = order.get('linkedAlgoOrd', {})
                if linked_algo and 'tpTriggerPx' in linked_algo:
                    tp = float(linked_algo['tpTriggerPx'])
            if not tp:
                print(f"[{okx_utils.get_shanghai_time()}] [{account_name}] 委托{order.get('ordId')}无止盈价，跳过")
                continue
            if (side == 'buy' and pos_side == 'long' and prev_close > tp) or (side == 'sell' and pos_side == 'short' and prev_close < tp):
                print(f"[{okx_utils.get_shanghai_time()}] [{account_name}] 委托{order.get('ordId')}触发止盈，撤单")
                okx_utils.cancel_pending_open_orders(trade_api, INST_ID, order_ids=order['ordId'], account_prefix=account_name)
                order_canceled = True
        if order_canceled:
            print(f"[{okx_utils.get_shanghai_time()}] [{account_name}] 撤单后继续判断信号")
        elif pending_orders:
            print(f"[{okx_utils.get_shanghai_time()}] [{account_name}] 有未成交委托，无需开新仓，当前委托数: {len(pending_orders)}")
            continue
        # 下单逻辑
        if signal and entry_price:
            trade_value = MARGIN * LEVERAGE
            raw_qty = trade_value / entry_price / CONTRACT_FACE_VALUE
            qty = int(raw_qty)
            if qty < 1:
                print(f"[{okx_utils.get_shanghai_time()}] [{account_name}] 计算下单数量过小，跳过")
                continue
            if signal == 'LONG':
                order_px = round(entry_price + SLIPPAGE, 3)
                tp_price = round(entry_price * (1 + TAKE_PROFIT_PERC), 3)
                sl_price = round(entry_price * (1 - STOP_LOSS_PERC), 3)
                side, pos_side = 'buy', 'long'
            else:
                order_px = round(entry_price - SLIPPAGE, 3)
                tp_price = round(entry_price * (1 - TAKE_PROFIT_PERC), 3)
                sl_price = round(entry_price * (1 + STOP_LOSS_PERC), 3)
                side, pos_side = 'sell', 'short'
            order_params = okx_utils.build_order_params(
                INST_ID, side, order_px, qty, pos_side, tp_price, sl_price, prefix="TRUMP"
            )
            print(f"[{okx_utils.get_shanghai_time()}] [{account_name}] 下单参数: {json.dumps(order_params, ensure_ascii=False)}")
            try:
                result = trade_api.place_order(**order_params)
                print(f"[{okx_utils.get_shanghai_time()}] [{account_name}] 下单结果: {json.dumps(result, ensure_ascii=False)}")
                okx_utils.send_bark_notification(
                    f"{account_name} TRUMP-15m反转V2开仓", 
                    f"时间: {okx_utils.get_shanghai_time()}\n合约: {INST_ID}\n数量: {qty}\n价格: {order_px}\n止盈: {tp_price}\n止损: {sl_price}\n方向: {signal}\n结果: {result.get('msg', '无')}",
                    group="OKX自动交易"
                )
            except Exception as e:
                print(f"[{okx_utils.get_shanghai_time()}] [{account_name}] 下单异常: {e}")
        else:
            trade_value = MARGIN * LEVERAGE
            raw_qty = trade_value / prev_close / CONTRACT_FACE_VALUE
            qty = int(raw_qty)
            print(f"[{okx_utils.get_shanghai_time()}] [{account_name}] 无开仓信号，本周期应下单数量: {qty}")

if __name__ == "__main__":
    main() 