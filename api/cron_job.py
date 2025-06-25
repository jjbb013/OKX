from app.strategies.eth_strategy import ETHStrategy
from app.strategies.vine_strategy import VineStrategy
import redis
import os
import json
from datetime import datetime

# 从环境变量获取 Redis URL
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
r = redis.from_url(REDIS_URL)

def run_strategies():
    eth_strategy = ETHStrategy()
    vine_strategy = VineStrategy()

    # 运行 ETH 策略
    eth_result = eth_strategy.run()
    # 运行 Vine 策略
    vine_result = vine_strategy.run()

    timestamp = datetime.now().isoformat()
    status_entry = {
        "timestamp": timestamp,
        "eth_status": eth_result,
        "vine_status": vine_result
    }

    # 将运行状态存储到 Redis 列表中，只保留最近3条
    r.lpush('strategy_runs', json.dumps(status_entry))
    r.ltrim('strategy_runs', 0, 2) # Keep only the latest 3 entries

    print(f"Strategies run at {timestamp}. ETH: {eth_result}, Vine: {vine_result}")

    # K线检查逻辑
    kline_data = {
        "timestamp": timestamp,
        "eth_amplitude": eth_strategy.calculate_amplitude(),
        "vine_swing": vine_strategy.check_swing_point(),
        "price_change": eth_strategy.get_price_change()
    }
    r.lpush('kline_checks', json.dumps(kline_data))
    r.ltrim('kline_checks', 0, 4)  # 保留最近5次检查

def handler(event, context):
    run_strategies()
    return {
        'statusCode': 200,
        'body': 'Strategies executed successfully'
    }

if __name__ == '__main__':
    run_strategies()