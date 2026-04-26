from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import backtests, charts, health, market, market_data, regime, strategies, sweeps, walkforward

app = FastAPI(
    title="Upbit Trading Console Backend",
    version="0.1.0",
    description="Backtest-first trading console backend with strategy-driven architecture.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(strategies.router)
app.include_router(backtests.router)
app.include_router(walkforward.router)
app.include_router(sweeps.router)
app.include_router(market_data.router)
app.include_router(market.router)
app.include_router(charts.router)
app.include_router(regime.router)
