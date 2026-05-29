import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine
from app.models import Base
from app.routers import trends as trends_router
from app.routers import climate as climate_router
from app.routers import weather as weather_router
from app.routers import news as news_router
from app.routers import astronomy as astronomy_router
from app.scheduler import refresh_all, refresh_breakout, refresh_climate, refresh_news, refresh_weather, start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    start_scheduler(interval_hours=3)
    yield


app = FastAPI(title="Trending News API", lifespan=lifespan)

_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:4173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trends_router.router)
app.include_router(climate_router.router)
app.include_router(weather_router.router)
app.include_router(news_router.router)
app.include_router(astronomy_router.router)


@app.post("/api/refresh", summary="Manually trigger a data refresh")
async def manual_refresh():
    await refresh_all()
    await refresh_climate()
    await refresh_news()
    await refresh_weather()
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "healthy"}
