"""
任务名称
name: OKX 多账户API测试（批量创建+批量撤销）
定时规则
cron: 1 1 1 1 *
"""
import os
import json
import time
from datetime import datetime, timezone, timedelta
import okx.MarketData as MarketData
import okx.Trade as Trade

# ============== 可配置参数区域 ==============
# 环境变量账户后缀，支持多账号 (如OKX_API_KEY1, OKX_SECRET_KEY1, OKX_PASSPHRASE1)
ACCOUNT_SUFFIXES = ["", "1"]  # 空字符串代表无后缀的默认账号

# 测试订单参数
TEST_INST_ID = "ETH-USDT-SWAP"  # 测试交易标的
TEST_PRICE = 0.01  # 测试订单价格（远离市场价，不会成交）
TEST_SIZE = 10  # 测试订单数量（张）
TEST_SIDE = "buy"  # 买入方向
TEST_POS_SIDE = "long"  # 做多
WAIT_SECONDS = 60  # 订单创建后等待时间（秒）

# 网络请求重试配置
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 2  # 重试间隔(秒)

# ==========================================

def get_beijing_time():
    """获取北京时间"""
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")

def create_test_order(trade_api, account_prefix):
    """为单个账户创建测试订单"""
    # 创建测试订单
    order_params = {
        "instId": TEST_INST_ID,
        "tdMode": "cross",
        "side": TEST_SIDE,
        "ordType": "limit",
        "px": str(TEST_PRICE),
        "sz": str(TEST_SIZE),
        "posSide": TEST_POS_SIDE
    }
    
    print(f"[{get_beijing_time()}] {account_prefix} [CREATE] 创建测试订单: {json.dumps(order_params)}")
    
    for attempt in range(MAX_RETRIES + 1):
        try:
            order_result = trade_api.place_order(**order_params)
            print(f"[{get_beijing_time()}] {account_prefix} [CREATE] 订单创建结果: {json.dumps(order_result)}")
            
            if order_result and 'code' in order_result and order_result['code'] == '0':
                ord_id = order_result['data'][0]['ordId']
                print(f"[{get_beijing_time()}] {account_prefix} [SUCCESS] 测试订单创建成功, ordId={ord_id}")
                return True, ord_id, None
            else:
                error_msg = order_result.get('msg', '未知错误') if order_result else '无响应'
                print(f"[{get_beijing_time()}] {account_prefix} [ERROR] 创建订单失败: {error_msg}")
                return False, None, f"订单创建失败: {error_msg}"
        except Exception as e:
            error_msg = f"创建订单异常 (尝试 {attempt+1}/{MAX_RETRIES+1}): {str(e)}"
            print(f"[{get_beijing_time()}] {account_prefix} [ERROR] {error_msg}")
            if attempt < MAX_RETRIES:
                print(f"[{get_beijing_time()}] {account_prefix} [CREATE] 重试中... ({attempt+1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
            else:
                return False, None, error_msg
    
    return False, None, "未知错误"

def cancel_test_order(trade_api, account_prefix, ord_id):
    """为单个账户撤销测试订单"""
    print(f"[{get_beijing_time()}] {account_prefix} [CANCEL] 撤销测试订单: ordId={ord_id}")
    
    for cancel_attempt in range(MAX_RETRIES + 1):
        try:
            cancel_result = trade_api.cancel_order(instId=TEST_INST_ID, ordId=ord_id)
            print(f"[{get_beijing_time()}] {account_prefix} [CANCEL] 撤单结果: {json.dumps(cancel_result)}")
            
            if cancel_result and 'code' in cancel_result and cancel_result['code'] == '0':
                print(f"[{get_beijing_time()}] {account_prefix} [SUCCESS] 测试订单撤销成功")
                return True, "订单撤销成功"
            else:
                error_msg = cancel_result.get('msg', '未知错误') if cancel_result else '无响应'
                print(f"[{get_beijing_time()}] {account_prefix} [ERROR] 撤销订单失败: {error_msg}")
                return False, f"订单撤销失败: {error_msg}"
        except Exception as e:
            error_msg = f"撤销订单异常 (尝试 {cancel_attempt+1}/{MAX_RETRIES+1}): {str(e)}"
            print(f"[{get_beijing_time()}] {account_prefix} [ERROR] {error_msg}")
            if cancel_attempt < MAX_RETRIES:
                print(f"[{get_beijing_time()}] {account_prefix} [CANCEL] 重试中... ({cancel_attempt+1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
            else:
                return False, error_msg
    
    return False, "未知错误"

def send_test_summary(results):
    """发送测试结果摘要"""
    success_count = sum(1 for _, success, _ in results if success)
    total_count = len(results)
    
    title = f"API测试结果: {success_count}/{total_count} 成功"
    message = "OKX账户API测试结果:\n\n"
    
    for account, success, detail in results:
        status = "✅ 成功" if success else "❌ 失败"
        message += f"账户: {account}\n状态: {status}\n详情: {detail}\n\n"
    
    message += f"总账户数: {total_count}\n成功账户数: {success_count}\n失败账户数: {total_count - success_count}"
    
    print(f"[{get_beijing_time()}] [SUMMARY] {message}")
    
    # 在实际环境中，这里可以添加发送通知的代码（如邮件、Bark等）
    # send_notification(title, message)

if __name__ == "__main__":
    print(f"[{get_beijing_time()}] [INFO] 开始OKX多账户API测试")
    print(f"[{get_beijing_time()}] [CONFIG] 测试标: {TEST_INST_ID}")
    print(f"[{get_beijing_time()}] [CONFIG] 测试价格: {TEST_PRICE}")
    print(f"[{get_beijing_time()}] [CONFIG] 测试数量: {TEST_SIZE}")
    print(f"[{get_beijing_time()}] [CONFIG] 等待时间: {WAIT_SECONDS}秒")
    
    test_results = []
    start_time = time.time()
    
    # 存储账户信息和订单ID
    account_orders = []
    
    # 第一阶段：为所有账户创建测试订单
    print(f"\n[{get_beijing_time()}] [PHASE 1] 开始为所有账户创建测试订单")
    
    for suffix in ACCOUNT_SUFFIXES:
        # 准备账户标识
        suffix_str = suffix if suffix else ""  # 空后缀对应默认账户
        prefix = "[ACCOUNT-" + suffix_str + "]" if suffix_str else "[ACCOUNT]"
        
        # 从环境变量获取账户信息
        api_key = os.getenv(f"OKX_API_KEY{suffix_str}")
        secret_key = os.getenv(f"OKX_SECRET_KEY{suffix_str}")
        passphrase = os.getenv(f"OKX_PASSPHRASE{suffix_str}")
        flag = os.getenv(f"OKX_FLAG{suffix_str}", "0")  # 默认实盘
        
        account_name = f"账户-{suffix_str}" if suffix_str else "默认账户"
        
        if not all([api_key, secret_key, passphrase]):
            print(f"[{get_beijing_time()}] {prefix} [ERROR] 账户信息不完整或未配置")
            test_results.append((account_name, False, "账户信息不完整"))
            continue
        
        # 初始化API
        try:
            # 确保所有参数都不为None
            if api_key is None or secret_key is None or passphrase is None:
                raise ValueError("API密钥、密钥或密码不能为空")
            
            trade_api = Trade.TradeAPI(api_key, secret_key, passphrase, False, flag)
            print(f"[{get_beijing_time()}] {prefix} API初始化成功")
        except Exception as e:
            error_msg = f"API初始化失败: {str(e)}"
            print(f"[{get_beijing_time()}] {prefix} [ERROR] {error_msg}")
            test_results.append((account_name, False, error_msg))
            continue
        
        # 创建测试订单
        success, ord_id, error_msg = create_test_order(trade_api, prefix)
        
        if success:
            account_orders.append({
                "account_name": account_name,
                "prefix": prefix,
                "trade_api": trade_api,
                "ord_id": ord_id
            })
            test_results.append((account_name, True, "订单创建成功"))
        else:
            test_results.append((account_name, False, error_msg))
    
    # 等待1分钟
    print(f"\n[{get_beijing_time()}] [WAITING] 所有账户订单已创建，等待{WAIT_SECONDS}秒...")
    
    for i in range(WAIT_SECONDS):
        time.sleep(1)
        if (i + 1) % 10 == 0:  # 每10秒打印一次状态
            print(f"[{get_beijing_time()}] [WAITING] 已等待 {i+1} 秒...")
    
    print(f"[{get_beijing_time()}] [WAITING] 等待完成，开始撤销订单")
    
    # 第二阶段：为所有账户撤销测试订单
    print(f"\n[{get_beijing_time()}] [PHASE 2] 开始为所有账户撤销测试订单")
    
    for order_info in account_orders:
        account_name = order_info["account_name"]
        prefix = order_info["prefix"]
        trade_api = order_info["trade_api"]
        ord_id = order_info["ord_id"]
        
        # 撤销订单
        success, error_msg = cancel_test_order(trade_api, prefix, ord_id)
        
        # 更新测试结果
        for i, (name, success_old, detail_old) in enumerate(test_results):
            if name == account_name and success_old:
                if success:
                    test_results[i] = (name, True, "订单创建并成功撤销")
                else:
                    test_results[i] = (name, True, f"订单创建成功但撤销失败: {error_msg}")
    
    # 计算测试耗时
    total_time = time.time() - start_time
    mins, secs = divmod(total_time, 60)
    
    # 打印测试摘要
    print(f"\n[{get_beijing_time()}] [INFO] 所有账户测试完成")
    print(f"[{get_beijing_time()}] [INFO] 测试总耗时: {int(mins)}分 {int(secs)}秒")
    print(f"[{get_beijing_time()}] [INFO] 测试结果摘要:")
    
    success_count = sum(1 for _, success, _ in test_results if success)
    for account, success, detail in test_results:
        status = "成功 ✅" if success else "失败 ❌"
        print(f"  {account}: {status} - {detail}")
    
    print(f"\n[{get_beijing_time()}] [SUMMARY] 成功账户数: {success_count}/{len(ACCOUNT_SUFFIXES)}")
    
    # 发送测试摘要（实际使用时取消注释）
    # send_test_summary(test_results)
    
    print(f"[{get_beijing_time()}] [INFO] API测试完成")
