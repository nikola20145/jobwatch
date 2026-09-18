"""keywords: opt-in whole-word matching

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-18

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "keywords",
        sa.Column("whole_word", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table("keywords") as batch:
        batch.drop_column("whole_word")
