import pytest
from sqlalchemy import func, select

from jobwatch.db.models import AlertSent
from jobwatch.ingest import ingest_postings
from jobwatch.pipeline import DIGEST_LIMIT, send_digest

from .conftest import make_scraped
from .test_pipeline import FakeAlerter


def ingest(session, source, batch):
    ingest_postings(session, source, batch)
    session.commit()


def alert_rows(session) -> int:
    return session.scalar(select(func.count()).select_from(AlertSent))


def test_digest_sends_one_message_and_records_all(session, source, amsterdam_keywords):
    ingest(
        session,
        source,
        [
            make_scraped("1", title="Software Engineer", location="Amsterdam"),
            make_scraped("2", title="Backend Intern", location="Amsterdam"),
            make_scraped("3", title="Sales", location="Amsterdam"),  # no match
        ],
    )
    alerter = FakeAlerter()

    covered = send_digest(session, alerter)

    assert covered == 2
    assert len(alerter.digests) == 1
    assert {p.external_id for p in alerter.digests[0]} == {"1", "2"}
    assert alert_rows(session) == 2


def test_second_digest_covers_nothing(session, source, amsterdam_keywords):
    ingest(session, source, [make_scraped("1", title="Software Engineer", location="Amsterdam")])
    alerter = FakeAlerter()

    assert send_digest(session, alerter) == 1
    assert send_digest(session, alerter) == 0
    assert len(alerter.digests) == 1  # nothing pending -> no empty message


def test_failed_digest_records_nothing(session, source, amsterdam_keywords):
    ingest(session, source, [make_scraped("1", title="Software Engineer", location="Amsterdam")])
    flaky = FakeAlerter(fail_digest=True)

    with pytest.raises(RuntimeError):
        send_digest(session, flaky)
    assert alert_rows(session) == 0

    # Retry with a healthy alerter picks the posting up again.
    assert send_digest(session, FakeAlerter()) == 1


def test_digest_caps_and_rolls_over(session, source, amsterdam_keywords):
    batch = [
        make_scraped(str(i), title=f"Software Engineer {i}", location="Amsterdam")
        for i in range(DIGEST_LIMIT + 5)
    ]
    ingest(session, source, batch)
    alerter = FakeAlerter()

    assert send_digest(session, alerter) == DIGEST_LIMIT
    assert len(alerter.digests[0]) == DIGEST_LIMIT
    # The overflow stays pending and lands in the next digest.
    assert send_digest(session, alerter) == 5


def test_no_keywords_sends_nothing(session, source):
    ingest(session, source, [make_scraped("1")])
    alerter = FakeAlerter()
    assert send_digest(session, alerter) == 0
    assert alerter.digests == []
