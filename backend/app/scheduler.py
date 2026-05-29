import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.database import SessionLocal
from app.services import news as news_service
from app.services import summarizer as summarizer_service
from app.services import trends as trends_service
from app.services import wikipedia as wikipedia_service
from app.services import pageviews as pageviews_service
from app.services.velocity import compute_velocity
from app.services import pytrends_service
from app.services import clustering as clustering_service
from app.services import climate as climate_service
from app.services import regional_weather as regional_weather_service
from app.services import news_categories as news_categories_service

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def refresh_all():
    logger.info("Starting scheduled refresh...")
    db = SessionLocal()
    try:
        # Trends service also parses embedded RSS articles — no external API needed
        all_trends = await trends_service.fetch_trends(db)
        from app.models import Article as ArticleModel
        for trend in all_trends:
            try:
                await news_service.fetch_articles(trend, db)
                articles = db.query(ArticleModel).filter(ArticleModel.trend_id == trend.id).all()
                await summarizer_service.generate_summary(trend, articles, db)
                pages = await wikipedia_service.fetch_wiki(trend, db)
                primary = next((p for p in pages if p.is_primary), None)
                if primary:
                    await pageviews_service.fetch_pageviews(primary, db)
                compute_velocity(trend, db)
            except Exception as trend_err:
                logger.warning("Error enriching '%s': %s", trend.title, trend_err)
        db.commit()
        await clustering_service.cluster_trends(db)
        logger.info("Refresh complete — %d trends processed", len(all_trends))
    except Exception as e:
        logger.exception("Refresh job failed: %s", e)
    finally:
        db.close()


async def refresh_climate():
    logger.info("Starting climate event refresh...")
    db = SessionLocal()
    try:
        events = await climate_service.fetch_climate_events(db)
        logger.info("Climate refresh complete — %d events", len(events))
    except Exception as e:
        logger.exception("Climate refresh failed: %s", e)
    finally:
        db.close()


async def refresh_news():
    logger.info("Refreshing news categories...")
    db = SessionLocal()
    try:
        for cat in ["politics", "transportation"]:
            await news_categories_service.fetch_news_category(cat, db)
    except Exception as e:
        logger.exception("News refresh failed: %s", e)
    finally:
        db.close()


async def refresh_weather():
    logger.info("Refreshing regional weather...")
    db = SessionLocal()
    try:
        await regional_weather_service.fetch_regional_weather(db)
    except Exception as e:
        logger.exception("Weather refresh failed: %s", e)
    finally:
        db.close()


async def refresh_breakout():
    logger.info("Starting pytrends breakout refresh...")
    db = SessionLocal()
    try:
        trends = await pytrends_service.fetch_breakout_trends(db)
        logger.info("Breakout refresh complete — %d topics", len(trends))
    except Exception as e:
        logger.exception("Breakout refresh failed: %s", e)
    finally:
        db.close()


def start_scheduler(interval_hours: int = 3):
    scheduler.add_job(
        refresh_all,
        IntervalTrigger(hours=interval_hours),
        id="refresh_job",
        replace_existing=True,
    )
    scheduler.add_job(
        refresh_climate,
        IntervalTrigger(hours=6),
        id="climate_job",
        replace_existing=True,
    )
    scheduler.add_job(
        refresh_news,
        IntervalTrigger(hours=1),
        id="news_job",
        replace_existing=True,
    )
    scheduler.add_job(
        refresh_weather,
        IntervalTrigger(hours=3),
        id="weather_job",
        replace_existing=True,
    )
    # Breakout job uses pytrends — enable when a reliable data source is wired in
    # scheduler.add_job(refresh_breakout, IntervalTrigger(hours=1), id="breakout_job")
    scheduler.start()
    logger.info("Scheduler started — RSS every %dh, pytrends every 1h", interval_hours)
