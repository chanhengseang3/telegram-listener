"""add_note_column_to_income_balance

Revision ID: i1j2k3l4m5n6
Revises: h3i4j5k6l7m8
Create Date: 2025-07-27 16:00:00.000000+07:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'i1j2k3l4m5n6'
down_revision: Union[str, Sequence[str], None] = 'h3i4j5k6l7m8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('income_balance', sa.Column('note', sa.Text, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('income_balance', 'note')