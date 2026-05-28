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

export async function triggerRefresh(): Promise<void> {
  await fetch("/api/refresh", { method: "POST" });
}
