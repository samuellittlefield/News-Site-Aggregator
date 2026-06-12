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
from app.services import wikipedia_trending as wikipedia_trending_service
from app.services import reddit_trending as reddit_trending_service
from app.services import google_trends_multi as google_trends_multi_service
from app.services import nyt as nyt_service
from app.services import situation_builder as situation_builder_service
from app.services import service_status as service_status_service
from app.services import nws_alerts as nws_alerts_service
from app.services import house_polls as house_polls_service
from app.services import fec_candidates as fec_candidates_service
from app.services import issue_tagger as issue_tagger_service
from app.services import economist_yougov as economist_yougov_service
from app.services import votehub as votehub_service
from app.services import earthquakes as earthquakes_service
from app.services import faa_status as faa_status_service
from app.services import prediction_markets as prediction_markets_service

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def refresh_all():
    logger.info("Starting scheduled refresh (multi-window Google Trends)...")
    db = SessionLocal()
    try:
        # Use multi-window service (4h + 24h) instead of single RSS
        all_trends = await google_trends_multi_service.fetch_google_trends_multi(db)
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


async def refresh_extended_sources():
    """Enrich active Google Trends with Wikipedia + NYT signals (boost only)."""
    logger.info("Refreshing enrichment sources (Wikipedia + NYT)...")
    db = SessionLocal()
    try:
        wiki_boosted = await wikipedia_trending_service.fetch_wikipedia_trending(db)
        nyt_boosted  = await nyt_service.fetch_nyt_trending(db)
        reddit_count = await reddit_trending_service.fetch_reddit_trending(db)
        logger.info(
            "Enrichment: Wikipedia boosted %d, NYT boosted %d, Reddit %d",
            wiki_boosted, nyt_boosted, reddit_count,
        )
        # Build cross-source situation summaries
        synthesized = await situation_builder_service.build_situation_summaries(db)
        logger.info("Situation synthesis: updated %d summaries", synthesized)
    except Exception as e:
        logger.exception("Extended sources refresh failed: %s", e)
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


async def refresh_status():
    logger.info("Refreshing service statuses...")
    db = SessionLocal()
    try:
        await service_status_service.fetch_service_statuses(db)
    except Exception as e:
        logger.exception("Service status refresh failed: %s", e)
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


async def refresh_nws_alerts():
    logger.info("Refreshing NWS active alerts...")
    db = SessionLocal()
    try:
        alerts = await nws_alerts_service.fetch_nws_alerts(db)
        logger.info("NWS alerts refresh complete — %d alerts", len(alerts))
    except Exception as e:
        logger.exception("NWS alerts refresh failed: %s", e)
    finally:
        db.close()


async def refresh_candidates():
    logger.info("Refreshing 2026 candidates from FEC...")
    db = SessionLocal()
    try:
        result = await fec_candidates_service.refresh_candidates(db)
        logger.info("Candidates refresh: House=%d Senate=%d Gov=%d",
                    result["house"], result["senate"], result["governors"])
    except Exception as e:
        logger.exception("Candidates refresh failed: %s", e)
    finally:
        db.close()


async def run_issue_tagger():
    logger.info("Running AI issue tagger...")
    db = SessionLocal()
    try:
        count = await issue_tagger_service.tag_candidates(db)
        logger.info("Issue tagger: %d suggestions added", count)
    except Exception as e:
        logger.exception("Issue tagger failed: %s", e)
    finally:
        db.close()


async def refresh_house_polls():
    logger.info("Refreshing 2026 House polls...")
    db = SessionLocal()
    try:
        result = await house_polls_service.refresh_house_polls(db)
        logger.info("House polls refresh complete — %d new polls", result.get("new_polls", 0))
    except Exception as e:
        logger.exception("House polls refresh failed: %s", e)
    finally:
        db.close()


async def refresh_economist():
    logger.info("Refreshing Economist/YouGov crosstabs...")
    db = SessionLocal()
    try:
        result = await economist_yougov_service.refresh_economist_yougov(db)
        logger.info("Econ/YouGov refresh complete — %d new reports, %d questions",
                    result.get("new_reports", 0), result.get("questions", 0))
    except Exception as e:
        logger.exception("Econ/YouGov refresh failed: %s", e)
    finally:
        db.close()


async def refresh_votehub():
    logger.info("Refreshing VoteHub polls...")
    db = SessionLocal()
    try:
        counts = await votehub_service.fetch_votehub_polls(db)
        logger.info("VoteHub refresh complete — %s", counts)
    except Exception as e:
        logger.exception("VoteHub refresh failed: %s", e)
    finally:
        db.close()


async def refresh_earthquakes():
    logger.info("Refreshing USGS earthquakes...")
    db = SessionLocal()
    try:
        count = await earthquakes_service.fetch_earthquakes(db)
        logger.info("Earthquake refresh complete — %d quakes", count)
    except Exception as e:
        logger.exception("Earthquake refresh failed: %s", e)
    finally:
        db.close()


async def refresh_faa():
    logger.info("Refreshing FAA airspace status...")
    try:
        events = await faa_status_service.fetch_faa_status()
        logger.info("FAA refresh complete — %d events", len(events))
    except Exception as e:
        logger.exception("FAA refresh failed: %s", e)


async def refresh_markets():
    logger.info("Refreshing prediction markets...")
    db = SessionLocal()
    try:
        count = await prediction_markets_service.fetch_polymarket(db)
        logger.info("Markets refresh complete — %d markets", count)
    except Exception as e:
        logger.exception("Markets refresh failed: %s", e)
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


def start_scheduler(interval_hours: int = 1):
    scheduler.add_job(
        refresh_all,
        IntervalTrigger(hours=interval_hours),
        id="refresh_job",
        replace_existing=True,
    )
    scheduler.add_job(
        refresh_extended_sources,
        IntervalTrigger(hours=1),
        id="extended_job",
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
        IntervalTrigger(minutes=30),
        id="news_job",
        replace_existing=True,
    )
    scheduler.add_job(
        refresh_weather,
        IntervalTrigger(hours=3),
        id="weather_job",
        replace_existing=True,
    )
    scheduler.add_job(
        refresh_status,
        IntervalTrigger(minutes=15),
        id="status_job",
        replace_existing=True,
    )
    scheduler.add_job(
        refresh_nws_alerts,
        IntervalTrigger(minutes=15),
        id="nws_alerts_job",
        replace_existing=True,
    )
    scheduler.add_job(
        refresh_house_polls,
        IntervalTrigger(hours=6),
        id="house_polls_job",
        replace_existing=True,
    )
    scheduler.add_job(
        refresh_candidates,
        IntervalTrigger(hours=24),
        id="candidates_job",
        replace_existing=True,
    )
    scheduler.add_job(
        run_issue_tagger,
        IntervalTrigger(days=7),
        id="issue_tagger_job",
        replace_existing=True,
    )
    scheduler.add_job(
        refresh_economist,
        IntervalTrigger(hours=12),
        id="economist_job",
        replace_existing=True,
    )
    scheduler.add_job(
        refresh_votehub,
        IntervalTrigger(hours=1),
        id="votehub_job",
        replace_existing=True,
    )
    scheduler.add_job(
        refresh_earthquakes,
        IntervalTrigger(minutes=5),
        id="earthquakes_job",
        replace_existing=True,
    )
    scheduler.add_job(
        refresh_faa,
        IntervalTrigger(minutes=10),
        id="faa_job",
        replace_existing=True,
    )
    scheduler.add_job(
        refresh_markets,
        IntervalTrigger(minutes=10),
        id="markets_job",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — Google Trends every %dh, enrichment every 1h", interval_hours)
