"""
任务名称
name: OKX 账户资产检查
定时规则
cron: 0 */2 * * * *
"""
import os
import json
import time
from datetime import datetime, timezone, timedelta
import okx.Account as Account
import okx.Trade as Trade
import okx.MarketData as MarketData

# 尝试导入本地配置，如果不存在则使用环境变量
try:
    from config_local import *
    print("[INFO] 使用本地配置文件")
except ImportError:
    print("[INFO] 使用环境变量配置")
    IS_DEVELOPMENT = False

# ============== 可配置参数区域 ==============
# 环境变量账户后缀，支持多账号
ACCOUNT_SUFFIXES = ["", "1", "2", "3"]  # 空字符串代表无后缀的默认账号

# 网络请求重试配置
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 2  # 重试间隔(秒)

# 资产检查配置
SHOW_DETAILS = True  # 是否显示详细信息
MIN_BALANCE_THRESHOLD = 1.0  # 最小余额阈值（USDT），低于此值会高亮显示

# ==========================================

def get_beijing_time():
    """获取北京时间"""
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")


def get_env_var(var_name, suffix=""):
    """获取环境变量或本地配置变量"""
    if IS_DEVELOPMENT:
        # 开发环境：从本地配置文件获取
        try:
            return globals()[f"{var_name}{suffix}"]
        except KeyError:
            return None
    else:
        # 生产环境：从环境变量获取
        return os.getenv(f"{var_name}{suffix}")


def init_api(account_suffix=""):
    """初始化API"""
    suffix = account_suffix if account_suffix else ""
    account_prefix = f"[ACCOUNT-{suffix}]" if suffix else "[ACCOUNT]"
    
    # 获取账户信息
    api_key = get_env_var("OKX_API_KEY", suffix)
    secret_key = get_env_var("OKX_SECRET_KEY", suffix)
    passphrase = get_env_var("OKX_PASSPHRASE", suffix)
    flag = get_env_var("OKX_FLAG", suffix) or "0"
    account_name = get_env_var("OKX_ACCOUNT_NAME", suffix) or f"账户{suffix}" if suffix else "默认账户"
    
    if not all([api_key, secret_key, passphrase]):
        print(f"[{get_beijing_time()}] {account_prefix} [ERROR] 账户信息不完整")
        return None, None, None, account_prefix, account_name
    
    try:
        account_api = Account.AccountAPI(api_key, secret_key, passphrase, False, flag)
        trade_api = Trade.TradeAPI(api_key, secret_key, passphrase, False, flag)
        market_api = MarketData.MarketAPI(api_key, secret_key, passphrase, False, flag)
        print(f"[{get_beijing_time()}] {account_prefix} API初始化成功 - {account_name}")
        return account_api, trade_api, market_api, account_prefix, account_name
    except Exception as err:  # pylint: disable=broad-except
        print(f"[{get_beijing_time()}] {account_prefix} [ERROR] API初始化失败: {str(err)}")
        return None, None, None, account_prefix, account_name


def get_account_balance(account_api, account_prefix=""):
    """获取账户余额"""
    try:
        result = account_api.get_account_balance()
        if result and 'code' in result and result['code'] == '0' and 'data' in result:
            balances = result['data']
            print(f"[{get_beijing_time()}] {account_prefix} [BALANCE] 获取到{len(balances)}个账户余额")
            return balances
        else:
            error_msg = result.get('msg', '') if result else '无响应'
            print(f"[{get_beijing_time()}] {account_prefix} [BALANCE] 获取余额失败: {error_msg}")
            return []
    except Exception as err:  # pylint: disable=broad-except
        print(f"[{get_beijing_time()}] {account_prefix} [BALANCE] 获取余额异常: {str(err)}")
        return []


def get_positions(account_api, account_prefix=""):
    """获取持仓信息"""
    try:
        result = account_api.get_positions()
        if result and 'code' in result and result['code'] == '0' and 'data' in result:
            positions = result['data']
            # 过滤出有持仓的记录
            active_positions = [pos for pos in positions if float(pos.get('pos', '0')) != 0]
            print(f"[{get_beijing_time()}] {account_prefix} [POSITION] 获取到{len(active_positions)}个活跃持仓")
            return active_positions
        else:
            error_msg = result.get('msg', '') if result else '无响应'
            print(f"[{get_beijing_time()}] {account_prefix} [POSITION] 获取持仓失败: {error_msg}")
            return []
    except Exception as err:  # pylint: disable=broad-except
        print(f"[{get_beijing_time()}] {account_prefix} [POSITION] 获取持仓异常: {str(err)}")
        return []


def get_pending_orders(trade_api, account_prefix=""):
    """获取未成交订单"""
    try:
        result = trade_api.get_order_list(state="live")
        if result and 'code' in result and result['code'] == '0' and 'data' in result:
            orders = result['data']
            print(f"[{get_beijing_time()}] {account_prefix} [ORDER] 获取到{len(orders)}个未成交订单")
            return orders
        else:
            error_msg = result.get('msg', '') if result else '无响应'
            print(f"[{get_beijing_time()}] {account_prefix} [ORDER] 获取订单失败: {error_msg}")
            return []
    except Exception as err:  # pylint: disable=broad-except
        print(f"[{get_beijing_time()}] {account_prefix} [ORDER] 获取订单异常: {str(err)}")
        return []


def get_current_price(market_api, inst_id, account_prefix=""):
    """获取当前价格"""
    try:
        result = market_api.get_ticker(instId=inst_id)
        if result and 'code' in result and result['code'] == '0' and 'data' in result:
            ticker = result['data'][0]
            return float(ticker['last'])
        else:
            print(f"[{get_beijing_time()}] {account_prefix} [PRICE] 获取{inst_id}价格失败")
            return None
    except Exception as err:  # pylint: disable=broad-except
        print(f"[{get_beijing_time()}] {account_prefix} [PRICE] 获取{inst_id}价格异常: {str(err)}")
        return None


def format_balance_info(balances, account_prefix=""):
    """格式化余额信息，显示总资产估值（USDT和CNY）和每币种折算"""
    if not balances:
        return "无余额信息"

    # OKX返回的balances是一个列表，通常只有一个元素，里面有totalEq、details等
    main_info = balances[0] if isinstance(balances, list) and balances else balances
    total_usdt = float(main_info.get('totalEq', 0))
    total_cny = float(main_info.get('totalCnyEq', 0)) if 'totalCnyEq' in main_info else None
    details = main_info.get('details', [])

    lines = [f"总资产估值: {total_usdt:.2f} USDT" + (f" / {total_cny:.2f} CNY" if total_cny else "")]
    lines.append("币种明细:")
    for d in details:
        ccy = d.get('ccy', '')
        bal = float(d.get('bal', '0'))
        eq_usd = float(d.get('eqUsd', 0)) if 'eqUsd' in d else 0
        eq_cny = float(d.get('eqCny', 0)) if 'eqCny' in d else 0
        if bal > 0 or eq_usd > 0:
            lines.append(f"  {ccy}: {bal:.4f} ≈ {eq_usd:.2f} USDT / {eq_cny:.2f} CNY")
    return "\n".join(lines)


def format_position_info(positions, account_prefix=""):
    """格式化持仓信息"""
    if not positions:
        return "无持仓"
    
    position_info = []
    total_pnl = 0.0
    
    for pos in positions:
        inst_id = pos.get('instId', '')
        pos_side = pos.get('posSide', '')
        pos_size = float(pos.get('pos', '0'))
        avg_px = float(pos.get('avgPx', '0'))
        upl = float(pos.get('upl', '0'))
        margin = float(pos.get('margin', '0'))
        
        if pos_size != 0:
            total_pnl += upl
            pnl_status = "📈 盈利" if upl > 0 else "📉 亏损" if upl < 0 else "➖ 持平"
            position_info.append(f"  {inst_id} {pos_side}: {pos_size} @ {avg_px:.4f}, PnL: {upl:.2f} USDT {pnl_status}")
    
    if position_info:
        total_status = "📈 总盈利" if total_pnl > 0 else "📉 总亏损" if total_pnl < 0 else "➖ 总持平"
        position_info.insert(0, f"总PnL: {total_pnl:.2f} USDT {total_status}")
    
    return "\n".join(position_info) if position_info else "无持仓"


def format_order_info(orders, account_prefix=""):
    """格式化订单信息"""
    if not orders:
        return "无未成交订单"
    
    order_info = []
    
    for order in orders:
        inst_id = order.get('instId', '')
        side = order.get('side', '')
        pos_side = order.get('posSide', '')
        ord_type = order.get('ordType', '')
        px = order.get('px', '0')
        sz = order.get('sz', '0')
        ord_id = order.get('ordId', '')
        
        order_info.append(f"  {inst_id} {side} {pos_side} {ord_type}: {sz} @ {px} (ID: {ord_id})")
    
    return "\n".join(order_info)


def check_account_assets(account_suffix=""):
    """检查单个账户资产"""
    account_api, trade_api, market_api, account_prefix, account_name = init_api(account_suffix)
    
    if not account_api:
        return None
    
    print(f"\n[{get_beijing_time()}] {account_prefix} 开始检查账户资产")
    
    # 获取余额
    balances = get_account_balance(account_api, account_prefix)
    balance_info = format_balance_info(balances, account_prefix)
    
    # 获取持仓
    positions = get_positions(account_api, account_prefix)
    position_info = format_position_info(positions, account_prefix)
    
    # 获取未成交订单
    orders = get_pending_orders(trade_api, account_prefix)
    order_info = format_order_info(orders, account_prefix)
    
    # 汇总信息
    account_summary = {
        "account_prefix": account_prefix,
        "account_name": account_name,
        "balances": balances,
        "positions": positions,
        "orders": orders,
        "balance_info": balance_info,
        "position_info": position_info,
        "order_info": order_info
    }
    
    # 输出详细信息
    if SHOW_DETAILS:
        print(f"\n{account_prefix} 资产详情:")
        print("=" * 50)
        print("💰 账户余额:")
        print(balance_info)
        print("\n📊 持仓信息:")
        print(position_info)
        print("\n📋 未成交订单:")
        print(order_info)
        print("=" * 50)
    
    return account_summary


def send_summary_notification(all_accounts):
    """发送资产摘要通知"""
    try:
        from notification_service import notification_service
        
        total_accounts = len(all_accounts)
        total_usdt = 0.0
        total_cny = 0.0
        total_pnl = 0.0
        total_orders = 0
        
        # 收集各账户信息
        account_details = []
        
        for account in all_accounts:
            if account:
                account_prefix = account["account_prefix"]
                account_name = account["account_name"]
                
                # 计算总资产估值
                account_usdt = 0.0
                account_cny = 0.0
                if account["balances"]:
                    main_info = account["balances"][0]
                    account_usdt = float(main_info.get('totalEq', 0))
                    account_cny = float(main_info.get('totalCnyEq', 0)) if 'totalCnyEq' in main_info else 0
                
                # 计算总PnL
                account_pnl = sum(float(pos.get('upl', '0')) for pos in account["positions"])
                
                total_usdt += account_usdt
                total_cny += account_cny
                total_pnl += account_pnl
                total_orders += len(account["orders"])
                
                account_details.append({
                    "prefix": account_prefix,
                    "name": account_name,
                    "usdt": account_usdt,
                    "cny": account_cny,
                    "pnl": account_pnl,
                    "positions": account["positions"],
                    "orders": account["orders"]
                })
        
        # 构建通知消息
        title = f"💰 账户资产检查 - {total_accounts}个账户"
        
        message_lines = []
        
        # 1. 账户资产估值
        message_lines.append("📊 账户资产估值:")
        for detail in account_details:
            cny_info = f" / {detail['cny']:.2f} CNY" if detail['cny'] > 0 else ""
            message_lines.append(f"  {detail['prefix']} - {detail['name']}: {detail['usdt']:.2f} USDT{cny_info}")
        message_lines.append(f"  总计: {total_usdt:.2f} USDT" + (f" / {total_cny:.2f} CNY" if total_cny > 0 else ""))
        message_lines.append("")
        
        # 2. 持仓状态
        message_lines.append("📈 持仓状态:")
        has_positions = any(len(detail['positions']) > 0 for detail in account_details)
        if has_positions:
            for detail in account_details:
                if detail['positions']:
                    pnl_status = "📈 盈利" if detail['pnl'] > 0 else "📉 亏损" if detail['pnl'] < 0 else "➖ 持平"
                    message_lines.append(f"  {detail['prefix']} - {detail['name']}: {detail['pnl']:.2f} USDT {pnl_status}")
        else:
            message_lines.append("  无持仓")
        message_lines.append("")
        
        # 3. 未成交订单
        message_lines.append("📋 未成交订单:")
        if total_orders > 0:
            for detail in account_details:
                if detail['orders']:
                    message_lines.append(f"  {detail['prefix']} - {detail['name']}: {len(detail['orders'])}个订单")
        else:
            message_lines.append("  无未成交订单")
        message_lines.append("")
        
        # 4. 检查时间
        message_lines.append(f"⏰ 检查时间: {get_beijing_time()}")
        
        message = "\n".join(message_lines)
        
        notification_service.send_bark_notification(title, message, group="账户资产检查")
        print(f"[{get_beijing_time()}] [NOTIFICATION] 资产摘要通知已发送")
        
    except ImportError:
        print(f"[{get_beijing_time()}] [NOTIFICATION] 通知服务未配置，跳过通知")
    except Exception as err:  # pylint: disable=broad-except
        print(f"[{get_beijing_time()}] [NOTIFICATION] 发送通知失败: {str(err)}")


def get_configured_accounts():
    """获取已配置的账户列表"""
    configured_accounts = []
    
    for suffix in ACCOUNT_SUFFIXES:
        api_key = get_env_var("OKX_API_KEY", suffix)
        secret_key = get_env_var("OKX_SECRET_KEY", suffix)
        passphrase = get_env_var("OKX_PASSPHRASE", suffix)
        
        if all([api_key, secret_key, passphrase]):
            configured_accounts.append(suffix)
    
    return configured_accounts


if __name__ == "__main__":
    print(f"[{get_beijing_time()}] [INFO] 开始OKX账户资产检查")
    
    # 获取已配置的账户
    configured_accounts = get_configured_accounts()
    print(f"[{get_beijing_time()}] [CONFIG] 已配置账户: {configured_accounts}")
    print(f"[{get_beijing_time()}] [CONFIG] 最小余额阈值: {MIN_BALANCE_THRESHOLD} USDT")
    
    if not configured_accounts:
        print(f"[{get_beijing_time()}] [ERROR] 未找到已配置的账户")
        exit(1)
    
    start_time = time.time()
    all_accounts = []
    
    # 检查已配置的账户
    for suffix in configured_accounts:
        account_summary = check_account_assets(suffix)
        all_accounts.append(account_summary)
    
    # 计算总耗时
    total_time = time.time() - start_time
    
    # 输出汇总信息
    print(f"\n[{get_beijing_time()}] [SUMMARY] 资产检查完成")
    print(f"[{get_beijing_time()}] [SUMMARY] 检查耗时: {total_time:.2f}秒")
    
    # 发送摘要通知
    send_summary_notification(all_accounts)
    
    print(f"[{get_beijing_time()}] [INFO] 账户资产检查完成") 