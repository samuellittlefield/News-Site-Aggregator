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

export async function triggerRefresh(): Promise<void> {
  await fetch("/api/refresh", { method: "POST" });
}
