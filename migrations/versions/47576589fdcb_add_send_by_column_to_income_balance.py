"""add_send_by_column_to_income_balance

Revision ID: 47576589fdcb
Revises: 021fc6ed1b5f
Create Date: 2025-07-23 15:13:35.298307+07:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '47576589fdcb'
down_revision: Union[str, Sequence[str], None] = '021fc6ed1b5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('income_balance', sa.Column('sent_by', sa.String(50), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('income_balance', 'sent_by')
