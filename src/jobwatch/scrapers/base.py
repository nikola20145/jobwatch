"""Normalized posting shape shared by all scrapers."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class ScrapedPosting:
    """One job posting, normalized out of an ATS-specific payload."""

    external_id: str
    title: str
    url: str
    location: str | None
    posted_at: datetime | None
    raw: dict[str, Any]

    @property
    def content_hash(self) -> str:
        # Hash the fields a user-visible edit would change; \x1f separates them
        # so ("a", "bc") and ("ab", "c") can't collide.
        payload = "\x1f".join((self.title, self.url, self.location or ""))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_iso_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp, tolerating a trailing Z. None on failure."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
