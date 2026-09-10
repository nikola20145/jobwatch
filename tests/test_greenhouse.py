import httpx

from jobwatch.scrapers import greenhouse

SAMPLE = {
    "jobs": [
        {
            "id": 4285367,
            "title": "  Software Engineer - Platform  ",
            "absolute_url": "https://boards.greenhouse.io/adyen/jobs/4285367",
            "location": {"name": "Amsterdam"},
            "updated_at": "2026-09-01T10:00:00-04:00",
            "first_published": "2026-08-20T09:00:00-04:00",
            "content": "<p>Job description</p>",
        },
        {
            "id": 4285368,
            "title": "Working Student",
            "absolute_url": "https://boards.greenhouse.io/adyen/jobs/4285368",
            "location": None,
            "updated_at": "2026-09-02T10:00:00Z",
        },
        # malformed: no absolute_url -> skipped
        {"id": 4285369, "title": "Ghost Job"},
    ],
    "meta": {"total": 3},
}


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_board_normalizes_jobs():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "boards-api.greenhouse.io"
        assert request.url.path == "/v1/boards/adyen/jobs"
        assert request.url.params["content"] == "true"
        return httpx.Response(200, json=SAMPLE)

    postings = greenhouse.fetch_board("adyen", client=make_client(handler))

    assert len(postings) == 2  # malformed job dropped
    first = postings[0]
    assert first.external_id == "4285367"
    assert first.title == "Software Engineer - Platform"  # stripped
    assert first.url == "https://boards.greenhouse.io/adyen/jobs/4285367"
    assert first.location == "Amsterdam"
    assert first.posted_at is not None
    assert first.posted_at.year == 2026 and first.posted_at.month == 8  # first_published wins
    assert first.raw["content"] == "<p>Job description</p>"

    second = postings[1]
    assert second.location is None
    assert second.posted_at is not None  # fell back to updated_at, Z suffix parsed


def test_fetch_board_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "no such board"})

    try:
        greenhouse.fetch_board("nope", client=make_client(handler))
    except httpx.HTTPStatusError as exc:
        assert exc.response.status_code == 404
    else:
        raise AssertionError("expected HTTPStatusError")


def test_content_hash_stable_and_sensitive():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=SAMPLE)

    a = greenhouse.fetch_board("adyen", client=make_client(handler))
    b = greenhouse.fetch_board("adyen", client=make_client(handler))
    assert [p.content_hash for p in a] == [p.content_hash for p in b]
    assert a[0].content_hash != a[1].content_hash
