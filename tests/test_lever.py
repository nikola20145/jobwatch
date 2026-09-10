import httpx
import pytest

from jobwatch.scrapers import lever

SAMPLE = [
    {
        "id": "a1b2c3d4-0000-1111-2222-333344445555",
        "text": "  Software Engineering Intern  ",
        "hostedUrl": "https://jobs.lever.co/mendix/a1b2c3d4",
        "categories": {"location": "Rotterdam, Netherlands", "team": "Engineering"},
        "createdAt": 1756684800000,  # 2025-09-01T00:00:00Z
    },
    {
        "id": "b2c3d4e5-0000-1111-2222-333344445555",
        "text": "Backend Engineer",
        "hostedUrl": "https://jobs.lever.co/mendix/b2c3d4e5",
        "categories": {},
        "createdAt": "not-a-number",
    },
    # malformed: no hostedUrl -> skipped
    {"id": "c3d4e5f6", "text": "Ghost Job"},
]


def make_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_board_normalizes_jobs():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.lever.co"
        assert request.url.path == "/v0/postings/mendix"
        assert request.url.params["mode"] == "json"
        return httpx.Response(200, json=SAMPLE)

    postings = lever.fetch_board("mendix", client=make_client(handler))

    assert len(postings) == 2  # malformed job dropped
    first = postings[0]
    assert first.external_id == "a1b2c3d4-0000-1111-2222-333344445555"
    assert first.title == "Software Engineering Intern"  # stripped
    assert first.location == "Rotterdam, Netherlands"
    assert first.posted_at is not None and first.posted_at.year == 2025

    second = postings[1]
    assert second.location is None
    assert second.posted_at is None  # bad createdAt degrades to None, not a crash


def test_fetch_board_raises_on_unknown_board():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Document not found")

    with pytest.raises(httpx.HTTPStatusError):
        lever.fetch_board("nope", client=make_client(handler))


def test_fetch_board_rejects_non_list_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": "weird"})

    with pytest.raises(ValueError):
        lever.fetch_board("weird", client=make_client(handler))
