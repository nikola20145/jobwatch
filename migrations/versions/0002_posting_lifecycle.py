"""posting lifecycle: last_seen_at and closed_at

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-18

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("postings", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("postings", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    # Existing rows were on their boards when last scraped.
    op.execute("UPDATE postings SET last_seen_at = scraped_at")
    with op.batch_alter_table("postings") as batch:
        batch.alter_column("last_seen_at", existing_type=sa.DateTime(timezone=True), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("postings") as batch:
        batch.drop_column("closed_at")
        batch.drop_column("last_seen_at")
