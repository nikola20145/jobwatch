"""One full run: fetch every enabled source, ingest, match, alert."""

import logging
from dataclasses import dataclass, field
from typing import Callable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from jobwatch.alerts.base import Alerter
from jobwatch.db.models import AlertSent, Keyword, Posting, Source
from jobwatch.ingest import IngestStats, ingest_postings
from jobwatch.matching import posting_matches
from jobwatch.scrapers import greenhouse, lever
from jobwatch.scrapers.base import ScrapedPosting

log = logging.getLogger(__name__)

Fetcher = Callable[[Source], list[ScrapedPosting]]

FETCHERS: dict[str, Fetcher] = {
    "greenhouse": lambda source: greenhouse.fetch_board(source.board_token),
    "lever": lambda source: lever.fetch_board(source.board_token),
}


@dataclass
class RunReport:
    ingest: dict[str, IngestStats] = field(default_factory=dict)
    alerts_sent: int = 0
    alerts_suppressed: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        inserted = sum(s.inserted for s in self.ingest.values())
        updated = sum(s.updated for s in self.ingest.values())
        unchanged = sum(s.unchanged for s in self.ingest.values())
        return (
            f"sources={len(self.ingest)} inserted={inserted} updated={updated} "
            f"unchanged={unchanged} alerts_sent={self.alerts_sent} "
            f"alerts_suppressed={self.alerts_suppressed} errors={len(self.errors)}"
        )


def run_once(
    session: Session,
    *,
    alerter: Alerter | None,
    fetchers: dict[str, Fetcher] | None = None,
    suppress_alerts: bool = False,
) -> RunReport:
    """Fetch, ingest, and alert. Safe to re-run: ingestion dedupes on
    (source, external_id) and alerting dedupes on (posting, channel).

    With suppress_alerts=True, matching postings are recorded as handled
    without sending anything — used to seed a fresh database so only postings
    that appear *after* seeding trigger real alerts.
    """
    fetchers = fetchers if fetchers is not None else FETCHERS
    report = RunReport()

    for source in session.scalars(select(Source).where(Source.enabled)).all():
        fetcher = fetchers.get(source.ats_type)
        if fetcher is None:
            report.errors.append(f"{source.name}: no fetcher for ats_type {source.ats_type!r}")
            log.error("no fetcher registered for ats_type %r (source %r)", source.ats_type, source.name)
            continue
        try:
            scraped = fetcher(source)
        except Exception as exc:  # one failing board must not kill the run
            report.errors.append(f"{source.name}: fetch failed: {exc}")
            log.exception("fetch failed for source %r", source.name)
            continue
        stats = ingest_postings(session, source, scraped)
        session.commit()
        report.ingest[source.name] = stats
        log.info(
            "source %s: %d fetched, %d new, %d updated, %d unchanged",
            source.name, len(scraped), stats.inserted, stats.updated, stats.unchanged,
        )

    _alert_phase(session, report, alerter=alerter, suppress_alerts=suppress_alerts)
    return report


def _alert_phase(
    session: Session,
    report: RunReport,
    *,
    alerter: Alerter | None,
    suppress_alerts: bool,
) -> None:
    if alerter is None and not suppress_alerts:
        log.info("no alert channel configured; skipping alert phase")
        return

    channel = alerter.channel if alerter is not None else "telegram"
    keywords = session.scalars(select(Keyword)).all()
    if not keywords:
        log.warning("no keywords saved; nothing can match — add some with `jobwatch add-keyword`")
        return

    pending = pending_alerts(session, keywords, channel)
    for posting in pending:
        if suppress_alerts:
            session.add(AlertSent(posting_id=posting.id, channel=channel, suppressed=True))
            report.alerts_suppressed += 1
            continue
        assert alerter is not None
        try:
            alerter.send(posting)
        except Exception as exc:
            # Leave no AlertSent row: the posting stays pending and is retried
            # next run. The unique (posting_id, channel) constraint is the
            # backstop against ever recording it twice.
            report.errors.append(f"alert failed for posting {posting.id}: {exc}")
            log.exception("alert failed for posting %s (%r)", posting.id, posting.title)
            continue
        session.add(AlertSent(posting_id=posting.id, channel=channel))
        # Commit per alert so a crash mid-loop can't re-send earlier ones.
        session.commit()
        report.alerts_sent += 1
    session.commit()


def pending_alerts(
    session: Session, keywords: Sequence[Keyword], channel: str
) -> list[Posting]:
    """Matching postings that have not been alerted (or suppressed) on this channel."""
    already = (
        select(AlertSent.id)
        .where(AlertSent.posting_id == Posting.id, AlertSent.channel == channel)
        .exists()
    )
    candidates = session.scalars(
        select(Posting).where(~already).order_by(Posting.id)
    ).all()
    return [p for p in candidates if posting_matches(p, keywords)]
