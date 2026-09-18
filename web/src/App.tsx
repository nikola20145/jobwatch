import { useCallback, useEffect, useState } from "react";

import {
  fetchPostings,
  fetchSources,
  fetchStats,
  Posting,
  PostingFilters,
  SourceInfo,
  Stats,
} from "./api";
import { FiltersBar } from "./components/FiltersBar";
import { PostingsTable } from "./components/PostingsTable";
import { StatCards } from "./components/StatCards";

const REFRESH_MS = 60_000;

export default function App() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [postings, setPostings] = useState<Posting[]>([]);
  const [filters, setFilters] = useState<PostingFilters>({
    q: "",
    source: "",
    status: "all",
    matchedOnly: false,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const refresh = useCallback(async (current: PostingFilters) => {
    try {
      const [nextStats, nextPostings] = await Promise.all([
        fetchStats(),
        fetchPostings(current),
      ]);
      setStats(nextStats);
      setPostings(nextPostings);
      setUpdatedAt(new Date());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

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
      <FiltersBar filters={filters} sources={sources} onChange={setFilters} />
      <PostingsTable postings={postings} loading={loading} />

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
