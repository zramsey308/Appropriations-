"""Add priority_order field to requests

Revision ID: 004
Revises: 003
Create Date: 2026-03-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('requests', sa.Column('priority_order', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_requests_priority_order'), 'requests', ['priority_order'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_requests_priority_order'), table_name='requests')
    op.drop_column('requests', 'priority_order')
