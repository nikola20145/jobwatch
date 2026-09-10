import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from jobwatch.db.models import AlertSent, Base, Keyword, Posting, Source
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
        source = Source(name="Adyen", ats_type="greenhouse", board_token="adyen")
        session.add(source)
        session.add_all(
            [
                Keyword(field="title", term="intern"),
                Keyword(field="location", term="amsterdam"),
            ]
        )
        session.flush()
        scraped = [
            make_scraped("1", title="Software Engineering Intern", location="Amsterdam"),
            make_scraped("2", title="Sales Manager <script>", location="Amsterdam"),
        ]
        postings = [
            Posting(
                source_id=source.id,
                external_id=s.external_id,
                title=s.title,
                url=s.url,
                location=s.location,
                posted_at=s.posted_at,
                content_hash=s.content_hash,
                raw=s.raw,
            )
            for s in scraped
        ]
        session.add_all(postings)
        session.flush()
        session.add(AlertSent(posting_id=postings[0].id, channel="telegram"))
        session.commit()

    with TestClient(create_app(factory)) as c:
        yield c
    engine.dispose()


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"


def test_stats(client):
    body = client.get("/api/stats").json()
    assert body["sources"] == 1
    assert body["postings"] == 2
    assert body["keywords"] == 2
    assert body["alerts_sent"] == 1
    assert body["pending_alerts"] == 0  # the only match is already alerted


def test_postings_carry_match_and_alert_flags(client):
    body = client.get("/api/postings").json()
    assert len(body) == 2
    by_id = {p["external_id"]: p for p in body}
    assert by_id["1"]["matched"] is True
    assert by_id["1"]["alerted"] is True
    assert by_id["1"]["source"] == "Adyen"
    assert by_id["2"]["matched"] is False
    assert by_id["2"]["alerted"] is False


def test_postings_matched_only_filter(client):
    body = client.get("/api/postings", params={"matched_only": "true"}).json()
    assert [p["external_id"] for p in body] == ["1"]


def test_postings_title_search(client):
    body = client.get("/api/postings", params={"q": "sales"}).json()
    assert [p["external_id"] for p in body] == ["2"]


def test_dashboard_html_renders_and_escapes(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Software Engineering Intern" in response.text
    assert "<script>" not in response.text  # posting titles are escaped
    assert "&lt;script&gt;" in response.text
