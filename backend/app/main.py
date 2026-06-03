import asyncio
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
from app.routers import status as status_router
from app.routers import polls as polls_router
from app.routers import candidates as candidates_router
from app.scheduler import refresh_all, refresh_breakout, refresh_candidates, refresh_climate, refresh_extended_sources, refresh_house_polls, refresh_news, refresh_nws_alerts, refresh_status, refresh_weather, start_scheduler
from fastapi import BackgroundTasks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

logger = logging.getLogger(__name__)


async def _startup_refresh():
    """Run an initial full refresh shortly after startup so summaries are populated immediately."""
    await asyncio.sleep(5)  # brief pause to let DB connections settle
    logger.info("Running startup refresh...")
    await refresh_all()
    await refresh_extended_sources()
    await refresh_news()
    await refresh_status()
    await refresh_weather()
    await refresh_nws_alerts()
    await refresh_house_polls()
    await refresh_candidates()
    logger.info("Startup refresh complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    start_scheduler(interval_hours=1)
    # Fire a full refresh immediately so the feed is fresh on every deploy
    asyncio.create_task(_startup_refresh())
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
app.include_router(status_router.router)
app.include_router(polls_router.router)
app.include_router(candidates_router.router)


async def _do_full_refresh():
    """Run all refresh jobs sequentially as a background task."""
    await refresh_all()
    await refresh_extended_sources()
    await refresh_climate()
    await refresh_news()
    await refresh_weather()
    await refresh_status()
    await refresh_nws_alerts()


@app.post("/api/refresh", summary="Manually trigger a data refresh")
async def manual_refresh(background_tasks: BackgroundTasks):
    """Returns immediately; all refresh jobs run in the background."""
    background_tasks.add_task(_do_full_refresh)
    return {"status": "ok", "message": "Refresh queued"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/api/debug/sources")
async def debug_sources():
    """Test extended sources connectivity and logic without writing to DB."""
    import httpx
    from datetime import date, timedelta

    results = {}

    # Test Wikimedia
    today = date.today()
    yesterday = today - timedelta(days=1)
    headers = {"User-Agent": "TrendingNewsSite/1.0"}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
            r = await client.get(
                f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access"
                f"/{today.year}/{today.month:02d}/{today.day:02d}"
            )
        items = r.json().get("items", [{}])
        articles = items[0].get("articles", []) if items else []
        results["wikimedia"] = {
            "status": r.status_code,
            "article_count": len(articles),
            "top_3": [a["article"] for a in articles[:3]],
        }
    except Exception as e:
        results["wikimedia"] = {"error": str(e)}

    # Test Reddit
    try:
        async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
            r = await client.get("https://www.reddit.com/r/all/hot.json?limit=5")
        posts = r.json().get("data", {}).get("children", [])
        results["reddit"] = {
            "status": r.status_code,
            "post_count": len(posts),
            "top_scores": [p["data"]["score"] for p in posts[:3]],
        }
    except Exception as e:
        results["reddit"] = {"error": str(e)}

    # Check current DB trend count by source
    from app.database import SessionLocal
    from app.models import Trend
    db = SessionLocal()
    try:
        all_trends = db.query(Trend).filter(Trend.is_active == True).all()  # noqa
        by_source = {}
        for t in all_trends:
            by_source[t.source] = by_source.get(t.source, 0) + 1
        results["db_trends"] = by_source
    finally:
        db.close()

    return results
