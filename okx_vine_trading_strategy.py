"""
任务名称
name: OKX VINE 自动交易 PROD
定时规则
cron: 1 */5 * * * *
"""
import os
import pandas as pd
import requests
import json
import random
import string
from datetime import datetime, timezone, timedelta
import okx.MarketData as MarketData
import okx.Trade as Trade

# ============== 可配置参数区域 ==============
# 交易标的参数
INST_ID = "VINE-USDT-SWAP"  # 交易标的
BAR = "5m"  # K线规格
LIMIT = 2  # 获取K线数量
LEVERAGE = 10  # 杠杆倍数
SizePoint = 2  # 下单数量的小数点保留位数

# 振幅阈值参数
RANGE1_MIN = 1.0  # 振幅范围1最小值(1%)
RANGE1_MAX = 1.5  # 振幅范围1最大值(1.5%)
RANGE2_THRESHOLD = 2  # 振幅范围2阈值(2%)

# 交易执行参数
MARGIN = 5  # 保证金(USDT)
TAKE_PROFIT_PERCENT = 0.015  # 止盈比例改为1.5%
STOP_LOSS_PERCENT = 0.03  # 止损比例(3%)

# 从环境变量获取账户信息
API_KEY = os.getenv("OKX_API_KEY")
SECRET_KEY = os.getenv("OKX_SECRET_KEY")
PASSPHRASE = os.getenv("OKX_PASSPHRASE")
FLAG = os.getenv("OKX_FLAG", "0")  # 默认实盘

# Bark通知配置
BARK_KEY = os.getenv("BARK_KEY")
BARK_GROUP = os.getenv("BARK_GROUP", "OKX自动交易通知")

# 前缀生成配置
PREFIX = INST_ID.split('-')[0]  # 使用标的名称作为前缀(如ETH)

# ==========================================

def get_beijing_time():
    """获取北京时间"""
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")


def send_bark_notification(title, message):
    """发送Bark通知"""
    if not BARK_KEY:
        print(f"[{get_beijing_time()}] [ERROR] 缺少BARK_KEY配置")
        return

    payload = {
        'title': title,
        'body': message,
        'group': BARK_GROUP,
        'sound': 'minuet'
    }
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(BARK_KEY, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"[{get_beijing_time()}] [BARK] 通知发送成功")
        else:
            print(f"[{get_beijing_time()}] [BARK] 发送失败: {response.text}")
    except Exception as e:
        print(f"[{get_beijing_time()}] [BARK] 异常: {str(e)}")


def get_orders_pending(trade_api):
    """获取当前账户下所有未成交订单信息"""
    try:
        # 使用Trade API的内部请求方法
        result = trade_api.get_order_list(instId=INST_ID)
        
        if result and 'code' in result and result['code'] == '0' and 'data' in result:
            print(f"[{get_beijing_time()}] [ORDERS] 成功获取{len(result['data'])}个未成交订单")
            return result['data']
        else:
            error_msg = result.get('msg', '') if result else '无响应'
            print(f"[{get_beijing_time()}] [ORDERS] 获取未成交订单失败: {error_msg}")
            return []
    except Exception as e:
        print(f"[{get_beijing_time()}] [ORDERS] 获取未成交订单异常: {str(e)}")
        return []


def get_pending_open_orders(trade_api):
    """
    获取需要撤销的开仓订单列表
    根据要求：linkedAlgoOrd为空时需要撤销
    """
    try:
        # 获取所有未成交订单
        all_pending_orders = get_orders_pending(trade_api)
        
        # 过滤出需要撤销的订单
        cancel_orders = []
        for order in all_pending_orders:
            # 检查linkedAlgoOrd字段 - 如果为空，说明是开仓订单需要撤销
            linked_algo = order.get('linkedAlgoOrd', {})
            algo_id = linked_algo.get('algoId', '')
            
            # 如果linkedAlgoOrd为空或者algoId为空字符串，则此订单需要撤销
            if not linked_algo or algo_id == '':
                cancel_orders.append({
                    "instId": INST_ID,
                    "ordId": order['ordId']
                })
                
                print(f"[{get_beijing_time()}] [TO_CANCEL] 标记为待撤销: ordId={order['ordId']}, linkedAlgoOrd={'空' if algo_id == '' else '非空'}")
        
        return cancel_orders
    except Exception as e:
        print(f"[{get_beijing_time()}] [ORDERS] 获取待撤销订单异常: {str(e)}")
        return []


def cancel_pending_open_orders(trade_api):
    """批量撤销需要取消的开仓订单"""
    # 获取需要撤销的订单列表
    cancel_orders = get_pending_open_orders(trade_api)
    
    if not cancel_orders:
        print(f"[{get_beijing_time()}] [CANCEL] 无需要撤销的开仓订单")
        return False  # 返回是否有订单被撤销
    
    try:
        # 准备批量撤销请求
        cancel_data = {
            "cancels": cancel_orders
        }
        
        print(f"[{get_beijing_time()}] [CANCEL] 正在批量撤销{len(cancel_orders)}个开仓订单")
        result = trade_api._request('POST', '/api/v5/trade/cancel-batch-orders', body=cancel_data)
        
        if result and 'code' in result and result['code'] == '0':
            # 成功响应
            failed_orders = []
            for order_result in result['data']:
                if order_result['sCode'] != '0':
                    failed_orders.append({
                        "ordId": order_result['ordId'],
                        "code": order_result['sCode'],
                        "msg": order_result['sMsg']
                    })
            
            if failed_orders:
                print(f"[{get_beijing_time()}] [CANCEL] 部分订单撤销失败: {json.dumps(failed_orders)}")
                return False
            else:
                print(f"[{get_beijing_time()}] [CANCEL] 所有{len(cancel_orders)}个订单撤销成功")
                
                # 发送通知
                first_order = cancel_orders[0]
                send_bark_notification(
                    "开仓订单撤销",
                    f"已撤销{len(cancel_orders)}个未成交开仓订单\n"
                    f"首个订单ID: {first_order['ordId']}\n"
                    f"标的: {INST_ID}"
                )
                return True
        else:
            error_msg = result.get('msg', '') if result else '无响应'
            print(f"[{get_beijing_time()}] [CANCEL] 批量撤销失败: {error_msg}")
            return False
    except Exception as e:
        print(f"[{get_beijing_time()}] [CANCEL] 撤销订单异常: {str(e)}")
        return False


def analyze_kline(kline):
    """分析单个K线，返回信号、入场价和振幅信息"""
    # 解析K线数据
    timestamp = int(kline[0])
    open_price = float(kline[1])
    high_price = float(kline[2])
    low_price = float(kline[3])
    close_price = float(kline[4])

    # 计算并记录振幅变量
    body_change = abs(close_price - open_price)
    body_change_perc = body_change / open_price * 100
    total_range = high_price - low_price
    total_range_perc = total_range / low_price * 100

    # 检查条件
    in_range1 = (body_change_perc >= RANGE1_MIN) and (body_change_perc <= RANGE1_MAX)
    # 修改为实体振幅大于2%
    in_range2 = body_change_perc > RANGE2_THRESHOLD
    is_green = close_price > open_price
    is_red = close_price < open_price

    signal = None
    entry_price = None
    condition = ""

    # 判断是否满足交易条件
    if in_range1 or in_range2:
        if in_range1:
            entry_price = (high_price + low_price) / 2
            signal = 'LONG' if is_green else 'SHORT'
            condition = f"满足振幅范围1条件({RANGE1_MIN}%-{RANGE1_MAX}%)"
        elif in_range2:
            # 修改为使用收盘价入场
            entry_price = close_price
            # 保持反向交易信号
            signal = 'SHORT' if is_green else 'LONG'
            condition = f"满足振幅范围2条件(实体振幅> {RANGE2_THRESHOLD}%)"

    # 返回所有计算数据
    amp_info = {
        'timestamp': timestamp,
        'open': open_price,
        'high': high_price,
        'low': low_price,
        'close': close_price,
        'body_change': body_change,
        'body_change_perc': body_change_perc,
        'total_range': total_range,
        'total_range_perc': total_range_perc,
        'in_range1': in_range1,
        'in_range2': in_range2,
        'is_green': is_green,
        'is_red': is_red,
        'signal': signal,
        'entry_price': entry_price,
        'condition': condition
    }

    return signal, entry_price, amp_info


def generate_clord_id():
    """生成符合OKX要求的clOrdId：字母数字组合，1-32位"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    return f"{PREFIX}{timestamp}{random_str}"[:32]


if __name__ == "__main__":
    # 验证账户信息
    if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
        print(f"[{get_beijing_time()}] [ERROR] 缺少OKX账户信息")
        exit(1)

    # 初始化API
    market_api = MarketData.MarketAPI(API_KEY, SECRET_KEY, PASSPHRASE, False, FLAG)
    trade_api = Trade.TradeAPI(API_KEY, SECRET_KEY, PASSPHRASE, False, FLAG)
    market_api.OK_ACCESS_TIMESTAMP = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    
    # 获取最近K线数据
    result = market_api.get_candlesticks(instId=INST_ID, bar=BAR, limit=str(LIMIT))

    if not result or 'data' not in result or len(result['data']) < 2:
        print(f"[{get_beijing_time()}] [ERROR] 获取K线数据失败或数据不足")
        exit(1)

    # 提取倒数第二根K线(前一根K线)
    prev_kline = result['data'][1]
    print(f"[{get_beijing_time()}] [DEBUG] 正在分析前一根K线: {prev_kline}")

    # 分析K线
    signal, entry_price, amp_info = analyze_kline(prev_kline)

    # 输出K线分析详情
    print(f"[{get_beijing_time()}] [KLINE] 分析结果:")
    print(f"  标的: {INST_ID} | K线规格: {BAR}")
    print(f"  开盘价: {amp_info['open']:.4f}")
    print(f"  最高价: {amp_info['high']:.4f}")
    print(f"  最低价: {amp_info['low']:.4f}")
    print(f"  收盘价: {amp_info['close']:.4f}")
    print(f"  K线实体变动: {amp_info['body_change']:.4f} ({amp_info['body_change_perc']:.2f}%)")
    print(f"  总振幅: {amp_info['total_range']:.4f} ({amp_info['total_range_perc']:.2f}%)")
    print(f"  振幅范围1({RANGE1_MIN}%-{RANGE1_MAX}%): {'满足' if amp_info['in_range1'] else '不满足'}")
    print(f"  振幅范围2(实体振幅> {RANGE2_THRESHOLD}%): {'满足' if amp_info['in_range2'] else '不满足'}")
    print(f"  是否为阳线: {amp_info['is_green']}")
    print(f"  是否为阴线: {amp_info['is_red']}")
    print(f"  信号: {signal if signal else '无信号'}")
    print(f"  入场价: {entry_price if entry_price else 'N/A'}")
    print(f"  条件: {amp_info['condition'] if amp_info['condition'] else '无交易条件'}")

    # 满足振幅条件时发送通知
    if amp_info['in_range1'] or amp_info['in_range2']:
        title = f"振幅预警! {INST_ID} 实体变动: {amp_info['body_change_perc']:.2f}%"
        message = (
            f"时间: {get_beijing_time()}\n"
            f"开盘: {amp_info['open']:.4f}\n"
            f"收盘: {amp_info['close']:.4f}\n"
            f"总振幅: {amp_info['total_range_perc']:.2f}%\n"
            f"条件: {amp_info['condition']}"
        )
        send_bark_notification(title, message)
        print(f"[{get_beijing_time()}] [AMPLITUDE] 发送振幅预警通知")

    # 如果有交易信号
    if signal:
        # 1. 撤销现有的开仓订单
        print(f"[{get_beijing_time()}] [ORDER] 检测到信号，先撤销现有开仓订单")
        canceled = cancel_pending_open_orders(trade_api)
        
        # 2. 计算合约数量
        size = round((MARGIN * LEVERAGE * 10 ) / entry_price, SizePoint) # 乘以10是标准倍数，如果不乘保证金会小十倍。

        # 根据信号方向计算止盈止损价格
        if signal == "LONG":
            take_profit_price = round(entry_price * (1 + TAKE_PROFIT_PERCENT), 4)
            stop_loss_price = round(entry_price * (1 - STOP_LOSS_PERCENT), 4)
        else:  # SHORT
            take_profit_price = round(entry_price * (1 - TAKE_PROFIT_PERCENT), 4)
            stop_loss_price = round(entry_price * (1 + STOP_LOSS_PERCENT), 4)

        # 生成符合要求的clOrdId
        cl_ord_id = generate_clord_id()

        # 构建止盈止损对象列表
        attach_algo_ord = {
            "attachAlgoClOrdId": generate_clord_id(),
            "tpTriggerPx": str(take_profit_price),
            "tpOrdPx": "-1",  # 市价止盈
            "tpOrdKind": "condition",
            "slTriggerPx": str(stop_loss_price),
            "slOrdPx": "-1",  # 市价止损
            "tpTriggerPxType": "last",
            "slTriggerPxType": "last"
        }

        # 重构交易参数
        order_params = {
            "instId": INST_ID,
            "tdMode": "cross",
            "side": "buy" if signal == "LONG" else "sell",
            "ordType": "limit",
            "px": str(entry_price),
            "sz": str(size),
            "clOrdId": cl_ord_id,
            "posSide": "long" if signal == "LONG" else "short",
            "attachAlgoOrds": [attach_algo_ord]
        }

        print(f"[{get_beijing_time()}] [ORDER] 准备下单参数: {json.dumps(order_params, indent=2)}")

        # 发送订单
        try:
            order_result = trade_api.place_order(**order_params)
            print(f"[{get_beijing_time()}] [ORDER] 订单提交结果: {json.dumps(order_result)}")
            
            # 检查是否成功下单
            if order_result and 'code' in order_result and order_result['code'] == '0':
                success = True
            else:
                success = False
                error_msg = order_result.get('msg', '') if order_result else '下单失败，无响应'
        except Exception as e:
            print(f"[{get_beijing_time()}] [ORDER] 下单异常: {str(e)}")
            success = False
            error_msg = str(e)

        # 发送交易通知
        title = f"交易信号: {signal} @ {INST_ID}"
        message = (
            f"信号类型: {signal}\n"
            f"入场价格: {entry_price:.4f}\n"
            f"委托数量: {size}\n"
            f"保证金: {MARGIN} USDT\n"
            f"止盈价: {take_profit_price:.4f} ({TAKE_PROFIT_PERCENT * 100:.2f}%)\n"
            f"止损价: {stop_loss_price:.4f} ({STOP_LOSS_PERCENT * 100:.2f}%)"
        )
        
        # 如果下单失败，添加错误信息
        if not success:
            message += f"\n\n⚠️ 下单失败 ⚠️\n错误: {error_msg}"
        
        send_bark_notification(title, message)

        # 日志输出
        print(f"[{get_beijing_time()}] [SIGNAL] {signal}@{entry_price:.4f}")
        print(f"[{get_beijing_time()}] [ORDER] {json.dumps(order_params)}")
        print(f"[{get_beijing_time()}] [RESULT] {json.dumps(order_result)}")
    else:
        print(f"[{get_beijing_time()}] [INFO] 未检测到交易信号")
        print(f"[{get_beijing_time()}] [AMP_DETAIL] "
              f"振幅范围1: {amp_info['in_range1']} "
              f"振幅范围2: {amp_info['in_range2']} "
              f"实体变动: {amp_info['body_change_perc']:.2f}% "
              f"总振幅: {amp_info['total_range_perc']:.2f}%")
