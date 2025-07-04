"""
任务名称
name: OKX 紧急平仓工具
定时规则
cron: 0 0 1 1 0 
"""
import os
import json
import time
from datetime import datetime, timezone, timedelta
import okx.Account as Account
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

# 需要紧急平仓的交易标的列表
EMERGENCY_INST_IDS = [
    "VINE-USDT-SWAP",
    "ETH-USDT-SWAP",
    "TRUMP-USDT-SWAP",
    "ADA-USDT-SWAP"
    # 可以添加更多需要平仓的交易标的
]

# 网络请求重试配置
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 2  # 重试间隔(秒)

# 平仓方式：market(市价平仓) 或 limit(限价平仓)
CLOSE_TYPE = "market"  # 建议使用市价平仓以确保快速成交

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


def get_positions(account_api, inst_id, account_prefix=""):
    """获取指定交易标的的所有仓位"""
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = account_api.get_positions(instId=inst_id)
            
            if result and 'code' in result and result['code'] == '0' and 'data' in result:
                positions = result['data']
                # 过滤出有持仓的记录
                active_positions = [pos for pos in positions if float(pos.get('pos', '0') or '0') != 0]
                print(f"[{get_beijing_time()}] {account_prefix} [POSITION] {inst_id} 获取到{len(active_positions)}个活跃仓位")
                return active_positions
            else:
                error_msg = result.get('msg', '') if result else '无响应'
                print(f"[{get_beijing_time()}] {account_prefix} [POSITION] 获取{inst_id}仓位失败: {error_msg}")
        except Exception as e:
            print(f"[{get_beijing_time()}] {account_prefix} [POSITION] 获取{inst_id}仓位异常 (尝试 {attempt+1}/{MAX_RETRIES+1}): {str(e)}")
            
        if attempt < MAX_RETRIES:
            print(f"[{get_beijing_time()}] {account_prefix} [POSITION] 重试中... ({attempt+1}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
    
    print(f"[{get_beijing_time()}] {account_prefix} [POSITION] 获取{inst_id}仓位失败")
    return []


def close_position(trade_api, inst_id, position, account_prefix=""):
    """平仓单个仓位"""
    try:
        # 获取仓位信息
        pos_side = position.get('posSide', '')  # long 或 short
        pos_size = float(position.get('pos', '0') or '0')  # 持仓数量
        
        if pos_size == 0:
            print(f"[{get_beijing_time()}] {account_prefix} [CLOSE] {inst_id} {pos_side} 仓位数量为0，跳过")
            return True, "仓位数量为0"
        
        # 确定平仓方向
        if pos_side == 'long':
            # 多头仓位需要卖出平仓
            side = 'sell'
        elif pos_side == 'short':
            # 空头仓位需要买入平仓
            side = 'buy'
        else:
            print(f"[{get_beijing_time()}] {account_prefix} [CLOSE] {inst_id} 仓位方向不明确: {pos_side}")
            return False, "仓位方向不明确"
        
        # 构建平仓参数
        close_params = {
            "instId": inst_id,
            "tdMode": "cross",
            "side": side,
            "posSide": pos_side,
            "sz": str(pos_size)
        }
        
        # 根据平仓方式设置参数
        if CLOSE_TYPE == "market":
            close_params["ordType"] = "market"
            print(f"[{get_beijing_time()}] {account_prefix} [CLOSE] 市价平仓 {inst_id} {pos_side} {pos_size}")
        else:
            # 限价平仓需要获取当前价格
            close_params["ordType"] = "limit"
            # 这里可以添加获取当前价格的逻辑，暂时使用市价
            close_params["ordType"] = "market"
            print(f"[{get_beijing_time()}] {account_prefix} [CLOSE] 限价平仓 {inst_id} {pos_side} {pos_size}")
        
        # 执行平仓
        for attempt in range(MAX_RETRIES + 1):
            try:
                result = trade_api.place_order(**close_params)
                
                if result and 'code' in result and result['code'] == '0':
                    print(f"[{get_beijing_time()}] {account_prefix} [CLOSE] {inst_id} {pos_side} 平仓成功")
                    return True, "平仓成功"
                else:
                    error_msg = result.get('msg', '') if result else '无响应'
                    print(f"[{get_beijing_time()}] {account_prefix} [CLOSE] {inst_id} {pos_side} 平仓失败: {error_msg}")
            except Exception as e:
                print(f"[{get_beijing_time()}] {account_prefix} [CLOSE] {inst_id} {pos_side} 平仓异常 (尝试 {attempt+1}/{MAX_RETRIES+1}): {str(e)}")
                
            if attempt < MAX_RETRIES:
                print(f"[{get_beijing_time()}] {account_prefix} [CLOSE] 重试中... ({attempt+1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
        
        print(f"[{get_beijing_time()}] {account_prefix} [CLOSE] {inst_id} {pos_side} 平仓失败")
        return False, "平仓失败"
        
    except Exception as e:
        print(f"[{get_beijing_time()}] {account_prefix} [CLOSE] 平仓{inst_id}时异常: {str(e)}")
        return False, f"平仓异常: {str(e)}"


def process_account_emergency_close(account_suffix):
    """处理单个账户的紧急平仓"""
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
            "closed_count": 0,
            "total_positions": 0
        }
    
    # 初始化API
    try:
        # 确保所有参数都是字符串类型
        api_key_str = str(api_key) if api_key else ""
        secret_key_str = str(secret_key) if secret_key else ""
        passphrase_str = str(passphrase) if passphrase else ""
        flag_str = str(flag) if flag else "0"
        
        account_api = Account.AccountAPI(api_key_str, secret_key_str, passphrase_str, False, flag_str)
        trade_api = Trade.TradeAPI(api_key_str, secret_key_str, passphrase_str, False, flag_str)
        print(f"[{get_beijing_time()}] {prefix} API初始化成功 - {account_name}")
    except Exception as e:
        error_msg = f"API初始化失败: {str(e)}"
        print(f"[{get_beijing_time()}] {prefix} [ERROR] {error_msg}")
        return {
            "account_name": account_name,
            "success": False,
            "error": error_msg,
            "closed_count": 0,
            "total_positions": 0
        }
    
    # 统计信息
    total_positions = 0
    closed_positions = []
    closed_count = 0
    
    # 遍历所有需要平仓的交易标的
    for inst_id in EMERGENCY_INST_IDS:
        print(f"[{get_beijing_time()}] {prefix} [EMERGENCY] 开始检查 {inst_id} 仓位")
        
        # 获取仓位
        positions = get_positions(account_api, inst_id, prefix)
        if not positions:
            print(f"[{get_beijing_time()}] {prefix} [EMERGENCY] {inst_id} 无持仓")
            continue
        
        total_positions += len(positions)
        
        # 平仓每个仓位
        for position in positions:
            pos_side = position.get('posSide', '')
            pos_size = float(position.get('pos', '0') or '0')
            avg_px = float(position.get('avgPx', '0') or '0')
            upl = float(position.get('upl', '0') or '0')
            
            print(f"[{get_beijing_time()}] {prefix} [EMERGENCY] 准备平仓: {inst_id} {pos_side} {pos_size} @ {avg_px:.4f} PnL: {upl:.2f}")
            
            # 执行平仓
            success, close_msg = close_position(trade_api, inst_id, position, prefix)
            
            if success:
                closed_count += 1
                closed_positions.append({
                    "inst_id": inst_id,
                    "pos_side": pos_side,
                    "pos_size": pos_size,
                    "avg_price": avg_px,
                    "pnl": upl,
                    "close_msg": close_msg
                })
                
                # 发送平仓通知
                notification_service.send_bark_notification(
                    f"{prefix} 紧急平仓成功",
                    f"标的: {inst_id}\n"
                    f"方向: {pos_side}\n"
                    f"数量: {pos_size}\n"
                    f"均价: {avg_px:.4f}\n"
                    f"盈亏: {upl:.2f} USDT\n"
                    f"平仓方式: {CLOSE_TYPE}",
                    group="OKX紧急平仓通知"
                )
            else:
                print(f"[{get_beijing_time()}] {prefix} [ERROR] {inst_id} {pos_side} 平仓失败: {close_msg}")
                
                # 发送失败通知
                notification_service.send_bark_notification(
                    f"{prefix} 紧急平仓失败",
                    f"标的: {inst_id}\n"
                    f"方向: {pos_side}\n"
                    f"数量: {pos_size}\n"
                    f"错误: {close_msg}",
                    group="OKX紧急平仓通知"
                )
    
    return {
        "account_name": account_name,
        "success": True,
        "error": None,
        "closed_count": closed_count,
        "total_positions": total_positions,
        "closed_positions": closed_positions
    }


def send_emergency_summary_notification(results):
    """发送紧急平仓结果摘要"""
    total_accounts = len(results)
    success_accounts = sum(1 for r in results if r['success'])
    total_closed = sum(r['closed_count'] for r in results)
    total_positions = sum(r['total_positions'] for r in results)
    
    title = f"🚨 紧急平仓完成: {total_closed}个仓位已平仓"
    message = f"平仓时间: {get_beijing_time()}\n"
    message += f"平仓方式: {CLOSE_TYPE}\n"
    message += f"平仓标的: {', '.join(EMERGENCY_INST_IDS)}\n\n"
    
    for result in results:
        status = "✅ 成功" if result['success'] else "❌ 失败"
        message += f"账户: {result['account_name']}\n"
        message += f"状态: {status}\n"
        if result['success']:
            message += f"总仓位数: {result['total_positions']}\n"
            message += f"平仓数量: {result['closed_count']}\n"
        else:
            message += f"错误: {result['error']}\n"
        message += "\n"
    
    message += f"总账户数: {total_accounts}\n"
    message += f"成功账户数: {success_accounts}\n"
    message += f"总平仓数量: {total_closed}\n"
    message += f"总检查仓位数: {total_positions}"
    
    print(f"[{get_beijing_time()}] [EMERGENCY_SUMMARY] {message}")
    notification_service.send_bark_notification(title, message, group="OKX紧急平仓通知")


if __name__ == "__main__":
    print(f"[{get_beijing_time()}] [EMERGENCY] 🚨 开始OKX紧急平仓操作")
    print(f"[{get_beijing_time()}] [EMERGENCY] 平仓标的: {', '.join(EMERGENCY_INST_IDS)}")
    print(f"[{get_beijing_time()}] [EMERGENCY] 平仓方式: {CLOSE_TYPE}")
    
    # 确认操作
    print(f"[{get_beijing_time()}] [EMERGENCY] ⚠️  警告：即将对所有指定标的进行紧急平仓！")
    print(f"[{get_beijing_time()}] [EMERGENCY] 请确认是否继续...")
    
    # 这里可以添加用户确认逻辑，暂时直接执行
    # confirm = input("输入 'YES' 确认执行紧急平仓: ")
    # if confirm != 'YES':
    #     print("操作已取消")
    #     exit(0)
    
    start_time = time.time()
    results = []
    
    # 处理所有账户
    for suffix in ACCOUNT_SUFFIXES:
        print(f"\n[{get_beijing_time()}] [EMERGENCY] 开始处理账户: {suffix if suffix else '默认'}")
        result = process_account_emergency_close(suffix)
        results.append(result)
    
    # 计算总耗时
    total_time = time.time() - start_time
    mins, secs = divmod(total_time, 60)
    
    # 打印结果摘要
    print(f"\n[{get_beijing_time()}] [EMERGENCY] 所有账户紧急平仓完成")
    print(f"[{get_beijing_time()}] [EMERGENCY] 操作总耗时: {int(mins)}分 {int(secs)}秒")
    
    total_closed = sum(r['closed_count'] for r in results)
    total_positions = sum(r['total_positions'] for r in results)
    
    print(f"[{get_beijing_time()}] [EMERGENCY_SUMMARY] 总检查仓位数: {total_positions}")
    print(f"[{get_beijing_time()}] [EMERGENCY_SUMMARY] 总平仓数量: {total_closed}")
    
    # 发送摘要通知
    send_emergency_summary_notification(results)
    
    print(f"[{get_beijing_time()}] [EMERGENCY] 🚨 紧急平仓操作完成") 
