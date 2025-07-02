"""
测试新的通知格式
演示详细的下单参数和服务器返回结果的易读排版
"""

from notification_service import notification_service

def test_detailed_notification():
    """测试详细的交易通知格式"""
    
    # 模拟下单参数
    order_params = {
        "instId": "ETH-USDT-SWAP",
        "tdMode": "cross",
        "side": "buy",
        "ordType": "limit",
        "px": "2500.50",
        "sz": "100",
        "clOrdId": "TEST_ORDER_001",
        "posSide": "long",
        "attachAlgoOrds": [
            {
                "attachAlgoClOrdId": "ALGO_TP_001",
                "tpTriggerPx": "2550.00",
                "tpOrdPx": "-1",
                "tpOrdKind": "condition",
                "slTriggerPx": "2450.00",
                "slOrdPx": "-1",
                "tpTriggerPxType": "last",
                "slTriggerPxType": "last"
            }
        ]
    }
    
    # 模拟服务器返回结果
    order_result = {
        "code": "0",
        "msg": "",
        "data": [
            {
                "ordId": "123456789",
                "clOrdId": "TEST_ORDER_001",
                "tag": "",
                "state": "live",
                "attachAlgoOrds": [
                    {
                        "attachAlgoClOrdId": "ALGO_TP_001",
                        "state": "live",
                        "tpTriggerPx": "2550.00",
                        "slTriggerPx": "2450.00"
                    }
                ]
            }
        ]
    }
    
    # 发送详细通知
    success = notification_service.send_trading_notification(
        account_name="测试账户",
        inst_id="ETH-USDT-SWAP",
        signal_type="LONG",
        entry_price=2500.50,
        size=100,
        margin=5.0,
        take_profit_price=2550.00,
        stop_loss_price=2450.00,
        success=True,
        error_msg="",
        order_params=order_params,
        order_result=order_result
    )
    
    print(f"详细通知发送结果: {'成功' if success else '失败'}")
    
    # 测试失败情况
    failed_result = {
        "code": "50001",
        "msg": "参数错误：价格超出限制",
        "data": []
    }
    
    success2 = notification_service.send_trading_notification(
        account_name="测试账户",
        inst_id="ETH-USDT-SWAP",
        signal_type="LONG",
        entry_price=2500.50,
        size=100,
        margin=5.0,
        take_profit_price=2550.00,
        stop_loss_price=2450.00,
        success=False,
        error_msg="参数错误：价格超出限制",
        order_params=order_params,
        order_result=failed_result
    )
    
    print(f"失败通知发送结果: {'成功' if success2 else '失败'}")

if __name__ == "__main__":
    print("开始测试新的通知格式...")
    test_detailed_notification()
    print("测试完成！") 