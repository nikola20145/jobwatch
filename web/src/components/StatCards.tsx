import { Stats } from "../api";

const LABELS: Array<{ key: keyof Stats; label: string; accent?: boolean }> = [
  { key: "sources", label: "sources" },
  { key: "postings", label: "postings" },
  { key: "open_postings", label: "open" },
  { key: "keywords", label: "keywords" },
  { key: "alerts_sent", label: "alerts sent" },
  { key: "pending_alerts", label: "pending", accent: true },
];

export function StatCards({ stats }: { stats: Stats | null }) {
  return (
    <div className="stat-grid">
      {LABELS.map(({ key, label, accent }) => (
        <div key={key} className={`stat-card${accent ? " accent" : ""}`}>
          <span className="stat-value">{stats ? stats[key] : "—"}</span>
          <span className="stat-label">{label}</span>
        </div>
      ))}
    </div>
  );
}
