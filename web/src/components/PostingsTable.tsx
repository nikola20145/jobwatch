import { Posting } from "../api";

function formatDate(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toISOString().slice(0, 10);
}

export function PostingsTable({
  postings,
  loading,
}: {
  postings: Posting[];
  loading: boolean;
}) {
  if (loading && postings.length === 0) {
    return <div className="empty">Loading postings…</div>;
  }
  if (postings.length === 0) {
    return (
      <div className="empty">
        Nothing here — adjust the filters, or run <code>jobwatch run</code> to ingest.
      </div>
    );
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>Source</th>
            <th>Location</th>
            <th>Posted</th>
          </tr>
        </thead>
        <tbody>
          {postings.map((p) => (
            <tr key={p.id} className={p.matched ? "hit" : p.closed_at ? "muted" : ""}>
              <td>
                <a href={p.url} target="_blank" rel="noopener">
                  {p.title}
                </a>
                {p.matched && <span className="badge match">match</span>}
                {p.alerted && <span className="badge sent">alerted</span>}
                {p.closed_at && <span className="badge closed">closed</span>}
              </td>
              <td>{p.source ?? "?"}</td>
              <td>{p.location ?? "—"}</td>
              <td>{formatDate(p.posted_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
