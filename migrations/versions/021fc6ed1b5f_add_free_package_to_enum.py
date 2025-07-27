"""add_free_package_to_enum

Revision ID: 021fc6ed1b5f
Revises: created_updated_to_chat_group
Create Date: 2025-07-22 13:17:27.870062+07:00

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '021fc6ed1b5f'
down_revision: Union[str, Sequence[str], None] = 'created_updated_to_chat_group'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add 'FREE' to the ServicePackage enum in MySQL
    op.execute("ALTER TABLE group_package MODIFY COLUMN package ENUM('TRIAL', 'BASIC', 'UNLIMITED', 'BUSINESS', 'FREE') NOT NULL DEFAULT 'TRIAL'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
