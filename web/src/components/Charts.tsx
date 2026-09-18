import { SourceStat, TimelinePoint } from "../api";

function weekLabel(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function TimelineChart({ points }: { points: TimelinePoint[] }) {
  const max = Math.max(1, ...points.map((p) => p.count));
  return (
    <div className="card">
      <div className="card-title">
        Postings per week
        <span className="legend">
          <i className="swatch total" /> total
          <i className="swatch matched" /> matched
        </span>
      </div>
      {points.length === 0 ? (
        <div className="chart-empty">No data yet</div>
      ) : (
        <>
          <div className="timeline">
            {points.map((p) => (
              <div
                key={p.week}
                className="timeline-col"
                title={`week of ${p.week}: ${p.count} postings, ${p.matched} matched`}
              >
                <div className="timeline-bar" style={{ height: `${(p.count / max) * 100}%` }}>
                  {p.count > 0 && (
                    <div
                      className="timeline-matched"
                      style={{ height: `${(p.matched / p.count) * 100}%` }}
                    />
                  )}
                </div>
              </div>
            ))}
          </div>
          <div className="timeline-labels">
            <span>{weekLabel(points[0].week)}</span>
            <span>{weekLabel(points[points.length - 1].week)}</span>
          </div>
        </>
      )}
    </div>
  );
}

export function SourceBars({ stats }: { stats: SourceStat[] }) {
  const max = Math.max(1, ...stats.map((s) => s.total));
  return (
    <div className="card">
      <div className="card-title">Sources</div>
      {stats.length === 0 ? (
        <div className="chart-empty">No sources registered</div>
      ) : (
        <div className="source-bars">
          {stats.map((s) => (
            <div key={s.name} className="source-row" title={`${s.open} open of ${s.total}`}>
              <span className="source-name">
                {s.name} <em>{s.ats_type}</em>
              </span>
              <span className="source-track">
                <span className="source-fill" style={{ width: `${(s.total / max) * 100}%` }} />
              </span>
              <span className="source-count">
                {s.total}
                {s.matched > 0 && <b> · {s.matched} match</b>}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
