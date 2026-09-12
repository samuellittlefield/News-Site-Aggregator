from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Date, Float, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    fec_id = Column(String, nullable=True, unique=True)   # None for governors
    name = Column(String, nullable=False)
    party = Column(String(4), nullable=True)              # DEM/REP/IND/LIB
    state = Column(String(2), nullable=False)
    district = Column(Integer, nullable=True)             # None for Senate/Governor
    office = Column(String(1), nullable=False)            # H/S/G
    incumbent_challenge = Column(String(1), nullable=True)  # I/C/O
    primary_date = Column(Date, nullable=True)
    primary_status = Column(String, nullable=True)        # upcoming/won/lost/runoff
    general_status = Column(String, nullable=True)        # Nominee / etc.
    fundraising_total = Column(Float, nullable=True)
    cook_rating = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    issue_tags = relationship("CandidateIssueTag", back_populates="candidate", cascade="all, delete-orphan")


class CandidateIssueTag(Base):
    __tablename__ = "candidate_issue_tags"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    issue_code = Column(String, nullable=False)
    ai_suggested = Column(Boolean, default=True, nullable=False)
    confirmed = Column(Boolean, default=False, nullable=False)
    rejected = Column(Boolean, default=False, nullable=False)
    confidence = Column(Float, nullable=True)
    supporting_text = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    candidate = relationship("Candidate", back_populates="issue_tags")


class HousePoll(Base):
    __tablename__ = "house_polls"

    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(String, nullable=False, unique=True)
    pollster = Column(String, nullable=False)
    grade = Column(String, nullable=True)
    state = Column(String(2), nullable=False)
    district = Column(Integer, nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    sample_size = Column(Integer, nullable=True)
    population = Column(String(4), nullable=True)  # LV/RV/A
    dem = Column(Float, nullable=True)
    rep = Column(Float, nullable=True)
    source_url = Column(String, nullable=True)
    # Which ingestion stream produced this row: "wikipedia" | "votehub".
    # server_default keeps existing rows valid; they predate VoteHub ingestion.
    source = Column(String(16), nullable=False, server_default="wikipedia")
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CompetitiveDistrict(Base):
    __tablename__ = "competitive_districts"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String(2), nullable=False)
    district = Column(Integer, nullable=False)
    cook_rating = Column(String, nullable=True)   # Toss-up / Lean D / Lean R / Likely D / Likely R
    dem_2024 = Column(Float, nullable=True)
    rep_2024 = Column(Float, nullable=True)
    margin_2024 = Column(Float, nullable=True)    # dem - rep
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    incumbent_party = Column(String(1), nullable=True)  # D / R / O (open)


class HouseRetirement(Base):
    """A sitting House member NOT seeking re-election in 2026 (scraped from the
    Wikipedia '2026 House elections → Retirements' list). FEC can't tell us this —
    it keeps withdrawn members flagged as active candidates — so this is the
    authoritative 'incumbent is departing → open seat' signal."""
    __tablename__ = "house_retirements"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String(2), nullable=False)
    district = Column(Integer, nullable=False)            # 0 = at-large / delegate
    member_name = Column(String, nullable=False)
    party = Column(String(1), nullable=True)              # D / R
    reason = Column(String, nullable=True)                # e.g. "retiring to run for U.S. Senate"
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EconYouGovReport(Base):
    __tablename__ = "econ_yougov_reports"

    id = Column(Integer, primary_key=True, index=True)
    source_url = Column(String, nullable=False, unique=True)   # cloudfront PDF link
    title = Column(String, nullable=True)                       # "The Economist/YouGov Poll"
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    sample_size = Column(Integer, nullable=True)
    sample_desc = Column(String, nullable=True)                 # "U.S. Adult Citizens"
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    crosstabs = relationship(
        "EconYouGovCrosstab", back_populates="report", cascade="all, delete-orphan",
    )


class EconYouGovCrosstab(Base):
    __tablename__ = "econ_yougov_crosstabs"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("econ_yougov_reports.id", ondelete="CASCADE"), nullable=False)
    question_code = Column(String, nullable=True)       # "23"
    question_key = Column(String, nullable=False)       # stable slug we track, e.g. "trump_approval"
    question_title = Column(String, nullable=True)      # "President Trump Job Approval"
    question_text = Column(Text, nullable=True)         # the prompt wording
    # blocks: [ {group_line, columns:[str], rows:{label:[int]}, ns:{col:int}} ]
    blocks = Column(JSONB, default=list, nullable=False)
    # topline: {label: total_pct} from the Total column (convenience for charting)
    topline = Column(JSONB, default=dict, nullable=False)

    report = relationship("EconYouGovReport", back_populates="crosstabs")


class VoteHubPoll(Base):
    __tablename__ = "votehub_polls"

    id = Column(Integer, primary_key=True, index=True)
    votehub_id = Column(String, nullable=False, unique=True)
    poll_type = Column(String, nullable=False, index=True)   # approval | generic-ballot | favorability
    subject = Column(String, nullable=True)                  # e.g. "Donald Trump", "2026"
    pollster = Column(String, nullable=True)
    sponsors = Column(JSONB, default=list, nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    sample_size = Column(Integer, nullable=True)
    population = Column(String(4), nullable=True)            # lv/rv/a
    answers = Column(JSONB, default=list, nullable=False)    # raw [{choice, pct}]
    approve = Column(Float, nullable=True)
    disapprove = Column(Float, nullable=True)
    dem = Column(Float, nullable=True)
    rep = Column(Float, nullable=True)
    url = Column(String, nullable=True)
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PredictionMarket(Base):
    __tablename__ = "prediction_markets"
    __table_args__ = (UniqueConstraint("platform", "market_id", name="uq_market_platform_id"),)

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String, nullable=False, default="polymarket")
    market_id = Column(String, nullable=False)
    question = Column(String, nullable=False)
    slug = Column(String, nullable=True)
    url = Column(String, nullable=True)
    event_title = Column(String, nullable=True)
    outcomes = Column(JSONB, default=list, nullable=False)   # [{name, price}]
    yes_price = Column(Float, nullable=True)                 # 0–1 for binary markets
    volume_24h = Column(Float, nullable=True)
    liquidity = Column(Float, nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    snapshots = relationship("MarketSnapshot", back_populates="market", cascade="all, delete-orphan")


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    market_id = Column(Integer, ForeignKey("prediction_markets.id", ondelete="CASCADE"), nullable=False)
    yes_price = Column(Float, nullable=True)
    captured_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    market = relationship("PredictionMarket", back_populates="snapshots")


class GenericBallotAggregate(Base):
    """Wikipedia-sourced generic-ballot aggregator averages, persisted from the
    same `refresh_house_polls` fetch that already runs every 6h (previously
    fetched live and discarded). One current row per aggregator `source`, not a
    history log — gives the forecast model a DB-only fallback read path."""
    __tablename__ = "generic_ballot_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False, unique=True)
    rep = Column(Float, nullable=False)
    dem = Column(Float, nullable=False)
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
