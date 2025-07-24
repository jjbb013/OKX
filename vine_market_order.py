"""
name: OKX VINE 市价下单脚本
"""
import os
import json
import random
import string
import time
from datetime import datetime, timezone, timedelta
import okx.Trade as Trade
from notification_service import notification_service

# ============== 可配置参数区域 ==============
INST_ID = "VINE-USDT-SWAP"  # 交易标的
ORDER_SIZE = 10  # 下单张数
ORDER_SIDE = "buy"  # "buy" 做多，"sell" 做空
ACCOUNT_SUFFIXES = ["1", "2"]  # 多账号支持

MAX_RETRIES = 3
RETRY_DELAY = 2

def get_beijing_time():
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")

def get_env_var(var_name, suffix="", default=None):
    if suffix:
        return os.getenv(f"OKX{suffix}_{var_name}", default)
    else:
        return os.getenv(f"OKX_{var_name}", default)

def generate_clord_id():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    return f"VINE{timestamp}{random_str}"[:32]

def market_order(account_suffix, order_size, order_side):
    suffix = account_suffix if account_suffix else ""
    account_prefix = f"[ACCOUNT-{suffix}]" if suffix else "[ACCOUNT]"
    api_key = get_env_var("API_KEY", suffix)
    secret_key = get_env_var("SECRET_KEY", suffix)
    passphrase = get_env_var("PASSPHRASE", suffix)
    flag = get_env_var("FLAG", suffix, "0")
    account_name = get_env_var("ACCOUNT_NAME", suffix) or f"账户{suffix}" if suffix else "默认账户"
    if not all([api_key, secret_key, passphrase]):
        print(f"[{get_beijing_time()}] {account_prefix} [ERROR] 账户信息不完整或未配置")
        return
    api_key = str(api_key)
    secret_key = str(secret_key)
    passphrase = str(passphrase)
    flag = str(flag)
    try:
        trade_api = Trade.TradeAPI(api_key, secret_key, passphrase, False, flag)
        print(f"[{get_beijing_time()}] {account_prefix} API初始化成功 - {account_name}")
    except Exception as e:
        print(f"[{get_beijing_time()}] {account_prefix} [ERROR] API初始化失败: {str(e)}")
        return
    cl_ord_id = generate_clord_id()
    order_params = {
        "instId": INST_ID,
        "tdMode": "cross",
        "side": order_side,
        "ordType": "market",
        "sz": str(order_size),
        "clOrdId": cl_ord_id,
        "posSide": "long" if order_side == "buy" else "short"
    }
    print(f"[{get_beijing_time()}] {account_prefix} [ORDER] 市价下单参数: {json.dumps(order_params, indent=2)}")
    order_result = None
    success = False
    error_msg = ""
    for attempt in range(MAX_RETRIES + 1):
        try:
            order_result = trade_api.place_order(**order_params)
            print(f"[{get_beijing_time()}] {account_prefix} [ORDER] 订单提交结果: {json.dumps(order_result)}")
            if order_result and 'code' in order_result and order_result['code'] == '0':
                success = True
                error_msg = ""
            else:
                success = False
                error_msg = order_result.get('msg', '') if order_result else '下单失败，无响应'
            break
        except Exception as e:
            print(f"[{get_beijing_time()}] {account_prefix} [ORDER] 下单异常 (尝试 {attempt+1}/{MAX_RETRIES+1}): {str(e)}")
            success = False
            error_msg = str(e)
            if attempt < MAX_RETRIES:
                print(f"[{get_beijing_time()}] {account_prefix} [ORDER] 重试中... ({attempt+1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
            else:
                print(f"[{get_beijing_time()}] {account_prefix} [ORDER] 所有尝试失败")
    notification_service.send_trading_notification(
        account_name=account_name,
        inst_id=INST_ID,
        signal_type=order_side.upper(),
        entry_price=None,
        size=order_size,
        margin=None,
        take_profit_price=None,
        stop_loss_price=None,
        success=success,
        error_msg=f"[vine_market_order] {error_msg}",
        order_params=order_params,
        order_result=order_result
    )
    print(f"[{get_beijing_time()}] {account_prefix} [ORDER] 市价下单完成")

if __name__ == "__main__":
    print(f"[{get_beijing_time()}] [INFO] 开始VINE市价下单脚本")
    for suffix in ACCOUNT_SUFFIXES:
        market_order(suffix, ORDER_SIZE, ORDER_SIDE)
    print(f"[{get_beijing_time()}] [INFO] 所有账户市价下单完成") 