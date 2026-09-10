"""initial schema: sources, postings, keywords, alerts_sent

Revision ID: 0001
Revises:
Create Date: 2026-09-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("ats_type", sa.String(length=50), nullable=False),
        sa.Column("board_token", sa.String(length=200), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_sources_name"),
        sa.UniqueConstraint("ats_type", "board_token", name="uq_sources_ats_board"),
    )

    op.create_table(
        "postings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "source_id",
            sa.Integer(),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=200), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("raw", json_type, nullable=False),
        sa.UniqueConstraint("source_id", "external_id", name="uq_postings_source_external"),
    )
    op.create_index("ix_postings_source_id", "postings", ["source_id"])
    op.create_index("ix_postings_content_hash", "postings", ["content_hash"])

    op.create_table(
        "keywords",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("field", sa.String(length=20), nullable=False),
        sa.Column("term", sa.String(length=200), nullable=False),
        sa.UniqueConstraint("field", "term", name="uq_keywords_field_term"),
        sa.CheckConstraint("field IN ('title', 'location')", name="ck_keywords_field"),
    )

    op.create_table(
        "alerts_sent",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "posting_id",
            sa.Integer(),
            sa.ForeignKey("postings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("suppressed", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("posting_id", "channel", name="uq_alerts_posting_channel"),
    )
    op.create_index("ix_alerts_sent_posting_id", "alerts_sent", ["posting_id"])


def downgrade() -> None:
    op.drop_table("alerts_sent")
    op.drop_table("keywords")
    op.drop_table("postings")
    op.drop_table("sources")
