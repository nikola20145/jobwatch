"""Generic Greenhouse job-board fetcher.

Works for any company hosted on Greenhouse — the board token is the only
per-company input (e.g. "adyen" for https://boards-api.greenhouse.io/v1/boards/adyen/jobs).
"""

import logging
from typing import Any

import httpx

from jobwatch.scrapers.base import ScrapedPosting, parse_iso_datetime

log = logging.getLogger(__name__)

API_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
USER_AGENT = "jobwatch/0.1 (+https://github.com/nikola20145/jobwatch)"


def fetch_board(
    board_token: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 30.0,
) -> list[ScrapedPosting]:
    """Fetch all postings on one Greenhouse board, normalized.

    Raises httpx.HTTPError on network/HTTP failure; the caller decides how a
    failing source affects the rest of the run.
    """
    owns_client = client is None
    if client is None:
        client = httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT})
    try:
        response = client.get(
            API_URL.format(board_token=board_token), params={"content": "true"}
        )
        response.raise_for_status()
        data = response.json()
    finally:
        if owns_client:
            client.close()

    postings: list[ScrapedPosting] = []
    for job in data.get("jobs", []):
        posting = _normalize(job)
        if posting is None:
            log.warning(
                "skipping malformed greenhouse job on board %r: %r", board_token, job.get("id")
            )
            continue
        postings.append(posting)
    return postings


def _normalize(job: dict[str, Any]) -> ScrapedPosting | None:
    external_id = job.get("id")
    title = (job.get("title") or "").strip()
    url = job.get("absolute_url")
    if external_id is None or not title or not url:
        return None
    location = ((job.get("location") or {}).get("name") or "").strip() or None
    posted_at = parse_iso_datetime(job.get("first_published") or job.get("updated_at"))
    return ScrapedPosting(
        external_id=str(external_id),
        title=title,
        url=url,
        location=location,
        posted_at=posted_at,
        raw=job,
    )
