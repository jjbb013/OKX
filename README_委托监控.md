# OKX 委托订单监控与撤销程序

## 功能说明

这个程序用于自动监控OKX账户中的未成交委托订单，并根据当前市场价格自动撤销符合条件的订单：

- **做多订单**：当当前价格超过委托价格时，自动撤销订单
- **做空订单**：当当前价格低于委托价格时，自动撤销订单

## 主要特性

1. **多账户支持**：支持监控多个OKX账户
2. **多交易标的管理**：可同时监控多个交易标的（如ETH、BTC等）
3. **智能价格判断**：包含价格容差机制，避免因微小价格波动导致的误判
4. **实时通知**：通过Bark发送撤销通知和监控摘要
5. **错误重试机制**：网络请求失败时自动重试
6. **详细日志记录**：完整的操作日志，便于问题排查

## 配置说明

### 1. 环境变量配置

在青龙面板中配置以下环境变量：

```bash
# 默认账户
OKX_API_KEY=您的API密钥
OKX_SECRET_KEY=您的密钥
OKX_PASSPHRASE=您的密码
OKX_FLAG=0  # 0=实盘, 1=模拟盘

# 第二个账户（可选）
OKX_API_KEY1=第二个账户的API密钥
OKX_SECRET_KEY1=第二个账户的密钥
OKX_PASSPHRASE1=第二个账户的密码
OKX_FLAG1=0

# 第三个账户（可选）
OKX_API_KEY2=第三个账户的API密钥
OKX_SECRET_KEY2=第三个账户的密钥
OKX_PASSPHRASE2=第三个账户的密码
OKX_FLAG2=0

# 第四个账户（可选）
OKX_API_KEY3=第三个账户的API密钥
OKX_SECRET_KEY3=第三个账户的密钥
OKX_PASSPHRASE3=第三个账户的密码
OKX_FLAG3=0

# Bark通知配置（可选）
BARK_KEY=您的Bark推送地址
BARK_GROUP=OKX委托监控
```

### 2. 程序参数配置

在 `okx_order_monitor.py` 文件中可以修改以下参数：

```python
# 账户后缀配置
ACCOUNT_SUFFIXES = ["", "1", "2", "3"]  # 支持4个账户

# 监控的交易标的
MONITOR_INST_IDS = [
    "ETH-USDT-SWAP",
    "VINE-USDT-SWAP",
    # 可以添加更多交易标的
]

# 价格容差（避免误判）
PRICE_TOLERANCE = 0.0001  # 0.01%的容差

# 网络请求重试配置
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 2  # 重试间隔(秒)
```

## 青龙面板配置

### 1. 添加脚本

将 `okx_order_monitor.py` 文件上传到青龙面板的脚本目录。

### 2. 配置定时任务

在青龙面板中添加定时任务：

- **任务名称**：OKX 委托订单监控与撤销
- **定时规则**：`*/10 * * * *` （每10分钟执行一次）
- **脚本路径**：`okx_order_monitor.py`

### 3. 安装依赖

确保青龙面板已安装 `okx` 模块：

```bash
pip install okx
```

## 工作原理

### 1. 订单监控流程

1. 遍历所有配置的账户
2. 对每个账户，遍历所有监控的交易标的
3. 获取当前市场价格
4. 获取该标的的所有未成交订单
5. 逐个检查订单是否需要撤销

### 2. 撤销条件判断

- **做多订单**（buy + long）：
  - 当前价格 > 止盈价格 × (1 + 容差) 时撤销
  
- **做空订单**（sell + short）：
  - 当前价格 < 止盈价格 × (1 - 容差) 时撤销

**注意**：程序会检查订单的 `linkedAlgoOrd.tpTriggerPx` 字段获取止盈价格，如果订单无止盈价格信息则跳过该订单。

### 3. 通知机制

- **单个订单撤销通知**：每次撤销订单时发送详细通知
- **监控摘要通知**：**仅在撤销订单时**发送统计摘要，无撤销时不发送通知

## 日志说明

程序会输出详细的日志信息，包括：

- `[INFO]`：一般信息
- `[CONFIG]`：配置信息
- `[ACCOUNT]`：账户相关操作
- `[MONITOR]`：监控过程
- `[PRICE]`：价格获取
- `[ORDERS]`：订单操作
- `[CHECK]`：订单检查
- `[CANCEL]`：订单撤销
- `[BARK]`：通知发送
- `[ERROR]`：错误信息
- `[SUMMARY]`：统计摘要

## 安全注意事项

1. **API权限**：确保API密钥具有交易权限
2. **价格容差**：合理设置价格容差，避免频繁撤销
3. **监控频率**：建议每10分钟执行一次，避免过于频繁
4. **测试环境**：首次使用建议在模拟盘环境测试

## 故障排除

### 常见问题

1. **账户信息不完整**：检查环境变量是否正确配置
2. **API调用失败**：检查网络连接和API权限
3. **通知发送失败**：检查Bark配置是否正确

### 调试方法

1. 查看青龙面板的日志输出
2. 检查环境变量是否正确设置
3. 确认API密钥的有效性
4. 验证网络连接状态

## 更新日志

- **v1.0.0**：初始版本，支持基本的委托订单监控和撤销功能 