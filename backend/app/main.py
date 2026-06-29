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
from app.routers import economist as economist_router
from app.routers import votehub as votehub_router
from app.routers import hazards as hazards_router
from app.routers import markets as markets_router
from app.routers import forecasts as forecasts_router
from app.scheduler import refresh_all, refresh_breakout, refresh_candidates, refresh_climate, refresh_earthquakes, refresh_economist, refresh_extended_sources, refresh_faa, refresh_house_polls, refresh_kalshi, refresh_markets, refresh_news, refresh_nws_alerts, refresh_retirements, refresh_status, refresh_votehub, refresh_weather, start_scheduler
from fastapi import BackgroundTasks

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

logger = logging.getLogger(__name__)


async def _safe_refresh(name: str, fn, timeout: float = 180.0):
    """Run one startup refresh step in isolation: a step that errors or hangs is
    logged and skipped so it can't starve the steps after it (notably the FEC
    candidate fetch, which sits near the end of the chain)."""
    try:
        await asyncio.wait_for(fn(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("Startup refresh step '%s' timed out after %ss; skipping", name, timeout)
    except Exception:  # noqa: BLE001
        logger.exception("Startup refresh step '%s' failed; continuing", name)


async def _startup_refresh():
    """Run an initial full refresh shortly after startup so summaries are populated
    immediately. Each step is isolated so one slow/broken source can't abort the rest."""
    await asyncio.sleep(5)  # brief pause to let DB connections settle
    logger.info("Running startup refresh...")
    # Fast/cheap sources first so the dashboard populates immediately.
    # (name, fn, timeout_seconds) — candidates pulls all of FEC + issue-tags, so
    # it gets a longer budget than the lighter feed refreshes.
    steps = [
        ("votehub", refresh_votehub, 120.0),
        ("earthquakes", refresh_earthquakes, 120.0),
        ("faa", refresh_faa, 120.0),
        ("markets", refresh_markets, 120.0),
        ("kalshi", refresh_kalshi, 120.0),
        ("all", refresh_all, 180.0),
        ("extended_sources", refresh_extended_sources, 180.0),
        ("news", refresh_news, 180.0),
        ("status", refresh_status, 120.0),
        ("weather", refresh_weather, 120.0),
        ("nws_alerts", refresh_nws_alerts, 120.0),
        ("house_polls", refresh_house_polls, 180.0),
        ("candidates", refresh_candidates, 600.0),
        ("retirements", refresh_retirements, 120.0),
        ("economist", refresh_economist, 180.0),
    ]
    for name, fn, timeout in steps:
        await _safe_refresh(name, fn, timeout)
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
app.include_router(economist_router.router)
app.include_router(votehub_router.router)
app.include_router(hazards_router.router)
app.include_router(markets_router.router)
app.include_router(forecasts_router.router)


async def _do_full_refresh():
    """Run all refresh jobs sequentially as a background task."""
    await refresh_all()
    await refresh_extended_sources()
    await refresh_climate()
    await refresh_news()
    await refresh_weather()
    await refresh_status()
    await refresh_nws_alerts()
    await refresh_votehub()
    await refresh_earthquakes()
    await refresh_faa()
    await refresh_markets()
    await refresh_kalshi()


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
