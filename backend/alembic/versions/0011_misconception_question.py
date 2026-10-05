"""Remember which question revealed each misconception.

topic_mastery.misconception_question_id
  Teach-Back re-asks the question whose wrong answer produced the belief. The
  belief is stored per topic, so a quiz with several wrong answers on one topic
  used to pair the belief from one question with a different question. Found
  by the end-to-end suite (e2e/tests/learning-loop.spec.js).

Revision ID: 0011_misconception_question
Revises: 0010_review_and_practice
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_misconception_question"
down_revision: Union[str, None] = "0010_review_and_practice"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "topic_mastery",
        sa.Column("misconception_question_id", sa.Uuid(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("topic_mastery", "misconception_question_id")
