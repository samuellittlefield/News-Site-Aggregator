import { useEffect, useState } from "react";

export interface Article {
  id: number;
  headline: string | null;
  url: string | null;
  source: string | null;
  published_at: string | null;
  description: string | null;
}

export interface Summary {
  body: string;
  generated_at: string;
}

export interface WikiPage {
  id: number;
  title: string;
  description: string | null;
  extract: string | null;
  url: string;
  thumbnail_url: string | null;
  is_primary: boolean;
  search_rank: number;
}

export interface PageView {
  view_date: string;
  views: number;
}

export interface Trend {
  id: number;
  title: string;
  traffic_volume: string | null;
  fetched_at: string;
  first_seen_at: string | null;
  appearance_count: number;
  category: string | null;
  velocity_abs: number;
  velocity_pct: number;
  rank_velocity: number;
  geo: string;
  summary: Summary | null;
  wiki_pages: WikiPage[];
  cluster_id: number | null;
  cluster_name: string | null;
  is_active?: boolean;
  signal_score: number;
  source: string;
  sources_list: string[];
  trend_window: string | null;
  validated_by: number;
}

export interface ClimateEvent {
  id: number;
  eonet_id: string;
  title: string;
  category: string;
  category_label: string;
  category_icon: string;
  status: string;
  coordinates: { lat: number; lon: number } | null;
  start_date: string | null;
  magnitude: number | null;
  magnitude_unit: string | null;
  source_url: string | null;
  ai_summary: string | null;
  location: string | null;
  fetched_at: string;
}

export interface TrendDetail extends Trend {
  articles: Article[];
}

// In dev, Vite proxies /api → localhost:8000. In production, point at the Railway URL.
const BASE = import.meta.env.VITE_API_URL ?? "";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export function useTrends() {
  const [trends, setTrends] = useState<Trend[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    get<Trend[]>("/api/trends")
      .then((data) => {
        setTrends(data);
        setError(null);
      })
      .catch((e: unknown) => setError(String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  return { trends, loading, error, refresh: load };
}

export function useTrendDetail(id: number) {
  const [trend, setTrend] = useState<TrendDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    get<TrendDetail>(`/api/trends/${id}`)
      .then((data) => {
        setTrend(data);
        setError(null);
      })
      .catch((e: unknown) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [id]);

  return { trend, loading, error };
}

export interface HistoryPoint {
  captured_at: string;
  rank: number | null;
  traffic_volume: string | null;
}

export function usePageViews(trendId: number) {
  const [views, setViews] = useState<PageView[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    get<PageView[]>(`/api/trends/${trendId}/pageviews`)
      .then((data) => { setViews(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [trendId]);

  return { views, loading };
}

export function useTrendHistory(id: number) {
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    get<HistoryPoint[]>(`/api/trends/${id}/history`)
      .then((data) => { setHistory(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [id]);

  return { history, loading };
}

export function useBreakoutTrends() {
  const [breakout, setBreakout] = useState<Trend[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    get<Trend[]>("/api/trends/breakout?limit=8")
      .then((data) => { setBreakout(data); setLoading(false); })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  return { breakout, loading, refresh: load };
}

export function useRisingTrends() {
  const [rising, setRising] = useState<Trend[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    get<Trend[]>("/api/trends/rising?limit=5")
      .then((data) => { setRising(data); setLoading(false); })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  return { rising, loading, refresh: load };
}

export function useClimateEvents() {
  const [events, setEvents] = useState<ClimateEvent[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    get<ClimateEvent[]>("/api/climate")
      .then((data) => { setEvents(data); setLoading(false); })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 10 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  return { events, loading, refresh: load };
}

export interface ExtremeCluster {
  category: string;
  label: string;
  icon: string;
  count: number;
  worst_title: string;
  worst_location: string | null;
  worst_date: string | null;
  worst_magnitude: number | null;
  worst_magnitude_unit: string | null;
  worst_summary: string | null;
  worst_source_url: string | null;
}

export interface RegionalWeather {
  region: string;
  city: string;
  temp_max_f: number | null;
  temp_min_f: number | null;
  precipitation_mm: number | null;
  condition: string | null;
}

export interface NewsArticle {
  id: number;
  category: string;
  title: string;
  url: string | null;
  source: string | null;
  published_at: string | null;
  description: string | null;
  ai_summary: string | null;
}

export interface AstronomyData {
  moon: {
    phase: string;
    illumination: number;
    next_full: string;
    next_full_iso: string;
    next_new: string;
    is_blue_moon: boolean;
    rise: string | null;
    set: string | null;
  };
  planets: { name: string; visible: boolean; altitude: number; rise: string | null; set: string | null }[];
  events: { title: string; date: string; date_iso: string; description: string; icon: string }[];
  location: string;
}

export interface DayForecast {
  date: string;
  day_name: string;
  temp_max_f: number | null;
  temp_min_f: number | null;
  precipitation_mm: number | null;
  wind_mph: number | null;
  condition: string | null;
}

export interface RegionalForecast {
  region: string;
  city: string;
  days: DayForecast[];
}

export function useRegionalForecast(region: string | null) {
  const [forecast, setForecast] = useState<RegionalForecast | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!region) { setForecast(null); return; }
    setLoading(true);
    get<RegionalForecast>(`/api/weather/forecast/${encodeURIComponent(region)}`)
      .then(d => { setForecast(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [region]);

  return { forecast, loading };
}

export function usePoliticalTrends() {
  const [trends, setTrends] = useState<Trend[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    get<Trend[]>("/api/trends/political")
      .then(d => { setTrends(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);
  return { trends, loading };
}

export function useAnomalyTrends() {
  const [trends, setTrends] = useState<Trend[]>([]);
  const [loading, setLoading] = useState(true);
  const load = () => {
    setLoading(true);
    get<Trend[]>("/api/trends/anomalies")
      .then(d => { setTrends(d); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);
  return { trends, loading, refresh: load };
}

export function useExtremeWeather() {
  const [clusters, setClusters] = useState<ExtremeCluster[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    get<ExtremeCluster[]>("/api/weather/extreme")
      .then(d => { setClusters(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);
  return { clusters, loading };
}

export function useRegionalWeather() {
  const [regions, setRegions] = useState<RegionalWeather[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    get<RegionalWeather[]>("/api/weather/regional")
      .then(d => { setRegions(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);
  return { regions, loading };
}

export function useNews(category: string) {
  const [articles, setArticles] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    get<NewsArticle[]>(`/api/news/${category}`)
      .then(d => { setArticles(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [category]);
  return { articles, loading };
}

export interface ServiceStatus {
  id: number;
  name: string;
  indicator: string;  // none | minor | major | critical
  description: string | null;
  icon: string | null;
  page_url: string | null;
  fetched_at: string;
}

export function useServiceStatus() {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    get<ServiceStatus[]>("/api/status")
      .then(d => { setServices(d); setLoading(false); })
      .catch(() => setLoading(false));
    const id = setInterval(() => {
      get<ServiceStatus[]>("/api/status").then(setServices).catch(() => {});
    }, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, []);
  return { services, loading };
}

export function useAstronomy() {
  const [sky, setSky] = useState<AstronomyData | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    get<AstronomyData>("/api/astronomy")
      .then(d => { setSky(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);
  return { sky, loading };
}

export interface NWSAlert {
  id: number;
  nws_id: string;
  event: string;
  headline: string | null;
  severity: string;
  urgency: string | null;
  area_desc: string | null;
  sender_name: string | null;
  wfo_url: string | null;
  onset: string | null;
  expires: string | null;
}

export function useWeatherAlerts() {
  const [alerts, setAlerts] = useState<NWSAlert[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    get<NWSAlert[]>("/api/weather/alerts")
      .then(d => { setAlerts(d); setLoading(false); })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  return { alerts, loading };
}

export interface HousePoll {
  id: number;
  poll_id: string;
  pollster: string;
  grade: string | null;
  state: string;
  district: number;
  start_date: string | null;
  end_date: string | null;
  sample_size: number | null;
  population: string | null;
  dem: number | null;
  rep: number | null;
  source_url: string | null;
}

export interface DistrictCandidate {
  name: string;
  party: string | null;                 // DEM/REP/IND/...
  incumbent_challenge: string | null;    // I / C / O
  fundraising_total: number | null;
  fec_id: string | null;                 // → fec.gov/data/candidate/{fec_id}
}

export interface DistrictLatestPoll {
  margin: number | null;
  dem: number | null;
  rep: number | null;
  pollster: string | null;
  date: string | null;
}

export interface DistrictData {
  state: string;
  district: string;                      // "1".."52" or "AL"
  label: string;                         // "PA-08"
  q: number;                             // axial hex coords (pointy-top)
  r: number;
  pres_margin_2024: number | null;       // D−R, drives hex color
  house_margin_2024: number | null;
  incumbent_party: string | null;        // D / R / O
  cook_rating: string | null;
  rating: string;                        // derived full-coverage label
  poll_count: number;
  latest_poll: DistrictLatestPoll | null;
  candidates: DistrictCandidate[];
}

export interface GenericBallot {
  source: string;
  rep: number;
  dem: number;
}

export function useHousePolls() {
  const [polls, setPolls] = useState<HousePoll[]>([]);
  const [loading, setLoading] = useState(true);
  const load = () => {
    get<HousePoll[]>("/api/polls/house")
      .then(d => { setPolls(d); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(() => { load(); const id = setInterval(load, 30 * 60 * 1000); return () => clearInterval(id); }, []);
  return { polls, loading };
}

export function useHouseDistricts() {
  const [districts, setDistricts] = useState<DistrictData[]>([]);
  const [loading, setLoading] = useState(true);
  const load = () => {
    get<DistrictData[]>("/api/polls/house/districts")
      .then(d => { setDistricts(d); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(() => { load(); const id = setInterval(load, 30 * 60 * 1000); return () => clearInterval(id); }, []);
  return { districts, loading };
}

export function useGenericBallot() {
  const [ballot, setBallot] = useState<GenericBallot[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    get<GenericBallot[]>("/api/polls/generic-ballot")
      .then(d => { setBallot(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);
  return { ballot, loading };
}

// ── Economist/YouGov crosstabs ────────────────────────────────────────────────

export interface EconQuestion {
  key: string;
  label: string;
  report_count: number;
  latest_net: number | null;
}

export function useEconQuestions() {
  const [questions, setQuestions] = useState<EconQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    get<EconQuestion[]>("/api/economist/questions")
      .then(d => { setQuestions(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);
  return { questions, loading };
}

export interface EconTrendPoint {
  report_id: number;
  end_date: string | null;
  sample_size: number | null;
  topline: Record<string, number>;
  net: number | null;
}

export interface EconBlock {
  group_line: string;
  columns: string[];
  rows: Record<string, number[]>;
  ns: Record<string, number>;
}

export interface EconCrosstab {
  report_id: number;
  end_date: string | null;
  sample_size: number | null;
  source_url: string | null;
  question_key: string;
  question_code: string | null;
  question_title: string | null;
  question_text: string | null;
  blocks: EconBlock[];
}

export function useEconTrend(questionKey: string) {
  const [points, setPoints] = useState<EconTrendPoint[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    setLoading(true);
    get<EconTrendPoint[]>(`/api/economist/trend/${questionKey}`)
      .then(d => { setPoints(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [questionKey]);
  return { points, loading };
}

export function useEconCrosstab(questionKey: string) {
  const [crosstab, setCrosstab] = useState<EconCrosstab | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    setLoading(true);
    get<EconCrosstab>(`/api/economist/crosstab/${questionKey}`)
      .then(d => { setCrosstab(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [questionKey]);
  return { crosstab, loading };
}

export interface IssueTaxonomyItem {
  code: string;
  label: string;
}

export interface IssueTag {
  id: number;
  issue_code: string;
  issue_label: string;
  ai_suggested: boolean;
  confirmed: boolean;
  rejected: boolean;
  confidence: number | null;
  supporting_text: string | null;
  created_at: string;
}

export interface CandidateSummary {
  id: number;
  fec_id: string | null;
  name: string;
  party: string | null;
  state: string;
  district: number | null;
  office: string;
  incumbent_challenge: string | null;
  primary_date: string | null;
  primary_status: string | null;
  general_status: string | null;
  fundraising_total: number | null;
  cook_rating: string | null;
  notes: string | null;
  confirmed_issues: string[];
}

export interface CandidateDetail extends CandidateSummary {
  issue_tags: IssueTag[];
}

export interface PendingTag {
  tag_id: number;
  candidate_id: number;
  candidate_name: string;
  candidate_office: string;
  candidate_state: string;
  candidate_district: number | null;
  candidate_party: string | null;
  issue_code: string;
  issue_label: string;
  confidence: number | null;
  supporting_text: string | null;
}

export function useCandidates(office?: string, state?: string) {
  const [candidates, setCandidates] = useState<CandidateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const params = new URLSearchParams();
    if (office) params.set("office", office);
    if (state) params.set("state", state);
    get<CandidateSummary[]>(`/api/candidates?${params}`)
      .then(d => { setCandidates(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [office, state]);
  return { candidates, loading };
}

export function usePendingTags() {
  const [tags, setTags] = useState<PendingTag[]>([]);
  const [loading, setLoading] = useState(true);
  const load = () => {
    get<PendingTag[]>("/api/candidates/issues/pending")
      .then(d => { setTags(d); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);
  return { tags, loading, refresh: load };
}

export function useIssueTaxonomy() {
  const [taxonomy, setTaxonomy] = useState<IssueTaxonomyItem[]>([]);
  useEffect(() => {
    get<IssueTaxonomyItem[]>("/api/candidates/taxonomy")
      .then(setTaxonomy)
      .catch(() => {});
  }, []);
  return taxonomy;
}

export async function confirmTag(candidateId: number, tagId: number): Promise<void> {
  await fetch(`/api/candidates/${candidateId}/issues/${tagId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmed: true, rejected: false }),
  });
}

export async function rejectTag(candidateId: number, tagId: number): Promise<void> {
  await fetch(`/api/candidates/${candidateId}/issues/${tagId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rejected: true }),
  });
}

export async function addManualTag(
  candidateId: number,
  issueCode: string,
  supportingText?: string,
): Promise<void> {
  await fetch(`/api/candidates/${candidateId}/issues`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ issue_code: issueCode, supporting_text: supportingText }),
  });
}

export async function triggerRefresh(): Promise<void> {
  await fetch("/api/refresh", { method: "POST" });
}

// ── VoteHub polls ─────────────────────────────────────────────────────────────

export interface VoteHubPoll {
  id: number;
  votehub_id: string;
  poll_type: string;
  subject: string | null;
  pollster: string | null;
  sponsors: string[];
  start_date: string | null;
  end_date: string | null;
  sample_size: number | null;
  population: string | null;
  approve: number | null;
  disapprove: number | null;
  dem: number | null;
  rep: number | null;
  url: string | null;
  fetched_at: string;
}

export interface ApprovalAverage {
  approve: number;
  disapprove: number;
  net: number;
  n_polls: number;
  window_days: number;
}

export interface GenericBallotAverage {
  dem: number;
  rep: number;
  margin: number;
  n_polls: number;
  window_days: number;
}

export interface VoteHubApprovalSet {
  average: ApprovalAverage | null;
  polls: VoteHubPoll[];
}

export interface VoteHubGenericSet {
  average: GenericBallotAverage | null;
  polls: VoteHubPoll[];
}

export function useVoteHubApproval() {
  const [data, setData] = useState<VoteHubApprovalSet | null>(null);
  const [loading, setLoading] = useState(true);
  const load = () => {
    get<VoteHubApprovalSet>("/api/votehub/approval")
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(() => { load(); const id = setInterval(load, 10 * 60 * 1000); return () => clearInterval(id); }, []);
  return { data, loading };
}

export function useVoteHubGenericBallot() {
  const [data, setData] = useState<VoteHubGenericSet | null>(null);
  const [loading, setLoading] = useState(true);
  const load = () => {
    get<VoteHubGenericSet>("/api/votehub/generic-ballot")
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(() => { load(); const id = setInterval(load, 10 * 60 * 1000); return () => clearInterval(id); }, []);
  return { data, loading };
}

// ── Prediction markets ────────────────────────────────────────────────────────

export interface Market {
  id: number;
  platform: string;
  market_id: string;
  question: string;
  slug: string | null;
  url: string | null;
  event_title: string | null;
  outcomes: { name: string; price: number }[];
  yes_price: number | null;
  volume_24h: number | null;
  liquidity: number | null;
  end_date: string | null;
  fetched_at: string;
}

export interface MarketSnapshotPoint {
  yes_price: number | null;
  captured_at: string;
}

export function useMarkets(limit = 30) {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [loading, setLoading] = useState(true);
  const load = () => {
    get<Market[]>(`/api/markets?limit=${limit}`)
      .then(d => { setMarkets(d); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(() => { load(); const id = setInterval(load, 2 * 60 * 1000); return () => clearInterval(id); }, [limit]);
  return { markets, loading };
}

export function useMarketHistory(marketId: number, days = 14) {
  const [history, setHistory] = useState<MarketSnapshotPoint[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    get<MarketSnapshotPoint[]>(`/api/markets/${marketId}/history?days=${days}`)
      .then(d => { setHistory(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [marketId, days]);
  return { history, loading };
}

// ── Congress forecast (control-of-chamber markets + model link-outs) ──────────

export interface ForecastSource {
  platform: string;
  dem_prob: number | null;
  rep_prob: number | null;
  url: string | null;
  dem_market_id: number | null;
  rep_market_id: number | null;
}

export interface ChamberModel {
  dem_prob: number;
  rep_prob: number;
  median_dem_seats: number;
  p10_dem_seats: number;
  p90_dem_seats: number;
  n_sims: number;
  note: string;
  swing_d: number;
  tau: number;
  delta: number;
}

export interface ChamberForecast {
  chamber: string;
  title: string;
  dem_prob: number | null;
  rep_prob: number | null;
  sources: ForecastSource[];
  model: ChamberModel | null;
}

export interface ForecastReference {
  name: string;
  publisher: string;
  url: string;
  note: string;
}

export interface CongressForecast {
  chambers: ChamberForecast[];
  references: ForecastReference[];
}

export function useCongressForecast() {
  const [forecast, setForecast] = useState<CongressForecast | null>(null);
  const [loading, setLoading] = useState(true);
  const load = () => {
    get<CongressForecast>("/api/forecasts/congress")
      .then(d => { setForecast(d); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(() => { load(); const id = setInterval(load, 10 * 60 * 1000); return () => clearInterval(id); }, []);
  return { forecast, loading };
}

// ── Experimental model knobs (live tuning) ────────────────────────────────────

export interface ModelKnobs {
  tau: number;
  delta_house: number;
  delta_senate: number;
  incumbency_adv: number;
  senate_prior_blend: number;
  fundraising_coef: number;
}

export interface ModelSim {
  house: ChamberModel;
  senate: ChamberModel;
  defaults: ModelKnobs;
}

export const MODEL_KNOB_META: { key: keyof ModelKnobs; label: string; min: number; max: number; step: number; help: string }[] = [
  { key: "tau", label: "National error σ (τ)", min: 0, max: 10, step: 0.5, help: "Spread of the shared national swing — bigger = more correlated uncertainty across all seats." },
  { key: "delta_house", label: "House seat noise (δ)", min: 0.5, max: 15, step: 0.5, help: "Per-district idiosyncratic noise." },
  { key: "delta_senate", label: "Senate seat noise (δ)", min: 0.5, max: 15, step: 0.5, help: "Per-seat idiosyncratic noise — Senate is more candidate-driven." },
  { key: "incumbency_adv", label: "Incumbency advantage", min: 0, max: 15, step: 0.5, help: "Margin nudge toward the party holding the seat." },
  { key: "senate_prior_blend", label: "Senate prior blend", min: 0, max: 1, step: 0.05, help: "0 = pure 2024 presidential lean · 1 = pure last Senate result (more incumbency)." },
  { key: "fundraising_coef", label: "Fundraising weight", min: 0, max: 10, step: 0.5, help: "Margin shift per 10× cash advantage (FEC). 0 = ignore fundraising." },
];

export function useModelSim(knobs: ModelKnobs | null) {
  const [sim, setSim] = useState<ModelSim | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!knobs) { setSim(null); return; }
    setLoading(true);
    const q = new URLSearchParams(
      Object.fromEntries(Object.entries(knobs).map(([k, v]) => [k, String(v)])),
    );
    const t = setTimeout(() => {
      get<ModelSim>(`/api/forecasts/model?${q}`)
        .then(d => { setSim(d); setLoading(false); })
        .catch(() => setLoading(false));
    }, 200); // debounce slider drags
    return () => clearTimeout(t);
  }, [knobs]);
  return { sim, loading };
}

// ── Hazards: earthquakes + FAA ────────────────────────────────────────────────

export interface Earthquake {
  id: number;
  usgs_id: string;
  magnitude: number | null;
  place: string | null;
  time: string | null;
  lat: number | null;
  lng: number | null;
  depth_km: number | null;
  alert_level: string | null;
  tsunami: boolean;
  felt: number | null;
  url: string | null;
}

export interface EarthquakeSet {
  summary: { count: number; max_magnitude: number | null; significant: Earthquake | null };
  earthquakes: Earthquake[];
}

export interface FaaEvent {
  airport: string;
  type: string;
  reason: string | null;
  avg_delay: string | null;
  end_time: string | null;
}

export interface FaaStatus {
  events: FaaEvent[];
  fetched_at: string | null;
}

export function useEarthquakes(minMag = 2.5, hours = 24) {
  const [data, setData] = useState<EarthquakeSet | null>(null);
  const [loading, setLoading] = useState(true);
  const load = () => {
    get<EarthquakeSet>(`/api/hazards/earthquakes?min_mag=${minMag}&hours=${hours}`)
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(() => { load(); const id = setInterval(load, 5 * 60 * 1000); return () => clearInterval(id); }, [minMag, hours]);
  return { data, loading };
}

export function useFaaStatus() {
  const [data, setData] = useState<FaaStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const load = () => {
    get<FaaStatus>("/api/hazards/faa")
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  };
  useEffect(() => { load(); const id = setInterval(load, 5 * 60 * 1000); return () => clearInterval(id); }, []);
  return { data, loading };
}
