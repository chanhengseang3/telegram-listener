"""add amount_paid and note to group_package

Revision ID: 48a5b6c7d8e9
Revises: 47576589fdcb
Create Date: 2025-01-27 10:00:00.000000+07:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '48a5b6c7d8e9'
down_revision: Union[str, Sequence[str], None] = '47576589fdcb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('group_package', sa.Column('amount_paid', sa.Float(), nullable=True))
    op.add_column('group_package', sa.Column('note', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('group_package', 'note')
    op.drop_column('group_package', 'amount_paid')