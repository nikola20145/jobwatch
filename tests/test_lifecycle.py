from sqlalchemy import select

from jobwatch.db.models import Posting
from jobwatch.ingest import ingest_postings
from jobwatch.pipeline import run_once

from .conftest import make_scraped
from .test_pipeline import FakeAlerter, fetchers_returning


def get(session, external_id: str) -> Posting:
    return session.scalars(
        select(Posting).where(Posting.external_id == external_id)
    ).one()


def test_disappeared_posting_is_closed(session, source):
    ingest_postings(session, source, [make_scraped("1"), make_scraped("2")])
    session.commit()

    stats = ingest_postings(session, source, [make_scraped("1")])
    session.commit()

    assert stats.closed == 1
    assert get(session, "2").closed_at is not None
    assert get(session, "1").closed_at is None


def test_returning_posting_is_reopened(session, source):
    ingest_postings(session, source, [make_scraped("1"), make_scraped("2")])
    ingest_postings(session, source, [make_scraped("1")])  # "2" closes
    stats = ingest_postings(session, source, [make_scraped("1"), make_scraped("2")])
    session.commit()

    assert stats.reopened == 1
    assert stats.closed == 0
    assert get(session, "2").closed_at is None


def test_still_present_posting_refreshes_last_seen(session, source):
    ingest_postings(session, source, [make_scraped("1")])
    session.commit()
    first_seen = get(session, "1").last_seen_at

    ingest_postings(session, source, [make_scraped("1")])
    session.commit()

    assert get(session, "1").last_seen_at >= first_seen


def test_empty_batch_never_mass_closes(session, source):
    ingest_postings(session, source, [make_scraped("1"), make_scraped("2")])
    session.commit()

    stats = ingest_postings(session, source, [])
    session.commit()

    assert stats.closed == 0
    assert get(session, "1").closed_at is None
    assert get(session, "2").closed_at is None


def test_closed_posting_is_not_alerted(session, source, amsterdam_keywords):
    match = make_scraped("1", title="Software Engineer", location="Amsterdam")
    other = make_scraped("2", title="Sales", location="Amsterdam")

    # Ingest without alerting, then the matching posting disappears before
    # any alert went out.
    ingest_postings(session, source, [match, other])
    session.commit()
    ingest_postings(session, source, [other])
    session.commit()

    alerter = FakeAlerter()
    report = run_once(session, alerter=alerter, fetchers=fetchers_returning([other]))
    assert report.alerts_sent == 0
    assert alerter.sent == []
