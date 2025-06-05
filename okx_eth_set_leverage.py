"""
任务名称
name: OKX Eth 设置杠杆
定时规则
cron: 0 0 0 * * ?
"""
import os
import json
from datetime import datetime, timezone, timedelta
import okx.Account as Account

def get_beijing_time():
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")

if __name__ == "__main__":
    # 从环境变量获取账户信息
    API_KEY = os.getenv("OKX_API_KEY")
    SECRET_KEY = os.getenv("OKX_SECRET_KEY")
    PASSPHRASE = os.getenv("OKX_PASSPHRASE")
    FLAG = os.getenv("OKX_FLAG", "0")  # 默认实盘

    if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
        print(f"[{get_beijing_time()}] [ERROR] 缺少环境变量: OKX_API_KEY, OKX_SECRET_KEY, OKX_PASSPHRASE")
        exit(1)

    # 初始化账户API
    account_api = Account.AccountAPI(API_KEY, SECRET_KEY, PASSPHRASE, False, FLAG)
    
    instId = "ETH-USDT-SWAP"
    print(f"[{get_beijing_time()}] [INFO] 正在设置{instId}杠杆...")
    
    leverage_result = account_api.set_leverage(
        instId=instId,
        lever="10",
        mgnMode="cross"
    )

    # 输出结果（青龙面板自动捕获日志）
    print(f"[{get_beijing_time()}] [杠杆设置结果] {json.dumps(leverage_result)}")
    
    if leverage_result.get('code') == '0':
        print(f"[{get_beijing_time()}] [SUCCESS] 杠杆设置成功")
    else:
        print(f"[{get_beijing_time()}] [ERROR] 杠杆设置失败: {leverage_result.get('msg')}")
