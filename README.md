# OKX Trading Dashboard

这是一个基于FastAPI的Web应用程序，用于监控和管理OKX交易策略。

## 功能特点

- 实时监控ETH和VINE交易策略的运行状态
- 查看当前订单和历史订单信息
- 跟踪策略收益率和性能指标
- 动态调整策略参数
- 美观的Web界面，支持实时数据更新

## 环境要求

- Python 3.8+
- Node.js 14+（用于Vercel部署）

## 安装依赖

```bash
pip install -r requirements.txt
```

## 环境变量配置

在Vercel上部署时，需要配置以下环境变量：

```env
OKX_API_KEY=你的OKX API密钥
OKX_SECRET_KEY=你的OKX Secret密钥
OKX_PASSPHRASE=你的OKX API密码
OKX_FLAG=0  # 0表示实盘，1表示模拟盘
BARK_KEY=你的Bark推送密钥（可选）
BARK_GROUP=OKX自动交易通知（可选）
```

## 本地开发

```bash
uvicorn app.main:app --reload
```

访问 http://localhost:8000 查看交易面板。

## Vercel部署

1. Fork 这个仓库到你的GitHub账号

2. 在Vercel上创建新项目，选择导入你fork的仓库

3. 配置环境变量（在Vercel项目设置中）

4. 部署项目

## 使用说明

### 查看策略状态

- 绿色标签表示策略正在运行
- 红色标签表示策略已停止

### 调整策略参数

可以通过Web界面修改以下参数：

- Range1 Min/Max：振幅范围1的最小/最大值
- Range2 Threshold：振幅范围2阈值
- Take Profit：止盈比例
- Stop Loss：止损比例
- Margin：保证金额度

### 性能监控

- 总收益：显示策略的累计盈亏（USDT）
- 胜率：显示策略的胜率百分比
- 订单列表：显示最近的交易订单信息

## 注意事项

1. 请确保API密钥具有适当的权限
2. 建议先在模拟盘测试策略
3. 定期检查策略运行状态和性能指标
4. 根据市场情况适时调整策略参数

## 安全提醒

- 请勿在公共场合泄露你的API密钥
- 建议启用API密钥的IP白名单
- 定期更换API密钥
- 设置合理的交易限额