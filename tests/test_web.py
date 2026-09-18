import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from jobwatch.db.models import AlertSent, Base, Keyword, Posting, Source, utcnow
from jobwatch.web import create_app

from .conftest import make_scraped


@pytest.fixture()
def client():
    # StaticPool: one shared connection, so the TestClient's worker thread
    # sees the same in-memory database the fixture seeded.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    with factory() as session:
        adyen = Source(name="Adyen", ats_type="greenhouse", board_token="adyen")
        mendix = Source(name="Mendix", ats_type="lever", board_token="mendix")
        session.add_all([adyen, mendix])
        session.add_all(
            [
                Keyword(field="title", term="intern"),
                Keyword(field="location", term="amsterdam"),
            ]
        )
        session.flush()
        scraped = [
            ("1", adyen, make_scraped("1", title="Software Engineering Intern", location="Amsterdam"), None),
            ("2", adyen, make_scraped("2", title="Sales Manager <script>", location="Amsterdam"), None),
            ("3", mendix, make_scraped("3", title="Platform Intern", location="Amsterdam"), utcnow()),
        ]
        postings = [
            Posting(
                source_id=src.id,
                external_id=s.external_id,
                title=s.title,
                url=s.url,
                location=s.location,
                posted_at=s.posted_at,
                content_hash=s.content_hash,
                closed_at=closed_at,
                raw=s.raw,
            )
            for _, src, s, closed_at in scraped
        ]
        session.add_all(postings)
        session.flush()
        session.add(AlertSent(posting_id=postings[0].id, channel="telegram"))
        session.commit()

    # Pin a nonexistent dist so these tests exercise the server-rendered
    # fallback even on machines where web/dist has been built.
    with TestClient(create_app(factory, web_dist="does-not-exist")) as c:
        yield c
    engine.dispose()


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"


def test_stats(client):
    body = client.get("/api/stats").json()
    assert body["sources"] == 2
    assert body["postings"] == 3
    assert body["open_postings"] == 2
    assert body["keywords"] == 2
    assert body["alerts_sent"] == 1
    # The open match is alerted; the other match is closed, so nothing pends.
    assert body["pending_alerts"] == 0


def test_postings_carry_match_and_alert_flags(client):
    body = client.get("/api/postings").json()
    assert len(body) == 3
    by_id = {p["external_id"]: p for p in body}
    assert by_id["1"]["matched"] is True
    assert by_id["1"]["alerted"] is True
    assert by_id["1"]["source"] == "Adyen"
    assert by_id["1"]["closed_at"] is None
    assert by_id["2"]["matched"] is False
    assert by_id["2"]["alerted"] is False
    assert by_id["3"]["closed_at"] is not None


def test_postings_matched_only_filter(client):
    body = client.get("/api/postings", params={"matched_only": "true"}).json()
    assert {p["external_id"] for p in body} == {"1", "3"}


def test_postings_source_filter(client):
    body = client.get("/api/postings", params={"source": "Adyen"}).json()
    assert {p["external_id"] for p in body} == {"1", "2"}


def test_postings_status_filter(client):
    closed = client.get("/api/postings", params={"status": "closed"}).json()
    assert [p["external_id"] for p in closed] == ["3"]
    opened = client.get("/api/postings", params={"status": "open"}).json()
    assert {p["external_id"] for p in opened} == {"1", "2"}


def test_sources_endpoint(client):
    body = client.get("/api/sources").json()
    assert [s["name"] for s in body] == ["Adyen", "Mendix"]
    assert body[0]["ats_type"] == "greenhouse"


def test_postings_offset_paginates(client):
    first = client.get("/api/postings", params={"limit": 2}).json()
    rest = client.get("/api/postings", params={"limit": 2, "offset": 2}).json()
    assert len(first) == 2
    assert len(rest) == 1
    ids = {p["external_id"] for p in first} | {p["external_id"] for p in rest}
    assert ids == {"1", "2", "3"}


def test_timeline_buckets_by_week(client):
    body = client.get("/api/stats/timeline").json()
    assert len(body) == 12
    # All three fixture postings are posted a week ago, inside the window.
    assert sum(p["count"] for p in body) == 3
    assert sum(p["matched"] for p in body) == 2
    week_with_data = next(p for p in body if p["count"])
    assert week_with_data["count"] == 3 and week_with_data["matched"] == 2


def test_source_stats_aggregates(client):
    body = client.get("/api/stats/sources").json()
    by_name = {s["name"]: s for s in body}
    assert by_name["Adyen"]["total"] == 2
    assert by_name["Adyen"]["open"] == 2
    assert by_name["Adyen"]["matched"] == 1
    assert by_name["Mendix"]["total"] == 1
    assert by_name["Mendix"]["open"] == 0  # its posting is closed
    assert by_name["Mendix"]["matched"] == 1


def test_postings_title_search(client):
    body = client.get("/api/postings", params={"q": "sales"}).json()
    assert [p["external_id"] for p in body] == ["2"]


def test_dashboard_html_renders_and_escapes(client):
    # No web/dist in the test environment -> server-rendered fallback page.
    response = client.get("/")
    assert response.status_code == 200
    assert "Software Engineering Intern" in response.text
    assert "<script>" not in response.text  # posting titles are escaped
    assert "&lt;script&gt;" in response.text


def test_spa_served_when_build_exists(tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    (tmp_path / "index.html").write_text("<html><body>SPA BUILD</body></html>")

    with TestClient(create_app(factory, web_dist=tmp_path)) as c:
        response = c.get("/")
        assert response.status_code == 200
        assert "SPA BUILD" in response.text
        # The API keeps working alongside the static frontend.
        assert c.get("/api/health").json()["status"] == "ok"
    engine.dispose()
