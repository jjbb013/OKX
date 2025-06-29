#!/usr/bin/env python3
"""
测试修复后的OKX交易策略脚本
"""
import os
import sys

# 设置测试环境变量
os.environ['OKX_API_KEY'] = 'test_api_key'
os.environ['OKX_SECRET_KEY'] = 'test_secret_key'
os.environ['OKX_PASSPHRASE'] = 'test_passphrase'
os.environ['OKX_FLAG'] = '0'

# 导入修复后的脚本
try:
    from okx_vine_trading_strategy import get_env_var, get_beijing_time
    print("✅ 成功导入修复后的脚本")
    
    # 测试get_env_var函数
    api_key = get_env_var("OKX_API_KEY")
    secret_key = get_env_var("OKX_SECRET_KEY")
    passphrase = get_env_var("OKX_PASSPHRASE")
    flag = get_env_var("OKX_FLAG", "", "0")
    
    print(f"✅ API密钥获取成功:")
    print(f"   API_KEY: {api_key}")
    print(f"   SECRET_KEY: {secret_key}")
    print(f"   PASSPHRASE: {passphrase}")
    print(f"   FLAG: {flag}")
    
    # 测试类型检查
    if all(isinstance(x, str) for x in [api_key, secret_key, passphrase, flag]):
        print("✅ 所有API参数都是字符串类型")
    else:
        print("❌ API参数类型检查失败")
    
    print(f"✅ 北京时间: {get_beijing_time()}")
    
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ 测试失败: {e}")
    sys.exit(1)

print("🎉 所有测试通过！") 