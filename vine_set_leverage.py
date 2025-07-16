"""
任务名称
name: OKX Vine 设置杠杆
定时规则
cron: 0 0 0 * * ?
"""
import os
import json
import time
from datetime import datetime, timezone, timedelta
import okx.Account as Account

# ============== 可配置参数区域 ==============
# 环境变量账户后缀，支持多账号 (如OKX_API_KEY1, OKX_SECRET_KEY1, OKX_PASSPHRASE1)
ACCOUNT_SUFFIXES = ["", "1", "2", "3"]  # 空字符串代表无后缀的默认账号

# 交易标的参数
INST_ID = "VINE-USDT-SWAP"  # 交易标的
LEVERAGE = 20  # 杠杆倍数
MARGIN_MODE = "cross"  # 保证金模式：cross (全仓) 或 isolated (逐仓)

# 网络请求重试配置
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 2  # 重试间隔(秒)

# ==========================================

def get_beijing_time():
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")

def set_leverage_for_account(account_suffix):
    """为单个账户设置杠杆"""
    # 从环境变量获取账户信息
    suffix = account_suffix if account_suffix else ""  # 空后缀对应默认账户
    prefix = "[ACCOUNT-" + suffix + "]" if suffix else "[ACCOUNT]"
    
    api_key = os.getenv(f"OKX_API_KEY{suffix}")
    secret_key = os.getenv(f"OKX_SECRET_KEY{suffix}")
    passphrase = os.getenv(f"OKX_PASSPHRASE{suffix}")
    flag = os.getenv(f"OKX_FLAG{suffix}", "0")  # 默认实盘
    
    if not all([api_key, secret_key, passphrase]):
        print(f"[{get_beijing_time()}] {prefix} [ERROR] 账户信息不完整或未配置")
        return False
    
    # 初始化账户API
    try:
        account_api = Account.AccountAPI(api_key, secret_key, passphrase, False, flag)
        print(f"[{get_beijing_time()}] {prefix} API初始化成功")
    except Exception as e:
        print(f"[{get_beijing_time()}] {prefix} [ERROR] API初始化失败: {str(e)}")
        return False
    
    # 设置杠杆
    for attempt in range(MAX_RETRIES + 1):
        try:
            print(f"[{get_beijing_time()}] {prefix} [INFO] 正在设置{INST_ID}杠杆为{LEVERAGE}倍...")
            
            leverage_result = account_api.set_leverage(
                instId=INST_ID,
                lever=str(LEVERAGE),
                mgnMode=MARGIN_MODE
            )
            
            # 输出结果
            print(f"[{get_beijing_time()}] {prefix} [杠杆设置结果] {json.dumps(leverage_result)}")
            
            if leverage_result.get('code') == '0':
                print(f"[{get_beijing_time()}] {prefix} [SUCCESS] 杠杆设置成功")
                return True
            else:
                error_msg = leverage_result.get('msg', '未知错误')
                print(f"[{get_beijing_time()}] {prefix} [ERROR] 杠杆设置失败: {error_msg}")
                
                # 如果是最后一次尝试，返回失败
                if attempt == MAX_RETRIES:
                    return False
        except Exception as e:
            print(f"[{get_beijing_time()}] {prefix} [ERROR] 设置杠杆异常 (尝试 {attempt+1}/{MAX_RETRIES+1}): {str(e)}")
            
            # 如果是最后一次尝试，返回失败
            if attempt == MAX_RETRIES:
                return False
        
        # 如果不是最后一次尝试，等待后重试
        if attempt < MAX_RETRIES:
            print(f"[{get_beijing_time()}] {prefix} [INFO] 重试中... ({attempt+1}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY)
    
    return False

if __name__ == "__main__":
    print(f"[{get_beijing_time()}] [INFO] 开始为所有账户设置杠杆")
    
    # 遍历所有账户设置杠杆
    for suffix in ACCOUNT_SUFFIXES:
        success = set_leverage_for_account(suffix)
        
        # 发送通知（可选）
        if success:
            print(f"[{get_beijing_time()}] [ACCOUNT-{suffix}] 杠杆设置成功")
        else:
            print(f"[{get_beijing_time()}] [ACCOUNT-{suffix}] 杠杆设置失败")
    
    print(f"[{get_beijing_time()}] [INFO] 所有账户杠杆设置完成")
