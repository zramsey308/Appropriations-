"""Add bureau, account, program_funding columns to requests

Revision ID: 005
Revises: 004
Create Date: 2026-03-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('requests', sa.Column('bureau', sa.String(length=500), nullable=True))
    op.add_column('requests', sa.Column('account', sa.String(length=500), nullable=True))
    op.add_column('requests', sa.Column('program_funding', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('requests', 'program_funding')
    op.drop_column('requests', 'account')
    op.drop_column('requests', 'bureau')
