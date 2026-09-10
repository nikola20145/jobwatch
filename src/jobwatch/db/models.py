"""Database schema: sources, postings, keywords, alerts_sent."""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# JSONB on Postgres, plain JSON elsewhere (tests run on SQLite).
JsonType = JSON().with_variant(JSONB(), "postgresql")

KEYWORD_FIELDS = ("title", "location")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Source(Base):
    """A career board to poll, e.g. Adyen on Greenhouse."""

    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("ats_type", "board_token", name="uq_sources_ats_board"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    ats_type: Mapped[str] = mapped_column(String(50))  # "greenhouse", later "lever", ...
    board_token: Mapped[str] = mapped_column(String(200))
    base_url: Mapped[str | None] = mapped_column(Text())
    enabled: Mapped[bool] = mapped_column(Boolean(), default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    postings: Mapped[list["Posting"]] = relationship(back_populates="source")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Source {self.name} ({self.ats_type}:{self.board_token})>"


class Posting(Base):
    """One job posting as seen on a source board.

    Identity for dedup is (source_id, external_id) — the ATS's own job id.
    content_hash detects edits to a posting we already hold.
    """

    __tablename__ = "postings"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_postings_source_external"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(Text())
    url: Mapped[str] = mapped_column(Text())
    location: Mapped[str | None] = mapped_column(Text())
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    raw: Mapped[dict] = mapped_column(JsonType)

    source: Mapped[Source] = relationship(back_populates="postings")
    alerts: Mapped[list["AlertSent"]] = relationship(back_populates="posting")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Posting {self.external_id} {self.title!r}>"


class Keyword(Base):
    """A match term. field says which posting attribute it applies to."""

    __tablename__ = "keywords"
    __table_args__ = (
        UniqueConstraint("field", "term", name="uq_keywords_field_term"),
        CheckConstraint("field IN ('title', 'location')", name="ck_keywords_field"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    field: Mapped[str] = mapped_column(String(20))
    term: Mapped[str] = mapped_column(String(200))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Keyword {self.field}:{self.term!r}>"


class AlertSent(Base):
    """Record of an alert delivered (or deliberately suppressed) for a posting.

    The (posting_id, channel) unique constraint is what makes alerting
    idempotent: a posting can be notified at most once per channel.
    """

    __tablename__ = "alerts_sent"
    __table_args__ = (
        UniqueConstraint("posting_id", "channel", name="uq_alerts_posting_channel"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    posting_id: Mapped[int] = mapped_column(ForeignKey("postings.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(50))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    suppressed: Mapped[bool] = mapped_column(Boolean(), default=False)

    posting: Mapped[Posting] = relationship(back_populates="alerts")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AlertSent posting={self.posting_id} via {self.channel}>"
