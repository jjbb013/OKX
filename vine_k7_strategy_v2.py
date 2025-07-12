"""
任务名称
name: OKX VINE K7趋势策略 V2
定时规则
cron: 3 */5 * * * *
"""
import os
import json
import random
import string
import time
from datetime import datetime, timezone, timedelta
import okx.MarketData as MarketData
import okx.Trade as Trade
from notification_service import notification_service

# ============== 可配置参数区域 ==============
# 交易标的参数
INST_ID = "VINE-USDT-SWAP"  # 交易标的
BAR = "5m"  # K线规格
LIMIT = 7  # 获取7根K线
LEVERAGE = 20  # 杠杆倍数
SizePoint = 0  # 下单数量的小数点保留位数
CONTRACT_FACE_VALUE = 10  # VINE-USDT-SWAP合约面值为10美元

# 策略参数
MARGIN = 5  # 保证金(USDT)
TAKE_PROFIT_PERCENT = 0.018  # 止盈1.6%
STOP_LOSS_PERCENT = 0.017     # 止损2%
MIN_BODY1 = 0.01  # K2最小实体振幅(1%)
MAX_BODY1 = 0.04  # K2最大实体振幅(4%)
MAX_TOTAL_RANGE = 0.017  # K3~K6总单向振幅上限(2%)

# 环境变量账户后缀，支持多账号
ACCOUNT_SUFFIXES = ["1", "2"]

# 网络请求重试配置
MAX_RETRIES = 3
RETRY_DELAY = 2

def get_beijing_time():
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")

def get_env_var(var_name, suffix="", default=None):
    if suffix:
        # 对于多账号，格式为 OKX1_ACCOUNT_NAME, OKX2_API_KEY 等
        return os.getenv(f"OKX{suffix}_{var_name}", default)
    else:
        # 对于默认账号，格式为 OKX_ACCOUNT_NAME, OKX_API_KEY 等
        return os.getenv(f"OKX_{var_name}", default)

def get_current_price(market_api, inst_id, account_prefix=""):
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = market_api.get_ticker(instId=inst_id)
            if result and 'code' in result and result['code'] == '0' and 'data' in result:
                current_price = float(result['data'][0]['last'])
                print(f"[{get_beijing_time()}] {account_prefix} [PRICE] {inst_id} 当前价格: {current_price}")
                return current_price
            else:
                error_msg = result.get('msg', '') if result else '无响应'
                print(f"[{get_beijing_time()}] {account_prefix} [PRICE] 获取{inst_id}价格失败: {error_msg}")
        except Exception as e:
            print(f"[{get_beijing_time()}] {account_prefix} [PRICE] 获取{inst_id}价格异常 (尝试 {attempt+1}/{MAX_RETRIES+1}): {str(e)}")
        if attempt < MAX_RETRIES:
            print(f"[{get_beijing_time()}] {account_prefix} [PRICE] 重试中... ({attempt+1}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
    print(f"[{get_beijing_time()}] {account_prefix} [PRICE] 获取{inst_id}价格失败")
    return None

def get_pending_orders(trade_api, inst_id, account_prefix=""):
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = trade_api.get_order_list(instId=inst_id, state="live")
            if result and 'code' in result and result['code'] == '0' and 'data' in result:
                orders = result['data']
                print(f"[{get_beijing_time()}] {account_prefix} [ORDERS] {inst_id} 获取到{len(orders)}个未成交订单")
                return orders
            else:
                error_msg = result.get('msg', '') if result else '无响应'
                print(f"[{get_beijing_time()}] {account_prefix} [ORDERS] 获取{inst_id}未成交订单失败: {error_msg}")
        except Exception as e:
            print(f"[{get_beijing_time()}] {account_prefix} [ORDERS] 获取{inst_id}未成交订单异常 (尝试 {attempt+1}/{MAX_RETRIES+1}): {str(e)}")
        if attempt < MAX_RETRIES:
            print(f"[{get_beijing_time()}] {account_prefix} [ORDERS] 重试中... ({attempt+1}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
    print(f"[{get_beijing_time()}] {account_prefix} [ORDERS] 获取{inst_id}未成交订单失败")
    return []

def cancel_order(trade_api, inst_id, ord_id, account_prefix=""):
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = trade_api.cancel_order(instId=inst_id, ordId=ord_id)
            if result and 'code' in result and result['code'] == '0':
                print(f"[{get_beijing_time()}] {account_prefix} [CANCEL] 订单{ord_id}撤销成功")
                return True, "撤销成功"
            else:
                error_msg = result.get('msg', '') if result else '无响应'
                print(f"[{get_beijing_time()}] {account_prefix} [CANCEL] 订单{ord_id}撤销失败: {error_msg}")
        except Exception as e:
            print(f"[{get_beijing_time()}] {account_prefix} [CANCEL] 订单{ord_id}撤销异常 (尝试 {attempt+1}/{MAX_RETRIES+1}): {str(e)}")
        if attempt < MAX_RETRIES:
            print(f"[{get_beijing_time()}] {account_prefix} [CANCEL] 重试中... ({attempt+1}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
    print(f"[{get_beijing_time()}] {account_prefix} [CANCEL] 订单{ord_id}撤销失败")
    return False, "撤销失败"

def cancel_pending_open_orders(trade_api, account_prefix=""):
    """
    撤销所有未成交的开仓订单（只撤销开仓方向的订单，平仓单不处理）
    """
    pending_orders = get_pending_orders(trade_api, INST_ID, account_prefix)
    for order in pending_orders:
        # 只撤销开仓订单
        pos_side = order.get('posSide', '')
        # 只处理long/short方向的开仓单
        if pos_side in ['long', 'short', '']:
            ord_id = order['ordId']
            cancel_order(trade_api, INST_ID, ord_id, account_prefix)

def analyze_kline(kline_list):
    """
    分析K线，判断是否产生交易信号。
    kline_list: 最新在前，K1=0, K2=1, ..., K7=6
    返回: (信号, 入场价, 分析详情字典)
    """
    print(f"[{get_beijing_time()}] [DEBUG] 开始分析K线数据，共{len(kline_list)}根")
    if len(kline_list) < 7:
        print(f"[{get_beijing_time()}] [WARN] K线数量不足7根，无法分析")
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

def generate_clord_id():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    return f"VINE{timestamp}{random_str}"[:32]

def save_trading_log(account_name, signal, entry_price, qty, order_params, order_result, amp_info=None):
    """
    保存交易日志到青龙面板可查阅的区域
    """
    try:
        # 确保logs目录存在
        os.makedirs("logs", exist_ok=True)
        
        # 创建日志文件名（按日期）
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = f"logs/vine_k7_strategy_{today}.log"
        
        # 准备日志数据
        log_data = {
            "timestamp": get_beijing_time(),
            "account_name": account_name,
            "symbol": INST_ID,
            "signal": signal,
            "entry_price": entry_price,
            "quantity": qty,
            "margin": MARGIN,
            "leverage": LEVERAGE,
            "order_params": order_params,
            "order_result": order_result,
            "analysis_info": amp_info
        }
        
        # 写入日志文件
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_data, ensure_ascii=False, indent=2) + "\n" + "-" * 80 + "\n")
        
        print(f"[{get_beijing_time()}] [LOG] 交易日志已保存到: {log_file}")
        
    except Exception as e:
        print(f"[{get_beijing_time()}] [LOG] 保存日志失败: {str(e)}")

def process_account_trading(account_suffix, signal, entry_price, amp_info):
    suffix = account_suffix if account_suffix else ""
    account_prefix = f"[ACCOUNT-{suffix}]" if suffix else "[ACCOUNT]"
    
    # 使用新的环境变量格式
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
        market_api = MarketData.MarketAPI(api_key, secret_key, passphrase, False, flag)
        print(f"[{get_beijing_time()}] {account_prefix} API初始化成功 - {account_name}")
    except Exception as e:
        print(f"[{get_beijing_time()}] {account_prefix} [ERROR] API初始化失败: {str(e)}")
        return
    
    # 撤销现有开仓订单
    print(f"[{get_beijing_time()}] {account_prefix} [ORDER] 检测到信号，先撤销现有开仓订单")
    cancel_pending_open_orders(trade_api, account_prefix)
    
    # 计算下单数量（保证金10USDT，10倍杠杆，价值约100USDT，向上取整为10的倍数）
    trade_value = MARGIN * LEVERAGE
    raw_qty = trade_value / (entry_price * CONTRACT_FACE_VALUE)
    qty = int((raw_qty + 9) // 10 * 10)  # 向上取整为10的倍数
    
    if qty == 0:
        print(f"[{get_beijing_time()}] {account_prefix} [ERROR] 计算数量为0，放弃交易")
        notification_service.send_bark_notification(
            f"{account_prefix} 交易失败",
            f"计算数量为0，放弃交易\n入场价格: {entry_price:.4f}\n保证金: {MARGIN} USDT\n杠杆: {LEVERAGE}倍",
            group="青龙交易通知PROD"
        )
        return
    
    print(f"[{get_beijing_time()}] {account_prefix} [SIZE_CALC] 下单数量: {qty} (10的倍数)")
    
    # 计算止盈止损价格
    if signal == "LONG":
        take_profit_price = round(entry_price * (1 + TAKE_PROFIT_PERCENT), 5)
        stop_loss_price = round(entry_price * (1 - STOP_LOSS_PERCENT), 5)
    else:
        take_profit_price = round(entry_price * (1 - TAKE_PROFIT_PERCENT), 5)
        stop_loss_price = round(entry_price * (1 + STOP_LOSS_PERCENT), 5)
    
    # 生成订单参数
    cl_ord_id = generate_clord_id()
    attach_algo_ord = {
        "attachAlgoClOrdId": generate_clord_id(),
        "tpTriggerPx": str(take_profit_price),
        "tpOrdPx": "-1",
        "tpOrdKind": "condition",
        "slTriggerPx": str(stop_loss_price),
        "slOrdPx": "-1",
        "tpTriggerPxType": "last",
        "slTriggerPxType": "last"
    }
    
    order_params = {
        "instId": INST_ID,
        "tdMode": "cross",
        "side": "buy" if signal == "LONG" else "sell",
        "ordType": "limit",
        "px": str(entry_price),
        "sz": str(qty),
        "clOrdId": cl_ord_id,
        "posSide": "long" if signal == "LONG" else "short",
        "attachAlgoOrds": [attach_algo_ord]
    }
    
    print(f"[{get_beijing_time()}] {account_prefix} [ORDER] 准备下单参数: {json.dumps(order_params, indent=2)}")
    
    # 下单
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
    
    # 保存交易日志
    save_trading_log(account_name, signal, entry_price, qty, order_params, order_result, amp_info)
    
    # 发送通知
    notification_service.send_trading_notification(
        account_name=account_name,
        inst_id=INST_ID,
        signal_type=signal,
        entry_price=entry_price,
        size=qty,
        margin=MARGIN,
        take_profit_price=take_profit_price,
        stop_loss_price=stop_loss_price,
        success=success,
        error_msg=error_msg,
        order_params=order_params,
        order_result=order_result
    )
    
    print(f"[{get_beijing_time()}] {account_prefix} [SIGNAL] {signal}@{entry_price:.4f}")
    print(f"[{get_beijing_time()}] {account_prefix} [ORDER] {json.dumps(order_params)}")
    print(f"[{get_beijing_time()}] {account_prefix} [RESULT] {json.dumps(order_result)}")

def get_kline_data():
    suffix = ACCOUNT_SUFFIXES[0] if ACCOUNT_SUFFIXES else ""
    api_key = get_env_var("API_KEY", suffix)
    secret_key = get_env_var("SECRET_KEY", suffix)
    passphrase = get_env_var("PASSPHRASE", suffix)
    flag = get_env_var("FLAG", suffix, "0")
    
    if not all([api_key, secret_key, passphrase]):
        print(f"[{get_beijing_time()}] [ERROR] 账户信息不完整，无法获取K线数据")
        return None, None, None
    
    try:
        market_api = MarketData.MarketAPI(str(api_key), str(secret_key), str(passphrase), False, str(flag))
        print(f"[{get_beijing_time()}] [MARKET] K线API初始化成功")
    except Exception as e:
        print(f"[{get_beijing_time()}] [ERROR] K线API初始化失败: {str(e)}")
        return None, None, None
    
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = market_api.get_candlesticks(instId=INST_ID, bar=BAR, limit=str(LIMIT))
            break
        except Exception as e:
            print(f"[{get_beijing_time()}] [MARKET] 获取K线数据异常 (尝试 {attempt+1}/{MAX_RETRIES+1}): {str(e)}")
            if attempt < MAX_RETRIES:
                print(f"[{get_beijing_time()}] [MARKET] 重试中... ({attempt+1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
            else:
                print(f"[{get_beijing_time()}] [MARKET] 所有尝试失败")
                return None, None, None
    
    if not result or 'data' not in result or len(result['data']) < 7:
        print(f"[{get_beijing_time()}] [ERROR] 获取K线数据失败或数据不足")
        return None, None, None
    
    kline_data = result['data']
    print(f"[{get_beijing_time()}] [DEBUG] 正在分析K线数据，共{len(kline_data)}根")
    
    signal, entry_price, amp_info = analyze_kline(kline_data)
    
    print(f"[{get_beijing_time()}] [KLINE] 分析结果:")
    print(f"  标的: {INST_ID} | K线规格: {BAR}")
    if amp_info:
        print(f"  K2实体振幅: {amp_info['body2']*100:.2f}%")
        print(f"  K3~K6总振幅: {amp_info['total_range']*100:.2f}%")
        print(f"  K2是否为阳线: {amp_info['is_long']}")
        print(f"  K2是否为阴线: {amp_info['is_short']}")
        print(f"  是否符合入场条件: {amp_info['can_entry']}")
    print(f"  信号: {signal if signal else '无信号'}")
    print(f"  入场价: {entry_price if entry_price else 'N/A'}")
    
    return signal, entry_price, amp_info

if __name__ == "__main__":
    print(f"[{get_beijing_time()}] [INFO] 开始VINE K7趋势策略 V2")
    signal, entry_price, amp_info = get_kline_data()
    
    if not signal:
        print(f"[{get_beijing_time()}] [INFO] 未检测到交易信号")
        # 无信号时也记录日志
        if entry_price:
            for suffix in ACCOUNT_SUFFIXES:
                account_name = get_env_var("ACCOUNT_NAME", suffix) or f"账户{suffix}"
                trade_value = MARGIN * LEVERAGE
                raw_qty = trade_value / (entry_price * CONTRACT_FACE_VALUE)
                qty = int((raw_qty + 9) // 10 * 10)
                print(f"[{get_beijing_time()}] [INFO] 无信号时，{account_name} 计算下单数量: {qty}")
                save_trading_log(account_name, "NO_SIGNAL", entry_price, qty, {}, {}, amp_info)
        exit(0)
    
    print(f"[{get_beijing_time()}] [INFO] 开始处理所有账户交易")
    for suffix in ACCOUNT_SUFFIXES:
        process_account_trading(suffix, signal, entry_price, amp_info)
    print(f"[{get_beijing_time()}] [INFO] 所有账户交易处理完成") 