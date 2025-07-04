"""
任务名称
name: OKX VINE 大振幅反转策略
定时规则
cron: 1 */5 * * * *
"""
import os
IS_DEVELOPMENT = False
if IS_DEVELOPMENT:
    import utils.okx_utils  # 触发自动加载 env_dev

import logging
from utils.okx_utils import (
    get_shanghai_time, get_kline_data,
    get_trade_api, get_orders_pending, cancel_pending_open_orders,
    build_order_params, send_bark_notification, get_env_var
)


# ========== 参数设置 ==========
TAKE_PROFIT_PERC = 5.5   # 止盈百分比
STOP_LOSS_PERC = 1.7     # 止损百分比
ORDER_EXPIRE_HOURS = 1   # 订单有效期（小时）
RANGE_THRESHOLD = 4.2   # 振幅阈值（%）
SLIPPAGE_PERC = 0.5      # 滑点百分比
SYMBOL = "VINE-USDT-SWAP"
QTY_USDT = 10           # 名义下单金额
KLINE_INTERVAL = "5m"
FAKE_KLINE = False  # 测试开关，True 时用假K线数据
CONTRACT_FACE_VALUE = 1  # ETH-USDT-SWAP每张合约面值
ACCOUNT_SUFFIXES = ["", "1"]  # 多账号支持，空字符串为主账号

logger = logging.getLogger("VINE-5m-大振幅反转开仓策略")
logging.basicConfig(level=logging.INFO, format='[%(asctime)s][%(levelname)s] %(message)s')

def process_account_trading(suffix, kline_data):
    account_name = get_env_var("OKX_ACCOUNT_NAME", suffix, default="未命名账户")
    account_prefix = f"[ACCOUNT-{account_name}]"
    API_KEY = get_env_var("OKX_API_KEY", suffix)
    SECRET_KEY = get_env_var("OKX_SECRET_KEY", suffix)
    PASSPHRASE = get_env_var("OKX_PASSPHRASE", suffix)
    FLAG = get_env_var("OKX_FLAG", suffix, default="0")
    if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
        logger.error(f"[{get_shanghai_time()}]{account_prefix} 账户信息不完整或未配置")
        return
    try:
        trade_api = get_trade_api()
        logger.info(f"[{get_shanghai_time()}]{account_prefix} TradeAPI初始化成功: {trade_api}")
    except Exception as e:
        logger.error(f"[{get_shanghai_time()}]{account_prefix} TradeAPI初始化失败: {e}")
        return
    k = kline_data[0]
    open_, high, low, close = float(k[1]), float(k[2]), float(k[3]), float(k[4])
    logger.info(f"[{get_shanghai_time()}]{account_prefix} 最新K线: open={open_}, close={close}, high={high}, low={low}")
    # 检查账户委托
    orders = get_orders_pending(trade_api, SYMBOL)
    need_skip = False
    if orders:
        for order in orders:
            side = order.get('side')
            pos_side = order.get('posSide')
            price = float(order.get('px'))
            if side == 'buy' and pos_side == 'long':
                tp_price = price * (1 + TAKE_PROFIT_PERC / 100)
                if close > tp_price:
                    logger.info(f"[{get_shanghai_time()}]{account_prefix} 多头委托已到达止盈价，撤销: {order}")
                    try:
                        cancel_result = cancel_pending_open_orders(trade_api, SYMBOL, order_ids=order.get('ordId'))
                        logger.info(f"[{get_shanghai_time()}]{account_prefix} 撤销多头委托响应: {cancel_result}")
                        if not cancel_result:
                            need_skip = True
                    except Exception as e:
                        logger.error(f"[{get_shanghai_time()}]{account_prefix} 撤销多头委托异常: {e}")
                        need_skip = True
            elif side == 'sell' and pos_side == 'short':
                tp_price = price * (1 - TAKE_PROFIT_PERC / 100)
                if close < tp_price:
                    logger.info(f"[{get_shanghai_time()}]{account_prefix} 空头委托已到达止盈价，撤销: {order}")
                    try:
                        cancel_result = cancel_pending_open_orders(trade_api, SYMBOL, order_ids=order.get('ordId'))
                        logger.info(f"[{get_shanghai_time()}]{account_prefix} 撤销空头委托响应: {cancel_result}")
                        if not cancel_result:
                            need_skip = True
                    except Exception as e:
                        logger.error(f"[{get_shanghai_time()}]{account_prefix} 撤销空头委托异常: {e}")
                        need_skip = True
        if need_skip:
            logger.info(f"[{get_shanghai_time()}]{account_prefix} 存在未完成委托且撤销失败，跳过本轮开仓")
            return
    # 检查K线形态，准备开仓
    range = (high - low) / low * 100
    in_range = range > RANGE_THRESHOLD
    is_green = close > open_
    is_red = close < open_
    logger.info(f"[{get_shanghai_time()}]{account_prefix} 振幅={range:.2f}%, in_range={in_range}, is_green={is_green}, is_red={is_red}")
    if in_range:
        order_price = None
        direction = None
        pos_side = None
        side = None
        if is_green:
            calculated_entry = (close + high) / 2
            order_price = calculated_entry * (1 - SLIPPAGE_PERC / 100)
            direction = "做空"
            pos_side = "short"
            side = "sell"
        elif is_red:
            calculated_entry = (close + low) / 2
            order_price = calculated_entry * (1 + SLIPPAGE_PERC / 100)
            direction = "做多"
            pos_side = "long"
            side = "buy"
        else:
            logger.info(f"[{get_shanghai_time()}]{account_prefix} K线无方向，不开仓")
            return
        qty = int(QTY_USDT / order_price / CONTRACT_FACE_VALUE)
        qty = int(-(-qty // 10) * 10) if qty % 10 != 0 else qty
        if qty < 1:
            logger.info(f"[{get_shanghai_time()}]{account_prefix} 下单数量过小，跳过本次开仓")
            return
        tp = order_price * (1 - TAKE_PROFIT_PERC / 100) if direction == '做空' else order_price * (1 + TAKE_PROFIT_PERC / 100)
        sl = order_price * (1 + STOP_LOSS_PERC / 100) if direction == '做空' else order_price * (1 - STOP_LOSS_PERC / 100)
        logger.info(f"[{get_shanghai_time()}]{account_prefix} 准备开仓: 方向={direction}, 价格={order_price:.4f}, 数量={qty}, 止盈={tp:.4f}, 止损={sl:.4f}")
        order_params = build_order_params(
            SYMBOL, side, order_price, qty, pos_side, tp, sl
        )
        try:
            resp = trade_api.place_order(**order_params)
        except Exception as e:
            resp = {"error": str(e)}
        sh_time = get_shanghai_time()
        strategy_name = "VINE-5m-大振幅反转策略"
        is_success = False
        resp_json = resp if isinstance(resp, dict) else {"resp": str(resp)}
        if isinstance(resp, dict) and str(resp.get("code")) == "0":
            is_success = True
        bark_title = f"{strategy_name} 开仓"
        bark_content = (
            f"策略: {strategy_name}\n"
            f"账户: {account_name}\n"
            f"时间: {sh_time}\n"
            f"合约: {SYMBOL}\n"
            f"方向: {direction}\n"
            f"数量: {qty}\n"
            f"开仓价: {order_price:.4f}\n"
            f"止盈: {tp:.4f}\n"
            f"止损: {sl:.4f}\n"
            f"下单结果: {'成功' if is_success else '失败'}\n"
            f"服务器响应: {resp_json}"
        )
        send_bark_notification(bark_title, bark_content)
        logger.info(f"[{get_shanghai_time()}]{account_prefix} 下单响应: {resp}")
    else:
        logger.info(f"[{get_shanghai_time()}]{account_prefix} K线不满足大振幅反转条件，不开仓")
        order_price = close
        qty = int(QTY_USDT / order_price / CONTRACT_FACE_VALUE)
        qty = int(-(-qty // 10) * 10) if qty % 10 != 0 else qty
        log_path = "logs/vine_k1k2_signals.log"
        os.makedirs("logs", exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            import json
            f.write(json.dumps({
                "time": get_shanghai_time(),
                "account": account_name,
                "signal": "NO_SIGNAL",
                "entry_price": order_price,
                "qty": qty,
                "note": "无信号时的下单数量估算"
            }, ensure_ascii=False) + "\n")
        print(f"[无信号下单数量估算] 时间: {get_shanghai_time()} 账户: {account_name} 收盘价: {order_price} 数量: {qty}")


def main():
    print(f"[{get_shanghai_time()}] [INFO] 开始VINE-5m-大振幅反转策略 多账号模式")
    # 统一获取K线，所有账号用同一根K线
    suffix0 = ACCOUNT_SUFFIXES[0] if ACCOUNT_SUFFIXES else ""
    API_KEY = get_env_var("OKX_API_KEY", suffix0)
    SECRET_KEY = get_env_var("OKX_SECRET_KEY", suffix0)
    PASSPHRASE = get_env_var("OKX_PASSPHRASE", suffix0)
    FLAG = get_env_var("OKX_FLAG", suffix0, default="0")
    kline_data = get_kline_data(API_KEY, SECRET_KEY, PASSPHRASE, SYMBOL, KLINE_INTERVAL, limit=2, flag=FLAG)
    if not kline_data or len(kline_data) < 1:
        print(f"[{get_shanghai_time()}] [ERROR] 未获取到K线数据")
        return
    for suffix in ACCOUNT_SUFFIXES:
        process_account_trading(suffix, kline_data)
    print(f"[{get_shanghai_time()}] [INFO] 所有账户处理完成")

if __name__ == "__main__":
    main() 