# Data Sources

Every external feed the Situation Monitor ingests, grouped by domain. Refresh cadences come from
`backend/app/scheduler.py`; each row lists the upstream, the service module that fetches it, the API
route it surfaces on, and the UI surface that consumes it.

All ingestion follows one pattern: an `async def fetch_*(db)` service → an upsert into a model in
`backend/app/models.py` → a router under `backend/app/routers/` → an APScheduler job. The Python
runtime is 3.9 (use `Optional[...]`, not `X | Y`).

---

## Politics & Polling

| Source | Upstream | Service | Cadence | Route | UI |
|---|---|---|---|---|---|
| VoteHub polls | `api.votehub.com/polls` (approval + generic ballot) | `votehub.py` | hourly | `/api/votehub/*`, merged into `/api/polls/generic-ballot` | Polls tab (approval card, recent polls, generic ballot) |
| Economist/YouGov crosstabs | weekly tab-report PDFs (cloudfront) discovered via Wikipedia | `economist_yougov.py` | 12h | `/api/economist/*` | Polls tab (`ApprovalSection`) |
| House district polls | Wikipedia 2026 House polls + vendored 538 pollster grades | `house_polls.py` | 6h | `/api/polls/house*` | Polls tab (district map, carousel) |
| FEC candidates | `api.open.fec.gov/v1` | `fec_candidates.py` | 24h | `/api/candidates/*` | Admin / candidates |

## Forecasting

| Source | Upstream | Service | Cadence | Route | UI |
|---|---|---|---|---|---|
| Kalshi (control of Congress) | `external-api.kalshi.com/trade-api/v2/markets` — series `CONTROLH`, `CONTROLS` (public, no auth) | `kalshi.py` → `PredictionMarket` (platform `kalshi`) | 10m | `/api/markets`, `/api/forecasts/congress` | Polls tab (`ForecastSection`), Markets |
| Polymarket | `gamma-api.polymarket.com/markets` (politics) | `prediction_markets.py` → `PredictionMarket` (platform `polymarket`) | 10m | `/api/markets`, opportunistically `/api/forecasts/congress` | Markets, Polls tab forecast |

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
| GDELT DOC 2.0 (primary) | `api.gdeltproject.org/api/v2/doc/doc` | `gdelt.py` | 30m | via news pipeline | Trends, News |
| NewsAPI (fallback) | `newsapi.org/v2/everything` (free tier lags ~24h) | `news.py` | 30m | `/api/news/*` | News |
| Google News RSS | `news.google.com/rss/*` (search + topics) | `news.py`, `news_categories.py` | 30m | `/api/news/*` | News |

## Trends & Attention

| Source | Upstream | Service | Cadence | Route | UI |
|---|---|---|---|---|---|
| Google Trends | trending RSS (multi-window) | `google_trends_multi.py`, `trends.py` | interval (1h default) | `/api/trends*` | Dashboard, Trends |
| pytrends breakout | Google Trends breakout | `pytrends_service.py` | on demand | `/api/trends/breakout` | Trends |
| Wikipedia trending + pageviews | `wikimedia.org/api/rest_v1/*`, `en.wikipedia.org` | `wikipedia*.py`, `pageviews.py` | 1h | `/api/trends/*` | Trends |
| Reddit | `reddit.com/r/all/hot.json` | `reddit_trending.py` | 1h | via trends | Trends |
| NYT RSS | `rss.nytimes.com/...` (HomePage, MostEmailed, MostShared, US, World) | `nyt.py` | 1h | via trends | Trends |

## Weather, Hazards & Nature

| Source | Upstream | Service | Cadence | Route | UI |
|---|---|---|---|---|---|
| USGS earthquakes | `earthquake.usgs.gov/.../{2.5_day,4.5_week}.geojson` | `earthquakes.py` | 5m | `/api/hazards/earthquakes` | Hazards |
| FAA airspace status | `nasstatus.faa.gov/api/airport-status-information` (XML) | `faa_status.py` | 10m | `/api/hazards/faa` | Hazards |
| NWS alerts | `api.weather.gov/alerts/active` | `nws_alerts.py` | 15m | `/api/weather/alerts` | Weather |
| Open-Meteo | `api.open-meteo.com/v1/forecast` | `regional_weather.py` | 3h | `/api/weather/*` | Weather |
| NASA EONET | `eonet.gsfc.nasa.gov/api/v3/events` | `climate.py` | 6h | `/api/climate` | Dashboard |
| Astronomy | computed locally (sun/moon) | `astronomy.py` | — | `/api/astronomy` | Dashboard |

## Service Status

statuspage.io-style feeds (`*/api/v2/status.json`), refreshed every 15m via `service_status.py`,
served at `/api/status`, shown on the Status panel/page:

Claude, OpenAI, Cloudflare, GitHub, Stripe, Twilio, Notion, Atlassian, Reddit, Discord, Linear,
Shopify, Vercel.

---

## Notes & caveats

- **538 pollster ratings are vendored** at `backend/app/data/pollster_ratings.csv` because the live
  feed is dead (the GitHub archive is frozen at 2025-02-25); the GitHub URL is a fallback only.
- **Groq** (`api.groq.com`) is a processing dependency used by `summarizer.py` for text generation —
  not an ingested data source.
- **Kalshi requires no authentication** for market data (public read endpoints, ~30 req/s); only
  trading needs signed requests.
