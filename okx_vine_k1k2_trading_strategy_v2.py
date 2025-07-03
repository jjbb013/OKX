import os
import json

if not signal:
    print(f"[{get_shanghai_time()}] [INFO] 未检测到交易信号")
    # 新增：无信号时也计算下单数量并写日志
    entry_price = float(kline_data[1][4])  # K2收盘价
    for suffix in ACCOUNT_SUFFIXES:
        account_prefix = f"[ACCOUNT-{suffix}]" if suffix else "[ACCOUNT]"
        trade_value = MARGIN * LEVERAGE
        raw_qty = trade_value / (entry_price * CONTRACT_FACE_VALUE)
        qty = int((raw_qty + 9) // 10 * 10)
        os.makedirs("logs", exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "time": get_shanghai_time(),
                "account": account_prefix,
                "signal": "NO_SIGNAL",
                "entry_price": entry_price,
                "qty": qty,
                "note": "无信号时的下单数量估算"
            }, ensure_ascii=False) + "\n")
    return 