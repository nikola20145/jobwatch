from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from jobwatch.db.models import Base, Keyword, Source
from jobwatch.scrapers.base import ScrapedPosting


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as s:
        yield s
    engine.dispose()


@pytest.fixture()
def source(session: Session) -> Source:
    src = Source(name="Adyen", ats_type="greenhouse", board_token="adyen")
    session.add(src)
    session.commit()
    return src


@pytest.fixture()
def amsterdam_keywords(session: Session) -> list[Keyword]:
    keywords = [
        Keyword(field="title", term="intern"),
        Keyword(field="title", term="software engineer"),
        Keyword(field="location", term="amsterdam"),
    ]
    session.add_all(keywords)
    session.commit()
    return keywords


def make_scraped(
    external_id: str = "100",
    title: str = "Software Engineer Intern",
    url: str = "https://example.com/jobs/100",
    location: str | None = "Amsterdam",
    posted_at: datetime | None = datetime(2026, 9, 1, tzinfo=timezone.utc),
) -> ScrapedPosting:
    return ScrapedPosting(
        external_id=external_id,
        title=title,
        url=url,
        location=location,
        posted_at=posted_at,
        raw={"id": external_id, "title": title},
    )
