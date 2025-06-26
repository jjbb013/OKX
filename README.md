# OKX 自动化交易系统

一个基于Python的OKX交易所自动化交易系统，支持多账户管理、智能交易策略、委托监控和实时通知功能。

## 🚀 项目特色

- **多账户支持**：支持同时管理多个OKX账户
- **智能交易策略**：基于K线振幅分析的自动化交易
- **委托订单监控**：自动监控和撤销符合条件的委托订单
- **统一通知服务**：集成Bark推送，支持多种通知类型
- **实时监控**：振幅检查、价格监控等实时预警功能
- **高可用性**：完善的错误处理和重试机制

## 📁 项目结构

```
OKX/
├── 核心交易策略
│   ├── okx_eth_trading_strategy.py    # ETH自动交易策略
│   ├── okx_vine_trading_strategy.py   # VINE自动交易策略
│   └── okx_test_order.py              # API测试程序
├── 监控服务
│   ├── okx_order_monitor.py           # 委托订单监控
│   ├── okx_振幅检查.py                # 振幅监控服务
│   └── 振幅检查_high_low_open.py      # 高低开振幅检查
├── 通知服务
│   └── notification_service.py        # 统一通知服务
├── 杠杆设置
│   ├── okx_eth_set_leverage.py        # ETH杠杆设置
│   ├── okx_vine_set_leverage.py       # VINE杠杆设置
│   └── okx_trump_set_leverage.py      # TRUMP杠杆设置
└── 文档
    ├── README.md                       # 项目说明文档
    └── README_委托监控.md              # 委托监控详细说明
```

## 🎯 核心功能

### 1. 自动交易策略

**ETH/VINE 交易策略**：
- 基于5分钟K线振幅分析
- 支持做多/做空双向交易
- 自动止盈止损设置
- 多账户并行执行

**交易条件**：
- 振幅范围1：0.8% - 1.8%（使用中间价入场）
- 振幅范围2：> 2%（使用收盘价入场，反向交易）
- 止盈：1.6%，止损：1.9%

### 2. 委托订单监控

**智能撤销逻辑**：
- 监控所有未成交委托订单
- 基于止盈价格判断撤销条件
- 做多订单：当前价格超过止盈价格时撤销
- 做空订单：当前价格低于止盈价格时撤销

### 3. 实时监控服务

**振幅检查**：
- 监控多个交易标的的实时振幅
- 支持自定义阈值设置
- 实时预警通知

**价格监控**：
- 实时获取市场价格
- 异常波动预警

### 4. 统一通知服务

**支持的通知类型**：
- 交易信号通知
- 订单撤销通知
- 振幅预警通知
- 监控摘要通知
- 测试通知

**通知特性**：
- 统一Bark推送配置
- 支持多种通知分组
- 通知统计功能
- 自动重试机制

## ⚙️ 环境配置

### 必需依赖

```bash
pip install okx requests pandas
```

### 环境变量配置

```bash
# 默认账户
OKX_API_KEY=您的API密钥
OKX_SECRET_KEY=您的密钥
OKX_PASSPHRASE=您的密码
OKX_FLAG=0  # 0=实盘, 1=模拟盘

# 多账户支持（可选）
OKX_API_KEY1=第二个账户的API密钥
OKX_SECRET_KEY1=第二个账户的密钥
OKX_PASSPHRASE1=第二个账户的密码
OKX_FLAG1=0

OKX_API_KEY2=第三个账户的API密钥
OKX_SECRET_KEY2=第三个账户的密钥
OKX_PASSPHRASE2=第三个账户的密码
OKX_FLAG2=0

OKX_API_KEY3=第四个账户的API密钥
OKX_SECRET_KEY3=第四个账户的密钥
OKX_PASSPHRASE3=第四个账户的密码
OKX_FLAG3=0

# 通知配置（可选）
BARK_KEY=您的Bark推送地址
BARK_GROUP=OKX通知
```

## 🕐 定时任务配置

### 青龙面板配置

| 程序 | 定时规则 | 说明 |
|------|----------|------|
| ETH交易策略 | `1 */5 * * * *` | 每5分钟执行一次 |
| VINE交易策略 | `1 */5 * * * *` | 每5分钟执行一次 |
| 委托订单监控 | `*/10 * * * *` | 每10分钟执行一次 |
| 振幅检查 | `10,20,50 * * * * *` | 每分钟的第10、20、50秒执行 |

### 手动执行

```bash
# 执行ETH交易策略
python okx_eth_trading_strategy.py

# 执行VINE交易策略
python okx_vine_trading_strategy.py

# 执行委托订单监控
python okx_order_monitor.py

# 执行振幅检查
python okx_振幅检查.py

# 测试通知服务
python notification_service.py
```

## 🔧 参数配置

### 交易策略参数

```python
# 交易标的
INST_ID = "ETH-USDT-SWAP"  # 或 "VINE-USDT-SWAP"

# 振幅阈值
RANGE1_MIN = 0.8   # 振幅范围1最小值
RANGE1_MAX = 1.8   # 振幅范围1最大值
RANGE2_THRESHOLD = 2  # 振幅范围2阈值

# 交易参数
MARGIN = 5                    # 保证金(USDT)
LEVERAGE = 10                 # 杠杆倍数
TAKE_PROFIT_PERCENT = 0.016   # 止盈比例(1.6%)
STOP_LOSS_PERCENT = 0.019     # 止损比例(1.9%)

# 账户配置
ACCOUNT_SUFFIXES = ["", "1", "2", "3"]  # 支持4个账户
```

### 监控参数

```python
# 监控标的
MONITOR_INST_IDS = [
    "ETH-USDT-SWAP",
    "VINE-USDT-SWAP",
    # 可添加更多标的
]

# 价格容差
PRICE_TOLERANCE = 0.0001  # 0.01%的容差

# 重试配置
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 2  # 重试间隔(秒)
```

## 📊 使用示例

### 1. 启动交易策略

```python
# 导入通知服务
from notification_service import notification_service

# 发送测试通知
notification_service.send_test_notification("策略启动", "ETH交易策略已启动")

# 执行交易策略
python okx_eth_trading_strategy.py
```

### 2. 监控委托订单

```python
# 委托监控会自动：
# 1. 检查所有未成交订单
# 2. 获取当前市场价格
# 3. 判断是否需要撤销
# 4. 发送撤销通知
python okx_order_monitor.py
```

### 3. 振幅监控

```python
# 振幅检查会监控：
# - BTC-USDT-SWAP
# - VINE-USDT-SWAP  
# - TRUMP-USDT-SWAP
# - ETH-USDT-SWAP
# - ADA-USDT-SWAP
# - DOGE-USDT-SWAP
python okx_振幅检查.py
```

## 🔍 日志说明

程序会输出详细的日志信息：

- `[INFO]` - 一般信息
- `[CONFIG]` - 配置信息
- `[ACCOUNT]` - 账户相关操作
- `[MONITOR]` - 监控过程
- `[PRICE]` - 价格获取
- `[ORDERS]` - 订单操作
- `[CHECK]` - 订单检查
- `[CANCEL]` - 订单撤销
- `[NOTIFICATION]` - 通知发送
- `[ERROR]` - 错误信息
- `[SUMMARY]` - 统计摘要

## ⚠️ 安全注意事项

1. **API权限**：确保API密钥具有交易权限
2. **测试环境**：首次使用建议在模拟盘测试
3. **风险控制**：合理设置保证金和杠杆倍数
4. **监控频率**：避免过于频繁的API调用
5. **密钥安全**：妥善保管API密钥，定期更换

## 🛠️ 故障排除

### 常见问题

1. **账户信息不完整**：检查环境变量是否正确配置
2. **API调用失败**：检查网络连接和API权限
3. **通知发送失败**：检查Bark配置是否正确
4. **订单撤销失败**：检查订单状态和权限

### 调试方法

1. 查看程序日志输出
2. 检查环境变量设置
3. 确认API密钥有效性
4. 验证网络连接状态

## 📈 性能优化

1. **并发处理**：多账户并行执行
2. **错误重试**：自动重试失败的请求
3. **通知优化**：只在必要时发送通知
4. **日志管理**：详细的日志记录便于问题排查

## 🤝 贡献指南

欢迎提交Issue和Pull Request来改进这个项目！

## 📄 许可证

本项目仅供学习和研究使用，请遵守相关法律法规和交易所规则。

## 📞 联系方式

如有问题或建议，请通过GitHub Issues联系。

---

**免责声明**：本项目仅供技术学习和研究使用，不构成投资建议。使用本系统进行实际交易的风险由用户自行承担。