"""Generic Recruitee job-board fetcher.

Third ATS, third wire format: Recruitee wraps postings in an "offers" object
and writes timestamps as "2026-09-18 13:27:28 UTC"
(e.g. https://channable.recruitee.com/api/offers/). The board token is the
company's subdomain on recruitee.com — common among Dutch scale-ups.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from jobwatch.scrapers.base import ScrapedPosting

log = logging.getLogger(__name__)

API_URL = "https://{board_token}.recruitee.com/api/offers/"
USER_AGENT = "jobwatch/0.1 (+https://github.com/nikola20145/jobwatch)"


def fetch_board(
    board_token: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 30.0,
) -> list[ScrapedPosting]:
    """Fetch all published offers on one Recruitee board, normalized.

    Raises httpx.HTTPError on network/HTTP failure; Recruitee 404s on
    unknown company subdomains.
    """
    owns_client = client is None
    if client is None:
        client = httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT})
    try:
        response = client.get(API_URL.format(board_token=board_token))
        response.raise_for_status()
        data = response.json()
    finally:
        if owns_client:
            client.close()

    postings: list[ScrapedPosting] = []
    for offer in data.get("offers", []):
        posting = _normalize(offer)
        if posting is None:
            log.warning(
                "skipping malformed recruitee offer on board %r: %r", board_token, offer.get("id")
            )
            continue
        postings.append(posting)
    return postings


def _normalize(offer: dict[str, Any]) -> ScrapedPosting | None:
    external_id = offer.get("id")
    title = (offer.get("title") or "").strip()
    url = offer.get("careers_url")
    if external_id is None or not title or not url:
        return None
    location = (offer.get("location") or "").strip() or None
    if location is None:
        parts = [p.strip() for p in (offer.get("city"), offer.get("country")) if p and p.strip()]
        location = ", ".join(parts) or None
    posted_at = _parse_recruitee_datetime(offer.get("published_at") or offer.get("created_at"))
    return ScrapedPosting(
        external_id=str(external_id),
        title=title,
        url=url,
        location=location,
        posted_at=posted_at,
        raw=offer,
    )


def _parse_recruitee_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=UTC)
    except ValueError:
        return None
