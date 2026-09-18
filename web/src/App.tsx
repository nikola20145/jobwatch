import { useCallback, useEffect, useRef, useState } from "react";

import {
  fetchPostings,
  fetchSources,
  fetchSourceStats,
  fetchStats,
  fetchTimeline,
  Posting,
  PostingFilters,
  SourceInfo,
  SourceStat,
  Stats,
  TimelinePoint,
} from "./api";
import { SourceBars, TimelineChart } from "./components/Charts";
import { DetailDrawer } from "./components/DetailDrawer";
import { FiltersBar } from "./components/FiltersBar";
import { PostingsTable } from "./components/PostingsTable";
import { StatCards } from "./components/StatCards";

const REFRESH_MS = 60_000;
const PAGE_SIZE = 50;

export default function App() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [sourceStats, setSourceStats] = useState<SourceStat[]>([]);
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [postings, setPostings] = useState<Posting[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [filters, setFilters] = useState<PostingFilters>({
    q: "",
    source: "",
    status: "all",
    matchedOnly: false,
  });
  const [selected, setSelected] = useState<Posting | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async (current: PostingFilters) => {
    try {
      const [nextStats, nextPostings, nextTimeline, nextSourceStats] = await Promise.all([
        fetchStats(),
        fetchPostings(current, PAGE_SIZE, 0),
        fetchTimeline(),
        fetchSourceStats(),
      ]);
      setStats(nextStats);
      setPostings(nextPostings);
      setHasMore(nextPostings.length === PAGE_SIZE);
      setTimeline(nextTimeline);
      setSourceStats(nextSourceStats);
      setUpdatedAt(new Date());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  const loadMore = useCallback(async () => {
    try {
      const next = await fetchPostings(filters, PAGE_SIZE, postings.length);
      setPostings((current) => [...current, ...next]);
      setHasMore(next.length === PAGE_SIZE);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [filters, postings.length]);

  useEffect(() => {
    fetchSources()
      .then(setSources)
      .catch(() => setSources([]));
  }, []);

  // Debounce the text search; other filter changes apply immediately (the
  // same 200ms delay is imperceptible for a click).
  useEffect(() => {
    setLoading(true);
    const handle = window.setTimeout(() => void refresh(filters), 200);
    return () => window.clearTimeout(handle);
  }, [filters, refresh]);

  useEffect(() => {
    const handle = window.setInterval(() => void refresh(filters), REFRESH_MS);
    return () => window.clearInterval(handle);
  }, [filters, refresh]);

  // "/" focuses search, like GitHub.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing = target && ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName);
      if (e.key === "/" && !typing) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="app">
      <header className="header">
        <h1>
          <span className="logo" aria-hidden>
            🔎
          </span>
          jobwatch
        </h1>
        <div className="header-meta">
          {updatedAt && <span>updated {updatedAt.toLocaleTimeString()}</span>}
          <button className="ghost" onClick={() => void refresh(filters)}>
            Refresh
          </button>
        </div>
      </header>

      {error && <div className="banner error">API error: {error}</div>}

      <StatCards stats={stats} />

      <div className="charts-row">
        <TimelineChart points={timeline} />
        <SourceBars stats={sourceStats} />
      </div>

      <FiltersBar filters={filters} sources={sources} onChange={setFilters} searchRef={searchRef} />
      <PostingsTable postings={postings} loading={loading} onSelect={setSelected} />
      {hasMore && (
        <button className="load-more" onClick={() => void loadMore()}>
          Load more
        </button>
      )}

      <DetailDrawer posting={selected} onClose={() => setSelected(null)} />

      <footer className="footer">
        <a href="/api/postings" target="_blank" rel="noopener">
          JSON API
        </a>
        <span> · </span>
        <a href="https://github.com/nikola20145/jobwatch" target="_blank" rel="noopener">
          GitHub
        </a>
      </footer>
    </div>
  );
}
