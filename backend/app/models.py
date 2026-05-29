from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Date, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class TrendCluster(Base):
    __tablename__ = "trend_clusters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    generated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    trends = relationship("Trend", back_populates="cluster")


class Trend(Base):
    __tablename__ = "trends"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    traffic_volume = Column(String, nullable=True)
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    first_seen_at = Column(DateTime(timezone=True), nullable=True)
    appearance_count = Column(Integer, default=1, nullable=False)
    category = Column(String, nullable=True)
    velocity_abs = Column(Integer, default=0, nullable=False)
    velocity_pct = Column(Integer, default=0, nullable=False)
    rank_velocity = Column(Integer, default=0, nullable=False)
    source = Column(String, default="rss", nullable=False)
    signal_score = Column(Float, default=0.0, nullable=False)
    sources_list = Column(JSONB, default=list, nullable=False)
    trend_window = Column(String, default="24h", nullable=True)
    cluster_id = Column(Integer, ForeignKey("trend_clusters.id", ondelete="SET NULL"), nullable=True)
    geo = Column(String, default="US")
    is_active = Column(Boolean, default=True)

    cluster = relationship("TrendCluster", back_populates="trends")
    articles = relationship("Article", back_populates="trend", cascade="all, delete-orphan")
    summary = relationship("Summary", back_populates="trend", uselist=False, cascade="all, delete-orphan")
    wiki_pages = relationship(
        "WikiPage", back_populates="trend", cascade="all, delete-orphan",
        order_by="WikiPage.search_rank",
    )
    snapshots = relationship("TrendSnapshot", back_populates="trend", cascade="all, delete-orphan")


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    trend_id = Column(Integer, ForeignKey("trends.id"), nullable=False)
    headline = Column(String(500), nullable=True)
    url = Column(String, nullable=True)
    source = Column(String, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    description = Column(Text, nullable=True)

    trend = relationship("Trend", back_populates="articles")


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    trend_id = Column(Integer, ForeignKey("trends.id"), nullable=False, unique=True)
    body = Column(Text, nullable=False)
    generated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    trend = relationship("Trend", back_populates="summary")


class TrendSnapshot(Base):
    __tablename__ = "trend_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    trend_id = Column(Integer, ForeignKey("trends.id"), nullable=False)
    traffic_volume = Column(String, nullable=True)
    rank = Column(Integer, nullable=True)
    captured_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    trend = relationship("Trend", back_populates="snapshots")


class WikiPage(Base):
    __tablename__ = "wiki_pages"

    id = Column(Integer, primary_key=True, index=True)
    trend_id = Column(Integer, ForeignKey("trends.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    extract = Column(Text, nullable=True)
    url = Column(String, nullable=False)
    thumbnail_url = Column(String, nullable=True)
    is_primary = Column(Boolean, default=True, nullable=False)
    search_rank = Column(Integer, default=1, nullable=False)
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    trend = relationship("Trend", back_populates="wiki_pages")
    pageviews = relationship("WikiPageView", back_populates="wiki_page", cascade="all, delete-orphan")


class WikiPageView(Base):
    __tablename__ = "wiki_pageviews"

    id = Column(Integer, primary_key=True, index=True)
    wiki_page_id = Column(Integer, ForeignKey("wiki_pages.id"), nullable=False)
    view_date = Column(Date, nullable=False)
    views = Column(Integer, nullable=False)

    wiki_page = relationship("WikiPage", back_populates="pageviews")


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, nullable=False)
    title = Column(String, nullable=False)
    url = Column(String, nullable=True)
    source = Column(String, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    description = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class RegionalWeather(Base):
    __tablename__ = "regional_weather"

    id = Column(Integer, primary_key=True, index=True)
    region = Column(String, nullable=False, unique=True)
    city = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    temp_max_f = Column(Float, nullable=True)
    temp_min_f = Column(Float, nullable=True)
    precipitation_mm = Column(Float, nullable=True)
    condition = Column(String, nullable=True)
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ServiceStatus(Base):
    __tablename__ = "service_status"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    indicator = Column(String, nullable=False, default="none")   # none | minor | major | critical
    description = Column(String, nullable=True)
    icon = Column(String, nullable=True)
    page_url = Column(String, nullable=True)
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ClimateEvent(Base):
    __tablename__ = "climate_events"

    id = Column(Integer, primary_key=True, index=True)
    eonet_id = Column(String, nullable=False, unique=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False)
    status = Column(String, nullable=False, default="open")
    coordinates = Column(JSONB, nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    magnitude = Column(Float, nullable=True)
    magnitude_unit = Column(String, nullable=True)
    source_url = Column(String, nullable=True)
    ai_summary = Column(Text, nullable=True)
    location = Column(String, nullable=True)
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
