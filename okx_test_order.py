"""
任务名称
name: OKX 多账户API测试（含延迟撤销）
定时规则
cron: 0 0 0 * * ?  # 每天运行一次
"""
import os
import json
import time
from datetime import datetime, timezone, timedelta
import okx.MarketData as MarketData
import okx.Trade as Trade

# ============== 可配置参数区域 ==============
# 环境变量账户后缀，支持多账号 (如OKX_API_KEY1, OKX_SECRET_KEY1, OKX_PASSPHRASE1)
ACCOUNT_SUFFIXES = ["", "1", "2", "3"]  # 空字符串代表无后缀的默认账号

# 测试订单参数
TEST_INST_ID = "ETH-USDT-SWAP"  # 测试交易标的
TEST_PRICE = 0.01  # 测试订单价格（远离市场价，不会成交）
TEST_SIZE = 10  # 测试订单数量（张）
TEST_SIDE = "buy"  # 买入方向
TEST_POS_SIDE = "long"  # 做多
WAIT_SECONDS = 60  # 订单创建后等待时间（秒）
WAIT_ATTEMPTS = 60  # 最大等待检查次数（等待1分钟）
WAIT_INTERVAL = 1   # 等待间隔（秒）

# 网络请求重试配置
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 2  # 重试间隔(秒)

# ==========================================

def get_beijing_time():
    """获取北京时间"""
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")

def test_account_api(account_suffix):
    """测试单个账户的API功能"""
    # 准备账户标识
    suffix = account_suffix if account_suffix else ""  # 空后缀对应默认账户
    prefix = "[ACCOUNT-" + suffix + "]" if suffix else "[ACCOUNT]"
    
    # 从环境变量获取账户信息
    api_key = os.getenv(f"OKX_API_KEY{suffix}")
    secret_key = os.getenv(f"OKX_SECRET_KEY{suffix}")
    passphrase = os.getenv(f"OKX_PASSPHRASE{suffix}")
    flag = os.getenv(f"OKX_FLAG{suffix}", "0")  # 默认实盘
    
    if not all([api_key, secret_key, passphrase]):
        print(f"[{get_beijing_time()}] {prefix} [ERROR] 账户信息不完整或未配置")
        return False, "账户信息不完整"
    
    # 初始化API
    try:
        trade_api = Trade.TradeAPI(api_key, secret_key, passphrase, False, flag)
        print(f"[{get_beijing_time()}] {prefix} API初始化成功")
    except Exception as e:
        error_msg = f"API初始化失败: {str(e)}"
        print(f"[{get_beijing_time()}] {prefix} [ERROR] {error_msg}")
        return False, error_msg
    
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
    
    print(f"[{get_beijing_time()}] {prefix} [TEST] 创建测试订单: {json.dumps(order_params)}")
    
    order_result = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            order_result = trade_api.place_order(**order_params)
            print(f"[{get_beijing_time()}] {prefix} [TEST] 订单创建结果: {json.dumps(order_result)}")
            break
        except Exception as e:
            error_msg = f"创建订单异常 (尝试 {attempt+1}/{MAX_RETRIES+1}): {str(e)}"
            print(f"[{get_beijing_time()}] {prefix} [ERROR] {error_msg}")
            if attempt < MAX_RETRIES:
                print(f"[{get_beijing_time()}] {prefix} [TEST] 重试中... ({attempt+1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
            else:
                return False, error_msg
    
    # 检查订单创建结果
    if order_result and 'code' in order_result and order_result['code'] == '0':
        ord_id = order_result['data'][0]['ordId']
        print(f"[{get_beijing_time()}] {prefix} [SUCCESS] 测试订单创建成功, ordId={ord_id}")
        
        # 等待1分钟后撤销订单
        print(f"[{get_beijing_time()}] {prefix} [TEST] 等待{WAIT_SECONDS}秒后撤销订单...")
        
        # 等待期间检查订单状态
        for i in range(WAIT_ATTEMPTS):
            time.sleep(WAIT_INTERVAL)
            if (i + 1) % 10 == 0:  # 每10秒打印一次状态
                print(f"[{get_beijing_time()}] {prefix} [TEST] 已等待 {i+1} 秒...")
        
        # 撤销测试订单
        print(f"[{get_beijing_time()}] {prefix} [TEST] 撤销测试订单: ordId={ord_id}")
        cancel_result = None
        
        for cancel_attempt in range(MAX_RETRIES + 1):
            try:
                cancel_result = trade_api.cancel_order(instId=TEST_INST_ID, ordId=ord_id)
                print(f"[{get_beijing_time()}] {prefix} [TEST] 撤单结果: {json.dumps(cancel_result)}")
                
                if cancel_result and 'code' in cancel_result and cancel_result['code'] == '0':
                    print(f"[{get_beijing_time()}] {prefix} [SUCCESS] 测试订单撤销成功")
                    return True, "订单创建并成功撤销"
                else:
                    error_msg = cancel_result.get('msg', '未知错误') if cancel_result else '无响应'
                    print(f"[{get_beijing_time()}] {prefix} [ERROR] 撤销订单失败: {error_msg}")
                    
                    if cancel_attempt < MAX_RETRIES:
                        print(f"[{get_beijing_time()}] {prefix} [TEST] 撤单重试中... ({cancel_attempt+1}/{MAX_RETRIES})")
                        time.sleep(RETRY_DELAY)
                    else:
                        return True, f"订单创建成功但撤销失败: {error_msg}"
            
            except Exception as e:
                error_msg = f"撤销订单异常 (尝试 {cancel_attempt+1}/{MAX_RETRIES+1}): {str(e)}"
                print(f"[{get_beijing_time()}] {prefix} [ERROR] {error_msg}")
                
                if cancel_attempt < MAX_RETRIES:
                    print(f"[{get_beijing_time()}] {prefix} [TEST] 撤单重试中... ({cancel_attempt+1}/{MAX_RETRIES})")
                    time.sleep(RETRY_DELAY)
                else:
                    return True, f"订单创建成功但撤销异常: {error_msg}"
    
    else:
        error_msg = order_result.get('msg', '未知错误') if order_result else '无响应'
        print(f"[{get_beijing_time()}] {prefix} [ERROR] 创建订单失败: {error_msg}")
        return False, f"订单创建失败: {error_msg}"

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
    
    # 遍历所有账户进行测试
    for i, suffix in enumerate(ACCOUNT_SUFFIXES):
        account_name = f"账户-{suffix}" if suffix else "默认账户"
        print(f"\n[{get_beijing_time()}] [TEST] 开始测试账户 ({i+1}/{len(ACCOUNT_SUFFIXES)}): {account_name}")
        
        success, detail = test_account_api(suffix)
        test_results.append((account_name, success, detail))
        
        # 账户间测试间隔
        if i < len(ACCOUNT_SUFFIXES) - 1:
            print(f"[{get_beijing_time()}] [TEST] 等待5秒后测试下一个账户...")
            time.sleep(5)
    
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
