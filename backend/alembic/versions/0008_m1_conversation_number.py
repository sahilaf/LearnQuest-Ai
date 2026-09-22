"""M1: per-user conversation numbers, so tutor URLs are readable.

The tutor route showed the conversation's primary key
(/tutor/2ab0ff8f-0a18-47be-a60d-25e6b0031d74). This adds a small integer that
counts from 1 per user, giving /tutor/7. The UUID remains the real key and the
only thing foreign keys reference; `number` is purely the public handle.

Existing rows are backfilled in creation order per user, so nobody's links
change meaning.

Revision ID: 0008_m1_conversation_number
Revises: 0007_m1_teachback_sessions
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_m1_conversation_number"
down_revision: Union[str, None] = "0007_m1_teachback_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable first so the backfill has somewhere to write.
    op.add_column("conversations", sa.Column("number", sa.Integer(), nullable=True))

    # Window function: supported by Postgres and by SQLite 3.25+.
    op.execute(
        """
        UPDATE conversations SET number = ranked.rn
        FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY user_id ORDER BY created_at, id
            ) AS rn
            FROM conversations
        ) AS ranked
        WHERE conversations.id = ranked.id
        """
        if op.get_bind().dialect.name == "postgresql"
        else """
        UPDATE conversations SET number = (
            SELECT COUNT(*) FROM conversations AS c2
            WHERE c2.user_id = conversations.user_id
              AND (c2.created_at < conversations.created_at
                   OR (c2.created_at = conversations.created_at AND c2.id <= conversations.id))
        )
        """
    )

    op.alter_column("conversations", "number", nullable=False)
    op.create_unique_constraint(
        "uq_conversations_user_number", "conversations", ["user_id", "number"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_conversations_user_number", "conversations", type_="unique")
    op.drop_column("conversations", "number")
