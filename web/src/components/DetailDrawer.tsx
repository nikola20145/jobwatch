import { useEffect } from "react";

import { Posting } from "../api";

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

export function DetailDrawer({
  posting,
  onClose,
}: {
  posting: Posting | null;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!posting) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [posting, onClose]);

  if (!posting) return null;

  const rows: Array<[string, string]> = [
    ["Source", posting.source ?? "?"],
    ["Location", posting.location ?? "—"],
    ["Posted", formatDateTime(posting.posted_at)],
    ["First scraped", formatDateTime(posting.scraped_at)],
    ["Last seen on board", formatDateTime(posting.last_seen_at)],
    ["Closed", posting.closed_at ? formatDateTime(posting.closed_at) : "still open"],
    ["ATS job id", posting.external_id],
  ];

  return (
    <>
      <div className="backdrop" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-label="Posting details">
        <div className="drawer-head">
          <h2>{posting.title}</h2>
          <button className="ghost" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <div className="drawer-badges">
          {posting.matched && <span className="badge match">match</span>}
          {posting.alerted && <span className="badge sent">alerted</span>}
          {posting.closed_at && <span className="badge closed">closed</span>}
        </div>
        <dl className="drawer-fields">
          {rows.map(([label, value]) => (
            <div key={label} className="drawer-row">
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        <a className="button" href={posting.url} target="_blank" rel="noopener">
          Open posting ↗
        </a>
      </aside>
    </>
  );
}
