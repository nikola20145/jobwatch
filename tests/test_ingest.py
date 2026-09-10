from sqlalchemy import func, select

from jobwatch.db.models import Posting
from jobwatch.ingest import ingest_postings

from .conftest import make_scraped


def count_postings(session) -> int:
    return session.scalar(select(func.count()).select_from(Posting))


def test_inserts_new_postings(session, source):
    batch = [make_scraped("1"), make_scraped("2", title="Backend Engineer")]
    stats = ingest_postings(session, source, batch)
    session.commit()

    assert stats.inserted == 2
    assert stats.updated == stats.unchanged == 0
    assert count_postings(session) == 2
    assert len(stats.new_posting_ids) == 2


def test_same_batch_twice_inserts_nothing(session, source):
    batch = [make_scraped("1"), make_scraped("2", title="Backend Engineer")]
    ingest_postings(session, source, batch)
    session.commit()

    stats = ingest_postings(session, source, batch)
    session.commit()

    assert stats.inserted == 0
    assert stats.unchanged == 2
    assert stats.new_posting_ids == []
    assert count_postings(session) == 2


def test_changed_content_updates_in_place(session, source):
    ingest_postings(session, source, [make_scraped("1", title="Old Title")])
    session.commit()

    stats = ingest_postings(session, source, [make_scraped("1", title="New Title")])
    session.commit()

    assert stats.inserted == 0
    assert stats.updated == 1
    assert count_postings(session) == 1
    posting = session.scalar(select(Posting))
    assert posting.title == "New Title"
    assert posting.content_hash == make_scraped("1", title="New Title").content_hash


def test_duplicate_external_id_within_batch_kept_once(session, source):
    batch = [make_scraped("1", title="First"), make_scraped("1", title="Second")]
    stats = ingest_postings(session, source, batch)
    session.commit()

    assert stats.inserted == 1
    assert count_postings(session) == 1
    assert session.scalar(select(Posting)).title == "First"


def test_same_external_id_on_other_source_is_distinct(session, source):
    from jobwatch.db.models import Source

    other = Source(name="Mollie", ats_type="greenhouse", board_token="mollie")
    session.add(other)
    session.commit()

    ingest_postings(session, source, [make_scraped("1")])
    stats = ingest_postings(session, other, [make_scraped("1")])
    session.commit()

    assert stats.inserted == 1
    assert count_postings(session) == 2
