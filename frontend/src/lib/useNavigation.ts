import { useCallback, useEffect, useState } from "react";

export type Page =
  | "dashboard"
  | "trends"
  | "polling"
  | "markets"
  | "hazards"
  | "weather"
  | "news"
  | "status"
  | "admin";

const PATHS: Record<Page, string> = {
  dashboard: "/",
  trends: "/trends",
  polling: "/polls",
  markets: "/markets",
  hazards: "/hazards",
  weather: "/weather",
  news: "/news",
  status: "/status",
  admin: "/admin",
};

const PAGE_BY_PATH = Object.fromEntries(
  Object.entries(PATHS).map(([page, path]) => [path, page as Page]),
);

function fromPath(pathname: string): { page: Page; trendId: number | null } {
  const trendMatch = pathname.match(/^\/trends\/(\d+)$/);
  if (trendMatch) return { page: "trends", trendId: Number(trendMatch[1]) };
  return { page: PAGE_BY_PATH[pathname.replace(/\/$/, "") || "/"] ?? "dashboard", trendId: null };
}

export function useNavigation() {
  const [state, setState] = useState(() => fromPath(window.location.pathname));

  useEffect(() => {
    const onPop = () => setState(fromPath(window.location.pathname));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = useCallback((page: Page) => {
    window.history.pushState({}, "", PATHS[page]);
    setState({ page, trendId: null });
  }, []);

  const openTrend = useCallback((id: number) => {
    window.history.pushState({}, "", `/trends/${id}`);
    setState((s) => ({ ...s, trendId: id }));
  }, []);

  const back = useCallback(() => window.history.back(), []);

  return { page: state.page, selectedTrendId: state.trendId, navigate, openTrend, back };
}
