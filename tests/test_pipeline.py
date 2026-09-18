from sqlalchemy import func, select

from jobwatch.db.models import AlertSent, Posting
from jobwatch.pipeline import run_once

from .conftest import make_scraped


class FakeAlerter:
    channel = "telegram"

    def __init__(self, fail_for: set[str] | None = None, fail_digest: bool = False):
        self.sent: list[Posting] = []
        self.digests: list[list[Posting]] = []
        self.fail_for = fail_for or set()
        self.fail_digest = fail_digest

    def send(self, posting: Posting) -> None:
        if posting.external_id in self.fail_for:
            raise RuntimeError("simulated delivery failure")
        self.sent.append(posting)

    def send_digest(self, postings) -> None:
        if self.fail_digest:
            raise RuntimeError("simulated digest failure")
        self.digests.append(list(postings))


def fetchers_returning(batch):
    return {"greenhouse": lambda source: list(batch)}


def test_full_run_alerts_once_per_matching_posting(session, source, amsterdam_keywords):
    batch = [
        make_scraped("1", title="Software Engineer", location="Amsterdam"),
        make_scraped("2", title="Sales Manager", location="Amsterdam"),  # no title match
        make_scraped("3", title="Intern, Payments", location="Berlin"),  # no location match
    ]
    alerter = FakeAlerter()

    report = run_once(session, alerter=alerter, fetchers=fetchers_returning(batch))

    assert report.ingest["Adyen"].inserted == 3
    assert report.alerts_sent == 1
    assert [p.external_id for p in alerter.sent] == ["1"]

    # Second identical run: nothing new, nothing re-alerted.
    report2 = run_once(session, alerter=alerter, fetchers=fetchers_returning(batch))
    assert report2.ingest["Adyen"].inserted == 0
    assert report2.alerts_sent == 0
    assert len(alerter.sent) == 1


def test_new_posting_in_later_run_is_alerted(session, source, amsterdam_keywords):
    alerter = FakeAlerter()
    first = [make_scraped("1", title="Software Engineer", location="Amsterdam")]
    run_once(session, alerter=alerter, fetchers=fetchers_returning(first))

    second = first + [make_scraped("9", title="Backend Intern", location="Amsterdam Office")]
    report = run_once(session, alerter=alerter, fetchers=fetchers_returning(second))

    assert report.alerts_sent == 1
    assert [p.external_id for p in alerter.sent] == ["1", "9"]


def test_seed_suppresses_backlog_but_alerts_future_postings(session, source, amsterdam_keywords):
    alerter = FakeAlerter()
    backlog = [make_scraped("1", title="Software Engineer", location="Amsterdam")]
    report = run_once(
        session, alerter=alerter, fetchers=fetchers_returning(backlog), suppress_alerts=True
    )

    assert report.alerts_sent == 0
    assert report.alerts_suppressed == 1
    assert alerter.sent == []

    later = backlog + [make_scraped("2", title="ML Intern", location="Amsterdam")]
    report2 = run_once(session, alerter=alerter, fetchers=fetchers_returning(later))
    assert report2.alerts_sent == 1
    assert [p.external_id for p in alerter.sent] == ["2"]


def test_failed_delivery_is_retried_next_run(session, source, amsterdam_keywords):
    batch = [make_scraped("1", title="Software Engineer", location="Amsterdam")]

    flaky = FakeAlerter(fail_for={"1"})
    report = run_once(session, alerter=flaky, fetchers=fetchers_returning(batch))
    assert report.alerts_sent == 0
    assert len(report.errors) == 1
    assert session.scalar(select(func.count()).select_from(AlertSent)) == 0

    ok = FakeAlerter()
    report2 = run_once(session, alerter=ok, fetchers=fetchers_returning(batch))
    assert report2.alerts_sent == 1
    assert [p.external_id for p in ok.sent] == ["1"]


def test_fetch_failure_is_isolated(session, source, amsterdam_keywords):
    def boom(_source):
        raise RuntimeError("board unreachable")

    report = run_once(session, alerter=FakeAlerter(), fetchers={"greenhouse": boom})
    assert report.ingest == {}
    assert len(report.errors) == 1


def test_no_alerter_skips_alert_phase(session, source, amsterdam_keywords):
    batch = [make_scraped("1", title="Software Engineer", location="Amsterdam")]
    report = run_once(session, alerter=None, fetchers=fetchers_returning(batch))
    assert report.alerts_sent == 0
    assert session.scalar(select(func.count()).select_from(AlertSent)) == 0
