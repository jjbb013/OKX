# 添加滑点
SLIPPAGE = 0.01
if signal == "LONG":
    order_price = entry_price + SLIPPAGE
else:
    order_price = entry_price - SLIPPAGE

order_params = {
    "instId": INST_ID,
    "tdMode": "cross",
    "side": "buy" if signal == "LONG" else "sell",
    "ordType": "limit",
    "px": str(order_price),
    "sz": str(size),
    "clOrdId": cl_ord_id,
    "posSide": "long" if signal == "LONG" else "short",
    "attachAlgoOrds": [attach_algo_ord]
} 