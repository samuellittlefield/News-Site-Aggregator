import { useCallback, useEffect, useState } from "react";

export type Page =
  | "dashboard"
  | "trends"
  | "polling"
  | "markets"
  | "hazards"
  | "weather"
  | "news"
  | "admin";

const PATHS: Record<Page, string> = {
  dashboard: "/",
  trends: "/trends",
  polling: "/polls",
  markets: "/markets",
  hazards: "/hazards",
  weather: "/weather",
  news: "/news",
  admin: "/admin",
};

const PAGE_BY_PATH = Object.fromEntries(
  Object.entries(PATHS).map(([page, path]) => [path, page as Page]),
);

// `/status` was retired into the consolidated `/admin` page — keep resolving
// old bookmarks/links there instead of 404ing or rendering blank.
const LEGACY_REDIRECTS: Record<string, Page> = { "/status": "admin" };

function fromPath(pathname: string): { page: Page; trendId: number | null } {
  const trendMatch = pathname.match(/^\/trends\/(\d+)$/);
  if (trendMatch) return { page: "trends", trendId: Number(trendMatch[1]) };
  const clean = pathname.replace(/\/$/, "") || "/";
  if (clean in LEGACY_REDIRECTS) return { page: LEGACY_REDIRECTS[clean], trendId: null };
  return { page: PAGE_BY_PATH[clean] ?? "dashboard", trendId: null };
}

export function useNavigation() {
  const [state, setState] = useState(() => fromPath(window.location.pathname));

  useEffect(() => {
    // Normalize the URL bar too, so a direct /status visit ends up on /admin.
    const clean = window.location.pathname.replace(/\/$/, "") || "/";
    if (clean in LEGACY_REDIRECTS) {
      window.history.replaceState({}, "", PATHS[LEGACY_REDIRECTS[clean]]);
    }
  }, []);

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
