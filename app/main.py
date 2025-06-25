from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import os
from datetime import datetime, timezone, timedelta
import json
from typing import Optional
import pandas as pd

app = FastAPI(title="OKX Trading Dashboard")

# 挂载静态文件和模板
app.mount("/static", StaticFiles(directory="/var/task/app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# 导入交易策略模块
from app.strategies.eth_strategy import ETHStrategy
from app.strategies.vine_strategy import VineStrategy

# 创建策略实例
eth_strategy = ETHStrategy()
vine_strategy = VineStrategy()

@app.get("/")
async def home(request: Request):
    """主页面"""
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )

@app.get("/api/status")
async def get_status():
    """获取所有策略的运行状态"""
    return {
        "eth": eth_strategy.get_status(),
        "vine": vine_strategy.get_status()
    }

@app.post("/api/parameters/{strategy}")
async def update_parameters(
    strategy: str,
    range1_min: float = Form(...),
    range1_max: float = Form(...),
    range2_threshold: float = Form(...),
    take_profit_percent: float = Form(...),
    stop_loss_percent: float = Form(...),
    margin: float = Form(...)
):
    """更新策略参数"""
    try:
        if strategy == "eth":
            eth_strategy.update_parameters(
                range1_min=range1_min,
                range1_max=range1_max,
                range2_threshold=range2_threshold,
                take_profit_percent=take_profit_percent,
                stop_loss_percent=stop_loss_percent,
                margin=margin
            )
        elif strategy == "vine":
            vine_strategy.update_parameters(
                range1_min=range1_min,
                range1_max=range1_max,
                range2_threshold=range2_threshold,
                take_profit_percent=take_profit_percent,
                stop_loss_percent=stop_loss_percent,
                margin=margin
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid strategy name")
        
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/orders/{strategy}")
async def get_orders(strategy: str):
    """获取策略的订单信息"""
    try:
        if strategy == "eth":
            return eth_strategy.get_orders()
        elif strategy == "vine":
            return vine_strategy.get_orders()
        else:
            raise HTTPException(status_code=400, detail="Invalid strategy name")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/performance/{strategy}")
async def get_performance(strategy: str):
    """获取策略的收益表现"""
    try:
        if strategy == "eth":
            return eth_strategy.get_performance()
        elif strategy == "vine":
            return vine_strategy.get_performance()
        else:
            raise HTTPException(status_code=400, detail="Invalid strategy name")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)