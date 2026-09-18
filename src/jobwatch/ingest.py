"""Idempotent ingestion: fetched postings -> database rows, without duplicates."""

import logging
from dataclasses import dataclass, field
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from jobwatch.db.models import Posting, Source, utcnow
from jobwatch.scrapers.base import ScrapedPosting

log = logging.getLogger(__name__)


@dataclass
class IngestStats:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    closed: int = 0
    reopened: int = 0
    new_posting_ids: list[int] = field(default_factory=list)


def ingest_postings(
    session: Session, source: Source, scraped: Sequence[ScrapedPosting]
) -> IngestStats:
    """Insert new postings, refresh edited ones, skip everything already known.

    Identity is (source_id, external_id). Re-running on the same batch is a
    no-op — that is what keeps alerting downstream idempotent. The caller
    commits.
    """
    existing = {
        p.external_id: p
        for p in session.scalars(select(Posting).where(Posting.source_id == source.id))
    }
    stats = IngestStats()
    seen_in_batch: set[str] = set()
    new_postings: list[Posting] = []

    for item in scraped:
        if item.external_id in seen_in_batch:
            log.warning(
                "duplicate external_id %r within one batch from source %r; keeping first",
                item.external_id,
                source.name,
            )
            continue
        seen_in_batch.add(item.external_id)

        current = existing.get(item.external_id)
        if current is not None:
            current.last_seen_at = utcnow()
            if current.closed_at is not None:
                current.closed_at = None
                stats.reopened += 1
        if current is None:
            posting = Posting(
                source_id=source.id,
                external_id=item.external_id,
                title=item.title,
                url=item.url,
                location=item.location,
                posted_at=item.posted_at,
                content_hash=item.content_hash,
                raw=item.raw,
            )
            session.add(posting)
            new_postings.append(posting)
            stats.inserted += 1
        elif current.content_hash != item.content_hash:
            current.title = item.title
            current.url = item.url
            current.location = item.location
            current.posted_at = item.posted_at
            current.content_hash = item.content_hash
            current.raw = item.raw
            current.scraped_at = utcnow()
            stats.updated += 1
        else:
            stats.unchanged += 1

    # A posting that stopped appearing on its board has been taken down.
    # An entirely empty batch is more likely an ATS glitch than a company
    # deleting every job at once, so never mass-close on one.
    if seen_in_batch:
        for posting in existing.values():
            if posting.external_id not in seen_in_batch and posting.closed_at is None:
                posting.closed_at = utcnow()
                stats.closed += 1
    elif existing:
        log.warning(
            "source %r returned an empty batch while %d postings are known; "
            "not closing anything (possible API glitch)",
            source.name,
            len(existing),
        )

    session.flush()
    stats.new_posting_ids = [p.id for p in new_postings]
    return stats
