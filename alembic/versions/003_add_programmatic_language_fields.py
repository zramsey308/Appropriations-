"""Add programmatic/language request fields

Revision ID: 003
Revises: 002
Create Date: 2026-02-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '003'
down_revision: Union[str, None] = '002b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('requests', sa.Column('agency', sa.String(length=500), nullable=True))
    op.add_column('requests', sa.Column('language_location', sa.String(length=500), nullable=True))
    op.add_column('requests', sa.Column('priority_rank', sa.String(length=50), nullable=True))
    op.add_column('requests', sa.Column('problem_statement', sa.Text(), nullable=True))
    op.add_column('requests', sa.Column('goals_outcomes', sa.Text(), nullable=True))
    op.add_column('requests', sa.Column('other_members', sa.Text(), nullable=True))
    op.add_column('requests', sa.Column('prior_year_submission', sa.Boolean(), nullable=True))
    op.add_column('requests', sa.Column('prior_year_details', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('requests', 'prior_year_details')
    op.drop_column('requests', 'prior_year_submission')
    op.drop_column('requests', 'other_members')
    op.drop_column('requests', 'goals_outcomes')
    op.drop_column('requests', 'problem_statement')
    op.drop_column('requests', 'priority_rank')
    op.drop_column('requests', 'language_location')
    op.drop_column('requests', 'agency')
