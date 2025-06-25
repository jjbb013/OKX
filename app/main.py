from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import redis
import os
import json

app = FastAPI(title="OKX Trading Dashboard")

# 从环境变量获取 Redis URL
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
r = redis.from_url(REDIS_URL)

# 挂载静态文件和模板
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    # 从 Redis 获取最近3次运行状态
    raw_runs = r.lrange('strategy_runs', 0, 2)
    runs = [json.loads(run) for run in raw_runs]
    return templates.TemplateResponse(
        "index.html", {"request": request, "runs": runs}
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

@app.get('/get_kline_checks')
async def get_kline_checks():
    checks = r.lrange('kline_checks', 0, 4)
    return [json.loads(check) for check in checks]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)