import { RefObject } from "react";

import { PostingFilters, SourceInfo } from "../api";

interface Props {
  filters: PostingFilters;
  sources: SourceInfo[];
  onChange: (next: PostingFilters) => void;
  searchRef: RefObject<HTMLInputElement>;
}

export function FiltersBar({ filters, sources, onChange, searchRef }: Props) {
  return (
    <div className="filters">
      <input
        ref={searchRef}
        type="search"
        placeholder="Search titles…  ( / )"
        value={filters.q}
        onChange={(e) => onChange({ ...filters, q: e.target.value })}
        aria-label="Search titles"
      />
      <select
        value={filters.source}
        onChange={(e) => onChange({ ...filters, source: e.target.value })}
        aria-label="Filter by source"
      >
        <option value="">All sources</option>
        {sources.map((s) => (
          <option key={s.id} value={s.name}>
            {s.name}
          </option>
        ))}
      </select>
      <select
        value={filters.status}
        onChange={(e) =>
          onChange({ ...filters, status: e.target.value as PostingFilters["status"] })
        }
        aria-label="Filter by status"
      >
        <option value="all">Open + closed</option>
        <option value="open">Open only</option>
        <option value="closed">Closed only</option>
      </select>
      <label className="toggle">
        <input
          type="checkbox"
          checked={filters.matchedOnly}
          onChange={(e) => onChange({ ...filters, matchedOnly: e.target.checked })}
        />
        Matches only
      </label>
    </div>
  );
}
