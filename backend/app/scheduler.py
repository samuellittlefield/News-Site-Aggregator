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

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def refresh_all():
    logger.info("Starting scheduled refresh...")
    db = SessionLocal()
    try:
        # Trends service also parses embedded RSS articles — no external API needed
        all_trends = await trends_service.fetch_trends(db)
        for trend in all_trends:
            # Supplement with NewsAPI articles if key is configured
            extra = await news_service.fetch_articles(trend, db)
            # Use whichever article list is non-empty for the summary
            from app.models import Article as ArticleModel
            articles = db.query(ArticleModel).filter(ArticleModel.trend_id == trend.id).all()
            await summarizer_service.generate_summary(trend, articles, db)
            pages = await wikipedia_service.fetch_wiki(trend, db)
            # Fetch pageviews only for the primary article (rank 1)
            primary = next((p for p in pages if p.is_primary), None)
            if primary:
                await pageviews_service.fetch_pageviews(primary, db)
            compute_velocity(trend, db)
        db.commit()
        logger.info("Refresh complete — %d trends processed", len(all_trends))
    except Exception as e:
        logger.exception("Refresh job failed: %s", e)
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
    # Breakout job uses pytrends — enable when a reliable data source is wired in
    # scheduler.add_job(refresh_breakout, IntervalTrigger(hours=1), id="breakout_job")
    scheduler.start()
    logger.info("Scheduler started — RSS every %dh, pytrends every 1h", interval_hours)
