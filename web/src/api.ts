export interface Posting {
  id: number;
  source: string | null;
  external_id: string;
  title: string;
  url: string;
  location: string | null;
  posted_at: string | null;
  scraped_at: string | null;
  closed_at: string | null;
  last_seen_at: string | null;
  matched: boolean;
  alerted: boolean;
}

export interface TimelinePoint {
  week: string;
  count: number;
  matched: number;
}

export interface SourceStat {
  name: string;
  ats_type: string;
  enabled: boolean;
  total: number;
  open: number;
  matched: number;
}

export interface Stats {
  sources: number;
  postings: number;
  open_postings: number;
  keywords: number;
  alerts_sent: number;
  pending_alerts: number;
}

export interface SourceInfo {
  id: number;
  name: string;
  ats_type: string;
  enabled: boolean;
}

export interface PostingFilters {
  q: string;
  source: string;
  status: "all" | "open" | "closed";
  matchedOnly: boolean;
}

async function get<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} responded ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchStats(): Promise<Stats> {
  return get<Stats>("/api/stats");
}

export function fetchSources(): Promise<SourceInfo[]> {
  return get<SourceInfo[]>("/api/sources");
}

export function fetchPostings(
  filters: PostingFilters,
  limit = 50,
  offset = 0,
): Promise<Posting[]> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (filters.q) params.set("q", filters.q);
  if (filters.source) params.set("source", filters.source);
  if (filters.status !== "all") params.set("status", filters.status);
  if (filters.matchedOnly) params.set("matched_only", "true");
  return get<Posting[]>(`/api/postings?${params}`);
}

export function fetchTimeline(): Promise<TimelinePoint[]> {
  return get<TimelinePoint[]>("/api/stats/timeline");
}

export function fetchSourceStats(): Promise<SourceStat[]> {
  return get<SourceStat[]>("/api/stats/sources");
}
