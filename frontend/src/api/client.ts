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

export interface DistrictData {
  state: string;
  district: number;
  cook_rating: string | null;
  dem_2024: number | null;
  rep_2024: number | null;
  margin_2024: number | null;
  lat: number;
  lng: number;
  incumbent_party: string | null;
  poll_count: number;
  poll_intensity: number;
  height: number;
  latest_margin: number | null;
  latest_dem: number | null;
  latest_rep: number | null;
  latest_pollster: string | null;
  latest_date: string | null;
  color: [number, number, number, number];
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
