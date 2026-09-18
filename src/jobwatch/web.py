"""Web dashboard and JSON API over the postings database.

Run locally with `jobwatch serve`, then open http://127.0.0.1:8000.
"""

import html as html_mod
from typing import Any

from fastapi import Depends, FastAPI, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload, sessionmaker

from jobwatch import __version__
from jobwatch.config import Settings
from jobwatch.db.models import AlertSent, Keyword, Posting, Source
from jobwatch.db.session import make_engine, make_session_factory
from jobwatch.matching import posting_matches


def create_app(session_factory: sessionmaker[Session] | None = None) -> FastAPI:
    """Build the FastAPI app. Tests inject their own session_factory."""
    if session_factory is None:
        session_factory = make_session_factory(make_engine(Settings()))

    app = FastAPI(title="jobwatch", version=__version__)

    def get_session():
        with session_factory() as session:
            yield session

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/api/stats")
    def stats(session: Session = Depends(get_session)) -> dict[str, int]:
        return _stats(session)

    @app.get("/api/postings")
    def postings(
        session: Session = Depends(get_session),
        limit: int = Query(default=50, ge=1, le=500),
        q: str | None = Query(default=None, description="substring filter on title"),
        matched_only: bool = Query(default=False),
    ) -> list[dict[str, Any]]:
        return [
            _serialize(posting, matched)
            for posting, matched in _recent_postings(session, limit=limit, q=q, matched_only=matched_only)
        ]

    @app.get("/", response_class=HTMLResponse)
    def dashboard(
        session: Session = Depends(get_session),
        matched_only: bool = Query(default=False),
    ) -> str:
        counts = _stats(session)
        rows = _recent_postings(session, limit=100, q=None, matched_only=matched_only)
        return _render_dashboard(counts, rows, matched_only)

    return app


def _recent_postings(
    session: Session, *, limit: int, q: str | None, matched_only: bool
) -> list[tuple[Posting, bool]]:
    keywords = session.scalars(select(Keyword)).all()
    stmt = (
        select(Posting)
        .options(joinedload(Posting.source), selectinload(Posting.alerts))
        .order_by(Posting.scraped_at.desc(), Posting.id.desc())
    )
    if q:
        stmt = stmt.where(Posting.title.ilike(f"%{q}%"))
    # Matching is Python-side (case-insensitive substring over keyword terms),
    # so filter while streaming instead of in SQL. Fine at this table's scale.
    results: list[tuple[Posting, bool]] = []
    for posting in session.scalars(stmt):
        matched = posting_matches(posting, keywords)
        if matched_only and not matched:
            continue
        results.append((posting, matched))
        if len(results) >= limit:
            break
    return results


def _serialize(posting: Posting, matched: bool) -> dict[str, Any]:
    return {
        "id": posting.id,
        "source": posting.source.name if posting.source else None,
        "external_id": posting.external_id,
        "title": posting.title,
        "url": posting.url,
        "location": posting.location,
        "posted_at": posting.posted_at.isoformat() if posting.posted_at else None,
        "scraped_at": posting.scraped_at.isoformat() if posting.scraped_at else None,
        "closed_at": posting.closed_at.isoformat() if posting.closed_at else None,
        "matched": matched,
        "alerted": any(not a.suppressed for a in posting.alerts),
    }


def _stats(session: Session) -> dict[str, int]:
    def count(stmt) -> int:
        return session.scalar(stmt) or 0

    keywords = session.scalars(select(Keyword)).all()
    pending = 0
    if keywords:
        already = (
            select(AlertSent.id)
            .where(AlertSent.posting_id == Posting.id)
            .exists()
        )
        unalerted = session.scalars(select(Posting).where(~already)).all()
        pending = sum(1 for p in unalerted if posting_matches(p, keywords))
    return {
        "sources": count(select(func.count()).select_from(Source)),
        "postings": count(select(func.count()).select_from(Posting)),
        "open_postings": count(
            select(func.count()).select_from(Posting).where(Posting.closed_at.is_(None))
        ),
        "keywords": count(select(func.count()).select_from(Keyword)),
        "alerts_sent": count(
            select(func.count()).select_from(AlertSent).where(~AlertSent.suppressed)
        ),
        "pending_alerts": pending,
    }


def _render_dashboard(
    counts: dict[str, int], rows: list[tuple[Posting, bool]], matched_only: bool
) -> str:
    esc = html_mod.escape
    chips = "".join(
        f'<div class="chip"><span>{value}</span>{esc(name.replace("_", " "))}</div>'
        for name, value in counts.items()
    )
    body_rows = []
    for posting, matched in rows:
        badges = ""
        if matched:
            badges += '<span class="badge match">match</span>'
        if any(not a.suppressed for a in posting.alerts):
            badges += '<span class="badge sent">alerted</span>'
        if posting.closed_at is not None:
            badges += '<span class="badge closed">closed</span>'
        posted = f"{posting.posted_at:%Y-%m-%d}" if posting.posted_at else "—"
        body_rows.append(
            f'<tr class="{"hit" if matched else ""}">'
            f'<td><a href="{esc(posting.url)}" target="_blank" rel="noopener">{esc(posting.title)}</a>{badges}</td>'
            f"<td>{esc(posting.source.name if posting.source else '?')}</td>"
            f"<td>{esc(posting.location or '—')}</td>"
            f"<td>{posted}</td></tr>"
        )
    toggle = (
        '<a href="/">show all</a>' if matched_only else '<a href="/?matched_only=true">matches only</a>'
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>jobwatch</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 60rem; padding: 0 1rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; }} h1 small {{ color: #888; font-weight: normal; }}
  .chips {{ display: flex; gap: .75rem; flex-wrap: wrap; margin: 1rem 0; }}
  .chip {{ background: #f4f4f5; border-radius: .5rem; padding: .5rem .9rem; font-size: .8rem; color: #555; }}
  .chip span {{ display: block; font-size: 1.2rem; font-weight: 600; color: #111; }}
  table {{ border-collapse: collapse; width: 100%; font-size: .9rem; }}
  th, td {{ text-align: left; padding: .45rem .6rem; border-bottom: 1px solid #e5e5e5; }}
  tr.hit {{ background: #f0fdf4; }}
  a {{ color: #1d4ed8; text-decoration: none; }} a:hover {{ text-decoration: underline; }}
  .badge {{ font-size: .65rem; border-radius: .4rem; padding: .1rem .35rem; margin-left: .4rem; vertical-align: middle; }}
  .badge.match {{ background: #dcfce7; color: #166534; }}
  .badge.sent {{ background: #dbeafe; color: #1e40af; }}
  .badge.closed {{ background: #f3f4f6; color: #6b7280; }}
  .toolbar {{ margin: .5rem 0 1rem; font-size: .85rem; }}
</style></head><body>
<h1>jobwatch <small>v{esc(__version__)}</small></h1>
<div class="chips">{chips}</div>
<div class="toolbar">Latest postings · {toggle} · <a href="/api/postings">JSON</a></div>
<table><thead><tr><th>Title</th><th>Source</th><th>Location</th><th>Posted</th></tr></thead>
<tbody>{"".join(body_rows) or '<tr><td colspan="4">No postings yet — run <code>jobwatch run</code>.</td></tr>'}</tbody></table>
</body></html>"""
