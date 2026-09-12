# Data Sources

Every external feed the Situation Monitor ingests, grouped by domain. Refresh cadences come from
`backend/app/scheduler.py`; each row lists the upstream, the service module that fetches it, the API
route it surfaces on, and the UI surface that consumes it.

All ingestion follows one pattern: an `async def fetch_*(db)` service → an upsert into a model in
`backend/app/models/` → a router under `backend/app/{elections,monitor,shared}/routers/` → an
APScheduler job. Since `elections-seam` (item #9, T1), `routers/` and `services/` are split into
three bounded packages — `app/elections/`, `app/monitor/`, `app/shared/` — matching the domain
groupings below; a boundary test (`backend/tests/test_module_boundaries.py`) fails CI if an
elections module imports a monitor one or vice versa. Railway and CI run Python 3.11; Samuel's local
venv is still 3.9 (rebuild pending, see roadmap's Later section) — keep `Optional[...]`, not `X | Y`,
until that's done.

Every registered scheduler job also records its own run health into a single upserted `SourceRun`
row (success/failure, last run/success time, item count, last error, expected cadence), keyed by the
job id. It's surfaced at `GET /api/status/sources` and in the "Data Sources" panel on the Status
page — see the `ingestion-health` feature. This is cross-cutting instrumentation of the jobs below,
not a new upstream source, so it gets no row of its own.

---

## Politics & Polling

| Source | Upstream | Service | Cadence | Route | UI |
|---|---|---|---|---|---|
| VoteHub polls | `api.votehub.com/polls` (approval + generic ballot; also `poll_type=us-representative` → House district polls) | `elections/services/votehub.py` | hourly | `/api/votehub/*`, merged into `/api/polls/generic-ballot`; district polls into `/api/polls/house*` | Polls tab (approval card, recent polls, generic ballot; district map/carousel) |
| Economist/YouGov crosstabs | weekly tab-report PDFs (cloudfront) discovered via Wikipedia | `elections/services/economist_yougov.py` | 12h | `/api/economist/*` | Polls tab (`ApprovalSection`) |
| House district polls | Two streams into `HousePoll` (distinguished by `source`): **(1)** Wikipedia — all 50 states' consolidated 2026 House pages; the scrape list is enumerated from each page's own section tree (every `District N → General election → Polling` descendant, plus the six at-large states' top-level `General election → Polling`, stored as district `0`), not from `CompetitiveDistrict` (`elections/services/house_polls.py`, 6h; see `district-coverage-from-wikipedia`); **(2)** VoteHub `us-representative` polls, party resolved via the `Candidate` crosswalk (`elections/services/votehub.py`, hourly — see VoteHub row). Pollster grades from the vendored 538 CSV. `CompetitiveDistrict` still supplies Cook ratings/centroids to `/api/polls/house/districts` and the map — it no longer gates what gets scraped | `elections/services/house_polls.py`, `elections/services/votehub.py` | 6h / hourly | `/api/polls/house*` | Polls tab (district map, carousel) |
| FEC candidates | `api.open.fec.gov/v1` | `elections/services/fec_candidates.py` | 24h | `/api/candidates/*` | Admin / candidates |

**VoteHub average window drain is a forecast-input trigger, not just a display concern
(poll-staleness-labels, 2026-09-12).** `compute_average` (`votehub.py`) is a rolling
21-day window on fieldwork end date measured from *now*, not from the data. If an
upstream feed goes quiet — as approval did, frozen at fieldwork 2026-08-28 since at
least 09-11 while ingestion stayed healthy — the window drains on schedule regardless:
fewer polls, then one poll, then `compute_average` returns `None`. The Polls page labels
this (newest-fieldwork date, a stale marker, thin-average emphasis, an explicit empty
state instead of the card silently vanishing), but the same drain also feeds
`forecast_model.py`'s `_current_env()`, which calls `compute_average(db,
"generic-ballot")` as its tier-1 swing input: a `None` return there **silently drops to
tier 2** (the persisted Wikipedia-aggregator average, the PR #11 fallback) with no
alert beyond the `swing_source` tag already surfaced on the model card. Generic ballot
is healthy today (09-08 fieldwork, still current) only because that stream is still
being delivered — the identical drain will happen to it the moment it stops, and
nothing distinguishes "aggregator tier because VoteHub is genuinely down" from
"aggregator tier because the window merely emptied."

## Forecasting

| Source | Upstream | Service | Cadence | Route | UI |
|---|---|---|---|---|---|
| Kalshi (control of Congress) | `external-api.kalshi.com/trade-api/v2/markets` — series `CONTROLH`, `CONTROLS` (public, no auth) | `elections/services/kalshi.py` → `PredictionMarket` (platform `kalshi`) | 10m | `/api/markets`, `/api/forecasts/congress` | Polls tab (`ForecastSection`), Markets |
| Polymarket | `gamma-api.polymarket.com/markets` (politics) | `elections/services/prediction_markets.py` → `PredictionMarket` (platform `polymarket`) | 10m | `/api/markets`, opportunistically `/api/forecasts/congress` | Markets, Polls tab forecast |

**Forecasting availability (June 2026 sweep).** Two layers exist: *polling averages* (raw inputs we
already ingest) and *forecasts* (probabilistic model/market outputs). On the forecast side:

- **Ingested** — **Kalshi** and **Polymarket** control-of-Congress markets give a market-implied
  forecast, normalized per chamber by `/api/forecasts/congress`. Kalshi is the guaranteed source
  (deterministic `CONTROLH-2026-D/-R`, `CONTROLS-2026-D/-R` tickers); Polymarket is matched
  opportunistically by title and may be absent when those markets fall out of the politics top-N by volume.
- **Link-out only** (cited in `/api/forecasts/congress` `references`, not ingested):
  - **Silver Bulletin** (Nate Silver) — daily generic-ballot average, full model forthcoming; paywalled Substack, no API.
  - **Race to the WH** — House/Senate/Gov model; web-only, no feed.
  - **Split Ticket** — Monte-Carlo chamber-control model built on VoteHub; data via a "Get the Data" / data-repository download whose scheduled-fetch cadence is unverified. Candidate for future ingest (a `ModelForecast` model) if a stable endpoint is confirmed.

## News

| Source | Upstream | Service | Cadence | Route | UI |
|---|---|---|---|---|---|
| GDELT DOC 2.0 (primary) | `api.gdeltproject.org/api/v2/doc/doc` | `monitor/services/gdelt.py` | 30m | via news pipeline | Trends, News |
| NewsAPI (fallback) | `newsapi.org/v2/everything` (free tier lags ~24h) | `monitor/services/news.py` | 30m | `/api/news/*` | News |
| Google News RSS | `news.google.com/rss/*` (search + topics) | `monitor/services/news.py`, `monitor/services/news_categories.py` | 30m | `/api/news/*` | News |

## Trends & Attention

| Source | Upstream | Service | Cadence | Route | UI |
|---|---|---|---|---|---|
| Google Trends | trending RSS (multi-window) | `monitor/services/google_trends_multi.py`, `monitor/services/trends.py` | interval (1h default) | `/api/trends*` | Dashboard, Trends |
| pytrends breakout | Google Trends breakout | `monitor/services/pytrends_service.py` | on demand | `/api/trends/breakout` | Trends |
| Wikipedia trending + pageviews | `wikimedia.org/api/rest_v1/*`, `en.wikipedia.org` | `monitor/services/wikipedia*.py`, `monitor/services/pageviews.py` | 1h | `/api/trends/*` | Trends |
| Reddit | `reddit.com/r/all/hot.json` | `monitor/services/reddit_trending.py` | 1h | via trends | Trends |
| NYT RSS | `rss.nytimes.com/...` (HomePage, MostEmailed, MostShared, US, World) | `monitor/services/nyt.py` | 1h | via trends | Trends |

## Weather, Hazards & Nature

| Source | Upstream | Service | Cadence | Route | UI |
|---|---|---|---|---|---|
| USGS earthquakes | `earthquake.usgs.gov/.../{2.5_day,4.5_week}.geojson` | `monitor/services/earthquakes.py` | 5m | `/api/hazards/earthquakes` | Hazards |
| FAA airspace status | `nasstatus.faa.gov/api/airport-status-information` (XML) | `monitor/services/faa_status.py` | 10m | `/api/hazards/faa` | Hazards |
| NWS alerts | `api.weather.gov/alerts/active` | `monitor/services/nws_alerts.py` | 15m | `/api/weather/alerts` | Weather |
| Open-Meteo | `api.open-meteo.com/v1/forecast` | `monitor/services/regional_weather.py` | 3h | `/api/weather/*` | Weather |
| NASA EONET | `eonet.gsfc.nasa.gov/api/v3/events` | `monitor/services/climate.py` | 6h | `/api/climate` | Dashboard |
| Astronomy | computed locally (sun/moon) | `monitor/services/astronomy.py` | — | `/api/astronomy` | Dashboard |

## Service Status

statuspage.io-style feeds (`*/api/v2/status.json`), refreshed every 15m via `shared/services/service_status.py`,
served at `/api/status`, shown on the Status panel/page:

Claude, OpenAI, Cloudflare, GitHub, Stripe, Twilio, Notion, Atlassian, Reddit, Discord, Linear,
Shopify, Vercel.

---

## Notes & caveats

- **538 pollster ratings are vendored** at `backend/app/data/pollster_ratings.csv` because the live
  feed is dead (the GitHub archive is frozen at 2025-02-25); the GitHub URL is a fallback only.
- **Groq** (`api.groq.com`) is a processing dependency used by `monitor/services/summarizer.py` for text generation —
  not an ingested data source.
- **Kalshi requires no authentication** for market data (public read endpoints, ~30 req/s); only
  trading needs signed requests.
