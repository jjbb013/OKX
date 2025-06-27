"""
通知服务模块
统一管理所有通知功能，支持Bark推送
"""
import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

class NotificationService:
    """通知服务类"""
    
    def __init__(self):
        """初始化通知服务"""
        # 尝试从本地配置文件读取Bark配置，如果不存在则使用环境变量
        try:
            from config_local import BARK_KEY, BARK_GROUP
            self.bark_key = BARK_KEY
            self.bark_group = BARK_GROUP
        except ImportError:
            # 从环境变量读取
            self.bark_key = os.getenv("BARK_KEY")
            self.bark_group = os.getenv("BARK_GROUP", "OKX通知")
        
        # 网络请求配置
        self.max_retries = 3
        self.retry_delay = 2
        self.timeout = 10
        
        # 通知统计
        self.notification_count = 0
        self.success_count = 0
        self.failed_count = 0
    
    def get_beijing_time(self) -> str:
        """获取北京时间"""
        beijing_tz = timezone(timedelta(hours=8))
        return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")
    
    def send_bark_notification(self, title: str, message: str, group: Optional[str] = None, 
                              sound: str = "bell", badge: Optional[int] = None, 
                              url: Optional[str] = None, copy: Optional[str] = None) -> bool:
        """
        发送Bark通知
        
        Args:
            title: 通知标题
            message: 通知内容
            group: 通知分组（可选，默认使用环境变量中的BARK_GROUP）
            sound: 通知声音（默认bell）
            badge: 角标数字（可选）
            url: 点击跳转链接（可选）
            copy: 复制内容（可选）
            
        Returns:
            bool: 发送是否成功
        """
        if not self.bark_key:
            print(f"[{self.get_beijing_time()}] [NOTIFICATION] [ERROR] 缺少BARK_KEY配置")
            return False
        
        # 使用指定的分组或默认分组
        notification_group = group if group else self.bark_group
        
        # 构建payload
        payload = {
            'title': title,
            'body': message,
            'group': notification_group,
            'sound': sound
        }
        
        # 添加可选参数
        if badge is not None:
            payload['badge'] = str(badge)
        if url:
            payload['url'] = url
        if copy:
            payload['copy'] = copy
        
        headers = {'Content-Type': 'application/json'}
        
        # 发送通知
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    self.bark_key, 
                    json=payload, 
                    headers=headers, 
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    self.notification_count += 1
                    self.success_count += 1
                    print(f"[{self.get_beijing_time()}] [NOTIFICATION] [BARK] 通知发送成功: {title}")
                    return True
                else:
                    print(f"[{self.get_beijing_time()}] [NOTIFICATION] [BARK] 发送失败: {response.text}")
                    
            except Exception as e:
                print(f"[{self.get_beijing_time()}] [NOTIFICATION] [BARK] 异常 (尝试 {attempt+1}/{self.max_retries+1}): {str(e)}")
                
            if attempt < self.max_retries:
                print(f"[{self.get_beijing_time()}] [NOTIFICATION] [BARK] 重试中... ({attempt+1}/{self.max_retries})")
                time.sleep(self.retry_delay)
        
        self.notification_count += 1
        self.failed_count += 1
        print(f"[{self.get_beijing_time()}] [NOTIFICATION] [BARK] 所有尝试失败")
        return False
    
    def send_trading_notification(self, account_name: str, inst_id: str, signal_type: str, 
                                 entry_price: float, size: float, margin: float,
                                 take_profit_price: float, stop_loss_price: float,
                                 success: bool = True, error_msg: str = "") -> bool:
        """
        发送交易通知
        
        Args:
            account_name: 账户名称
            inst_id: 交易标的
            signal_type: 信号类型（LONG/SHORT）
            entry_price: 入场价格
            size: 委托数量
            margin: 保证金
            take_profit_price: 止盈价格
            stop_loss_price: 止损价格
            success: 是否成功
            error_msg: 错误信息
            
        Returns:
            bool: 发送是否成功
        """
        title = f"交易信号: {signal_type} @ {inst_id}"
        message = (
            f"账户: {account_name}\n"
            f"信号类型: {signal_type}\n"
            f"入场价格: {entry_price:.4f}\n"
            f"委托数量: {size}\n"
            f"保证金: {margin} USDT\n"
            f"止盈价: {take_profit_price:.4f}\n"
            f"止损价: {stop_loss_price:.4f}"
        )
        
        if not success:
            message += f"\n\n⚠️ 下单失败 ⚠️\n错误: {error_msg}"
        
        return self.send_bark_notification(title, message, group="OKX自动交易通知")
    
    def send_order_cancel_notification(self, account_name: str, inst_id: str, ord_id: str,
                                      side: str, pos_side: str, order_price: float,
                                      take_profit_price: float, current_price: float,
                                      reason: str) -> bool:
        """
        发送订单撤销通知
        
        Args:
            account_name: 账户名称
            inst_id: 交易标的
            ord_id: 订单ID
            side: 买卖方向
            pos_side: 持仓方向
            order_price: 委托价格
            take_profit_price: 止盈价格
            current_price: 当前价格
            reason: 撤销原因
            
        Returns:
            bool: 发送是否成功
        """
        title = f"委托订单已撤销 - {inst_id}"
        message = (
            f"账户: {account_name}\n"
            f"交易标的: {inst_id}\n"
            f"订单ID: {ord_id}\n"
            f"方向: {side} {pos_side}\n"
            f"委托价格: {order_price:.4f}\n"
            f"止盈价格: {take_profit_price:.4f}\n"
            f"当前价格: {current_price:.4f}\n"
            f"撤销原因: {reason}"
        )
        
        return self.send_bark_notification(title, message, group="OKX委托监控")
    
    def send_amplitude_alert(self, symbol: str, amplitude: float, threshold: float,
                           open_price: float, latest_price: float) -> bool:
        """
        发送振幅预警通知
        
        Args:
            symbol: 交易标的
            amplitude: 当前振幅
            threshold: 阈值
            open_price: 开盘价
            latest_price: 最新价
            
        Returns:
            bool: 发送是否成功
        """
        title = f"⚠️ {symbol} 振幅预警"
        message = (
            f"当前振幅: {amplitude}%\n"
            f"阈值: {threshold}%\n"
            f"时间: {self.get_beijing_time()}\n"
            f"开盘价: {open_price}\n"
            f"最新价: {latest_price}"
        )
        
        return self.send_bark_notification(title, message, group="OKX振幅监控")
    
    def send_summary_notification(self, results: list, total_canceled: int) -> bool:
        """
        发送监控摘要通知
        
        Args:
            results: 监控结果列表
            total_canceled: 总撤销数量
            
        Returns:
            bool: 发送是否成功
        """
        if total_canceled == 0:
            return True  # 无撤销时不发送通知
        
        total_accounts = len(results)
        success_accounts = sum(1 for r in results if r['success'])
        total_orders = sum(r['total_orders'] for r in results)
        
        title = f"委托监控结果: {total_canceled}个订单已撤销"
        message = f"监控时间: {self.get_beijing_time()}\n\n"
        
        for result in results:
            status = "✅ 成功" if result['success'] else "❌ 失败"
            message += f"账户: {result['account_name']}\n"
            message += f"状态: {status}\n"
            if result['success']:
                message += f"总订单数: {result['total_orders']}\n"
                message += f"撤销订单数: {result['canceled_count']}\n"
            else:
                message += f"错误: {result['error']}\n"
            message += "\n"
        
        message += f"总账户数: {total_accounts}\n"
        message += f"成功账户数: {success_accounts}\n"
        message += f"总撤销订单数: {total_canceled}\n"
        message += f"总监控订单数: {total_orders}"
        
        return self.send_bark_notification(title, message, group="OKX委托监控")
    
    def send_test_notification(self, title: str = "测试通知", message: str = "这是一条测试通知") -> bool:
        """
        发送测试通知
        
        Args:
            title: 通知标题
            message: 通知内容
            
        Returns:
            bool: 发送是否成功
        """
        return self.send_bark_notification(title, message, group="OKX测试通知")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取通知统计信息
        
        Returns:
            Dict: 统计信息
        """
        return {
            "total_notifications": self.notification_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "success_rate": (self.success_count / self.notification_count * 100) if self.notification_count > 0 else 0
        }
    
    def reset_statistics(self):
        """重置统计信息"""
        self.notification_count = 0
        self.success_count = 0
        self.failed_count = 0

# 创建全局通知服务实例
notification_service = NotificationService()

# 便捷函数，用于向后兼容
def send_bark_notification(title: str, message: str, group: Optional[str] = None) -> bool:
    """
    发送Bark通知（便捷函数）
    
    Args:
        title: 通知标题
        message: 通知内容
        group: 通知分组（可选）
        
    Returns:
        bool: 发送是否成功
    """
    return notification_service.send_bark_notification(title, message, group)

if __name__ == "__main__":
    # 测试通知服务
    print("测试通知服务...")
    
    # 测试基本通知
    success = notification_service.send_test_notification("通知服务测试", "通知服务已成功启动！")
    print(f"测试通知发送结果: {'成功' if success else '失败'}")
    
    # 显示统计信息
    stats = notification_service.get_statistics()
    print(f"通知统计: {json.dumps(stats, indent=2, ensure_ascii=False)}") 