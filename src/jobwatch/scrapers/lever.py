"""Generic Lever job-board fetcher.

Same idea as the Greenhouse scraper, different API shape: Lever returns a
bare JSON array and timestamps as epoch milliseconds
(e.g. https://api.lever.co/v0/postings/mendix?mode=json).
"""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from jobwatch.scrapers.base import ScrapedPosting

log = logging.getLogger(__name__)

API_URL = "https://api.lever.co/v0/postings/{board_token}"
USER_AGENT = "jobwatch/0.1 (+https://github.com/nikola20145/jobwatch)"


def fetch_board(
    board_token: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 30.0,
) -> list[ScrapedPosting]:
    """Fetch all postings on one Lever board, normalized.

    Raises httpx.HTTPError on network/HTTP failure. Note: Lever 404s on
    unknown board tokens, unlike Greenhouse which returns an error body.
    """
    owns_client = client is None
    if client is None:
        client = httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT})
    try:
        response = client.get(API_URL.format(board_token=board_token), params={"mode": "json"})
        response.raise_for_status()
        data = response.json()
    finally:
        if owns_client:
            client.close()

    if not isinstance(data, list):
        raise ValueError(f"unexpected lever response shape for board {board_token!r}")

    postings: list[ScrapedPosting] = []
    for job in data:
        posting = _normalize(job)
        if posting is None:
            log.warning("skipping malformed lever job on board %r: %r", board_token, job.get("id"))
            continue
        postings.append(posting)
    return postings


def _normalize(job: dict[str, Any]) -> ScrapedPosting | None:
    external_id = job.get("id")
    title = (job.get("text") or "").strip()
    url = job.get("hostedUrl")
    if not external_id or not title or not url:
        return None
    location = ((job.get("categories") or {}).get("location") or "").strip() or None
    return ScrapedPosting(
        external_id=str(external_id),
        title=title,
        url=url,
        location=location,
        posted_at=_from_epoch_ms(job.get("createdAt")),
        raw=job,
    )


def _from_epoch_ms(value: Any) -> datetime | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None
