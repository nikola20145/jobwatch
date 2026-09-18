import httpx

from jobwatch.scrapers import recruitee

SAMPLE = {
    "offers": [
        {
            "id": 2751915,
            "title": "  Backend Engineer  ",
            "careers_url": "https://jobs.channable.com/o/backend-engineer",
            "location": "Utrecht, Utrecht, Netherlands",
            "city": "Utrecht",
            "country": "Netherlands",
            "published_at": "2026-09-18 13:27:28 UTC",
            "created_at": "2026-09-18 12:55:59 UTC",
            "status": "published",
        },
        {
            # no location string -> falls back to city + country; no published_at
            "id": 2751916,
            "title": "Working Student",
            "careers_url": "https://jobs.channable.com/o/working-student",
            "location": "",
            "city": "Amsterdam",
            "country": "Netherlands",
            "created_at": "2026-09-01 08:00:00 UTC",
        },
        # malformed: no careers_url -> skipped
        {"id": 2751917, "title": "Ghost Offer"},
    ]
}


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_board_normalizes_offers():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "channable.recruitee.com"
        assert request.url.path == "/api/offers/"
        return httpx.Response(200, json=SAMPLE)

    postings = recruitee.fetch_board("channable", client=make_client(handler))

    assert len(postings) == 2  # malformed offer dropped
    first = postings[0]
    assert first.external_id == "2751915"
    assert first.title == "Backend Engineer"  # stripped
    assert first.location == "Utrecht, Utrecht, Netherlands"
    assert first.posted_at is not None
    assert first.posted_at.hour == 13  # published_at wins over created_at
    assert first.posted_at.tzinfo is not None

    second = postings[1]
    assert second.location == "Amsterdam, Netherlands"  # city + country fallback
    assert second.posted_at is not None and second.posted_at.day == 1


def test_fetch_board_raises_on_unknown_company():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "Not Found"})

    try:
        recruitee.fetch_board("nope", client=make_client(handler))
    except httpx.HTTPStatusError as exc:
        assert exc.response.status_code == 404
    else:
        raise AssertionError("expected HTTPStatusError")


def test_unparseable_timestamp_degrades_to_none():
    sample = {
        "offers": [
            {
                "id": 1,
                "title": "Engineer",
                "careers_url": "https://jobs.example.com/o/engineer",
                "published_at": "yesterday-ish",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=sample)

    postings = recruitee.fetch_board("x", client=make_client(handler))
    assert len(postings) == 1
    assert postings[0].posted_at is None
