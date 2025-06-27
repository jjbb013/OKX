"""
任务名称
name: OKX 委托订单监控与撤销
定时规则
cron: */10 * * * *
"""
import os
import json
import time
from datetime import datetime, timezone, timedelta
import okx.MarketData as MarketData
import okx.Trade as Trade
from notification_service import notification_service

# 尝试导入本地配置，如果不存在则使用环境变量
try:
    from config_local import *
    print("[INFO] 使用本地配置文件")
    IS_DEVELOPMENT = True
except ImportError:
    print("[INFO] 使用环境变量配置")
    IS_DEVELOPMENT = False

# ============== 可配置参数区域 ==============
# 环境变量账户后缀，支持多账号 (如OKX_API_KEY1, OKX_SECRET_KEY1, OKX_PASSPHRASE1)
ACCOUNT_SUFFIXES = ["", "1", "2", "3"]  # 空字符串代表无后缀的默认账号

# 监控的交易标的列表
MONITOR_INST_IDS = [
    "ETH-USDT-SWAP",
    "VINE-USDT-SWAP",
    # 可以添加更多交易标的
]

# 网络请求重试配置
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 2  # 重试间隔(秒)

# 价格比较容差（避免因微小价格波动导致的误判）
PRICE_TOLERANCE = 0.0001  # 0.01%的容差

# ==========================================

def get_beijing_time():
    """获取北京时间"""
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")

def get_env_var(var_name, suffix="", default=None):
    """获取环境变量或本地配置变量"""
    if IS_DEVELOPMENT:
        # 开发环境：从本地配置文件获取
        try:
            return globals()[f"{var_name}{suffix}"]
        except KeyError:
            return default
    else:
        # 生产环境：从环境变量获取
        return os.getenv(f"{var_name}{suffix}", default)

def get_current_price(market_api, inst_id, account_prefix=""):
    """获取指定交易标的的当前最新价格"""
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
    """获取指定交易标的的未成交订单"""
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

def should_cancel_order(order, current_price, account_prefix=""):
    """判断订单是否应该被撤销"""
    try:
        # 获取订单信息
        ord_id = order['ordId']
        side = order['side']  # buy 或 sell
        pos_side = order.get('posSide', '')  # long 或 short
        order_price = float(order['px'])  # 委托价格
        
        # 判断做多还是做空
        is_long = (side == 'buy' and pos_side == 'long') or (side == 'buy' and pos_side == '')
        is_short = (side == 'sell' and pos_side == 'short') or (side == 'sell' and pos_side == '')
        
        if not (is_long or is_short):
            print(f"[{get_beijing_time()}] {account_prefix} [CHECK] 订单{ord_id} 方向不明确: side={side}, posSide={pos_side}")
            return False, "方向不明确", None
        
        # 获取止盈价格
        take_profit_price = None
        linked_algo = order.get('linkedAlgoOrd', {})
        if linked_algo and 'tpTriggerPx' in linked_algo:
            take_profit_price = float(linked_algo['tpTriggerPx'])
            print(f"[{get_beijing_time()}] {account_prefix} [CHECK] 订单{ord_id} 止盈价格: {take_profit_price}")
        else:
            print(f"[{get_beijing_time()}] {account_prefix} [CHECK] 订单{ord_id} 无止盈价格信息")
            return False, "无止盈价格信息", None
        
        # 判断是否需要撤销
        should_cancel = False
        reason = ""
        
        if is_long:
            # 做多订单：当前价格超过止盈价格时撤销
            if current_price > take_profit_price * (1 + PRICE_TOLERANCE):
                should_cancel = True
                reason = f"做多订单，当前价格({current_price:.4f})已超过止盈价格({take_profit_price:.4f})"
        elif is_short:
            # 做空订单：当前价格低于止盈价格时撤销
            if current_price < take_profit_price * (1 - PRICE_TOLERANCE):
                should_cancel = True
                reason = f"做空订单，当前价格({current_price:.4f})已低于止盈价格({take_profit_price:.4f})"
        
        if should_cancel:
            print(f"[{get_beijing_time()}] {account_prefix} [CHECK] 订单{ord_id} 需要撤销: {reason}")
        else:
            print(f"[{get_beijing_time()}] {account_prefix} [CHECK] 订单{ord_id} 无需撤销: 当前价格={current_price:.4f}, 止盈价格={take_profit_price:.4f}")
        
        return should_cancel, reason, take_profit_price
        
    except Exception as e:
        print(f"[{get_beijing_time()}] {account_prefix} [CHECK] 判断订单{order.get('ordId', 'unknown')}时异常: {str(e)}")
        return False, f"判断异常: {str(e)}", None

def cancel_order(trade_api, inst_id, ord_id, account_prefix=""):
    """撤销指定订单"""
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

def process_account_orders(account_suffix):
    """处理单个账户的订单监控"""
    # 准备账户标识
    suffix_str = account_suffix if account_suffix else ""  # 空后缀对应默认账户
    prefix = "[ACCOUNT-" + suffix_str + "]" if suffix_str else "[ACCOUNT]"
    
    # 从环境变量获取账户信息
    api_key = get_env_var("OKX_API_KEY", suffix=suffix_str)
    secret_key = get_env_var("OKX_SECRET_KEY", suffix=suffix_str)
    passphrase = get_env_var("OKX_PASSPHRASE", suffix=suffix_str)
    flag = get_env_var("OKX_FLAG", suffix=suffix_str, default="0")  # 默认实盘
    account_name = get_env_var("OKX_ACCOUNT_NAME", suffix=suffix_str) or f"账户{suffix_str}" if suffix_str else "默认账户"
    
    if not all([api_key, secret_key, passphrase]):
        print(f"[{get_beijing_time()}] {prefix} [ERROR] 账户信息不完整或未配置")
        return {
            "account_name": account_name,
            "success": False,
            "error": "账户信息不完整",
            "canceled_count": 0,
            "total_orders": 0
        }
    
    # 初始化API
    try:
        # 确保所有参数都不为None
        if api_key is None or secret_key is None or passphrase is None:
            raise ValueError("API密钥、密钥或密码不能为空")
        
        trade_api = Trade.TradeAPI(api_key, secret_key, passphrase, False, flag)
        market_api = MarketData.MarketAPI(api_key, secret_key, passphrase, False, flag)
        print(f"[{get_beijing_time()}] {prefix} API初始化成功 - {account_name}")
    except Exception as e:
        error_msg = f"API初始化失败: {str(e)}"
        print(f"[{get_beijing_time()}] {prefix} [ERROR] {error_msg}")
        return {
            "account_name": account_name,
            "success": False,
            "error": error_msg,
            "canceled_count": 0,
            "total_orders": 0
        }
    
    # 统计信息
    total_orders = 0
    canceled_orders = []
    canceled_count = 0
    
    # 遍历所有监控的交易标的
    for inst_id in MONITOR_INST_IDS:
        print(f"[{get_beijing_time()}] {prefix} [MONITOR] 开始监控 {inst_id}")
        
        # 获取当前价格
        current_price = get_current_price(market_api, inst_id, prefix)
        if current_price is None:
            print(f"[{get_beijing_time()}] {prefix} [MONITOR] 跳过 {inst_id}，无法获取价格")
            continue
        
        # 获取未成交订单
        pending_orders = get_pending_orders(trade_api, inst_id, prefix)
        if not pending_orders:
            print(f"[{get_beijing_time()}] {prefix} [MONITOR] {inst_id} 无未成交订单")
            continue
        
        total_orders += len(pending_orders)
        
        # 检查每个订单
        for order in pending_orders:
            should_cancel, reason, take_profit_price = should_cancel_order(order, current_price, prefix)
            
            if should_cancel:
                # 撤销订单
                success, cancel_msg = cancel_order(trade_api, inst_id, order['ordId'], prefix)
                
                if success:
                    canceled_count += 1
                    print(f"[{get_beijing_time()}] {prefix} [CHECK] 订单{order['ordId']} 止盈价格: {take_profit_price}")
                    
                    canceled_orders.append({
                        "inst_id": inst_id,
                        "ord_id": order['ordId'],
                        "side": order['side'],
                        "pos_side": order.get('posSide', ''),
                        "order_price": float(order['px']),
                        "take_profit_price": take_profit_price,
                        "current_price": current_price,
                        "reason": reason
                    })
                    
                    # 发送撤销通知
                    notification_service.send_order_cancel_notification(
                        account_name=account_name,
                        inst_id=inst_id,
                        ord_id=order['ordId'],
                        side=order['side'],
                        pos_side=order.get('posSide', ''),
                        order_price=float(order['px']),
                        take_profit_price=take_profit_price,
                        current_price=current_price,
                        reason=reason
                    )
                else:
                    print(f"[{get_beijing_time()}] {prefix} [ERROR] 订单{order['ordId']}撤销失败: {cancel_msg}")
    
    return {
        "account_name": account_name,
        "success": True,
        "error": None,
        "canceled_count": canceled_count,
        "total_orders": total_orders,
        "canceled_orders": canceled_orders
    }

def send_summary_notification(results):
    """发送监控结果摘要"""
    total_accounts = len(results)
    success_accounts = sum(1 for r in results if r['success'])
    total_canceled = sum(r['canceled_count'] for r in results)
    total_orders = sum(r['total_orders'] for r in results)
    
    # 只在有撤销委托时才发送Bark通知
    if total_canceled > 0:
        title = f"委托监控结果: {total_canceled}个订单已撤销"
        message = f"监控时间: {get_beijing_time()}\n\n"
        
        for result in results:
            status = "✅ 成功" if result['success'] else "❌ 失败"
            message += f"账户: {result['account_name']}\n"
            message += f"状态: {status}\n"
            if result['success']:
                message += f"总订单数: {result['total_orders']}\n"
                message += f"撤销订单数: {result['canceled_count']}\n"
            else:
                message += f"错误: {result['error']}\n"
            message += "\n"
        
        message += f"总账户数: {total_accounts}\n"
        message += f"成功账户数: {success_accounts}\n"
        message += f"总撤销订单数: {total_canceled}\n"
        message += f"总监控订单数: {total_orders}"
        
        print(f"[{get_beijing_time()}] [SUMMARY] {message}")
        notification_service.send_summary_notification(results, total_canceled)
    else:
        # 没有撤销委托时，只打印日志，不发送Bark通知
        print(f"[{get_beijing_time()}] [SUMMARY] 监控完成，无撤销委托")
        print(f"[{get_beijing_time()}] [SUMMARY] 总账户数: {total_accounts}")
        print(f"[{get_beijing_time()}] [SUMMARY] 成功账户数: {success_accounts}")
        print(f"[{get_beijing_time()}] [SUMMARY] 总撤销订单数: {total_canceled}")
        print(f"[{get_beijing_time()}] [SUMMARY] 总监控订单数: {total_orders}")

if __name__ == "__main__":
    print(f"[{get_beijing_time()}] [INFO] 开始OKX委托订单监控")
    print(f"[{get_beijing_time()}] [CONFIG] 监控标的: {', '.join(MONITOR_INST_IDS)}")
    print(f"[{get_beijing_time()}] [CONFIG] 价格容差: {PRICE_TOLERANCE * 100:.2f}%")
    
    start_time = time.time()
    results = []
    
    # 处理所有账户
    for suffix in ACCOUNT_SUFFIXES:
        print(f"\n[{get_beijing_time()}] [ACCOUNT] 开始处理账户: {suffix if suffix else '默认'}")
        result = process_account_orders(suffix)
        results.append(result)
    
    # 计算总耗时
    total_time = time.time() - start_time
    mins, secs = divmod(total_time, 60)
    
    # 打印结果摘要
    print(f"\n[{get_beijing_time()}] [INFO] 所有账户监控完成")
    print(f"[{get_beijing_time()}] [INFO] 监控总耗时: {int(mins)}分 {int(secs)}秒")
    
    total_canceled = sum(r['canceled_count'] for r in results)
    total_orders = sum(r['total_orders'] for r in results)
    
    print(f"[{get_beijing_time()}] [SUMMARY] 总监控订单数: {total_orders}")
    print(f"[{get_beijing_time()}] [SUMMARY] 总撤销订单数: {total_canceled}")
    
    # 发送摘要通知
    send_summary_notification(results)
    
    print(f"[{get_beijing_time()}] [INFO] 委托订单监控完成") 