"""Add defense programmatic fields to requests

Revision ID: 006
Revises: 005
Create Date: 2026-03-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('requests', sa.Column('component', sa.String(length=500), nullable=True))
    op.add_column('requests', sa.Column('budget_activity', sa.String(length=500), nullable=True))
    op.add_column('requests', sa.Column('program_element', sa.String(length=255), nullable=True))
    op.add_column('requests', sa.Column('line_number', sa.String(length=255), nullable=True))
    op.add_column('requests', sa.Column('project_program_name', sa.String(length=500), nullable=True))
    op.add_column('requests', sa.Column('funding_amount_enacted_previous_year', sa.BigInteger(), nullable=True))
    op.add_column('requests', sa.Column('funding_amount_presidents_budget', sa.BigInteger(), nullable=True))
    op.add_column('requests', sa.Column('location', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('requests', 'location')
    op.drop_column('requests', 'funding_amount_presidents_budget')
    op.drop_column('requests', 'funding_amount_enacted_previous_year')
    op.drop_column('requests', 'project_program_name')
    op.drop_column('requests', 'line_number')
    op.drop_column('requests', 'program_element')
    op.drop_column('requests', 'budget_activity')
    op.drop_column('requests', 'component')
