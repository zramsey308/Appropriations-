"""Add NDAA details table

Revision ID: 002
Revises: 001
Create Date: 2026-02-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '002b'
down_revision: Union[str, None] = '002a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ndaa_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=False),

        # Section I - General Information
        sa.Column('company_organization', sa.String(length=500), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(length=255), nullable=True),
        sa.Column('state', sa.String(length=50), nullable=True),
        sa.Column('zip_code', sa.String(length=20), nullable=True),
        sa.Column('poc_name', sa.String(length=255), nullable=True),
        sa.Column('poc_is_lobbyist', sa.Boolean(), nullable=False, default=False),
        sa.Column('lobbyist_organization', sa.String(length=500), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('met_with_congressman', sa.String(length=500), nullable=True),
        sa.Column('meeting_date', sa.String(length=50), nullable=True),
        sa.Column('multiple_requests', sa.Boolean(), nullable=False, default=False),
        sa.Column('request_priority', sa.String(length=50), nullable=True),

        # Section II - Budgetary Legislative Proposal
        sa.Column('official_project_name', sa.String(length=500), nullable=True),
        sa.Column('funding_agency', sa.String(length=500), nullable=True),
        sa.Column('budget_account', sa.String(length=500), nullable=True),
        sa.Column('sub_account_1', sa.String(length=500), nullable=True),
        sa.Column('sub_account_2', sa.String(length=500), nullable=True),
        sa.Column('line_title', sa.String(length=500), nullable=True),
        sa.Column('line_number', sa.String(length=100), nullable=True),
        sa.Column('hasc_subcommittee', sa.String(length=255), nullable=True),
        sa.Column('funded_in_pb', sa.Boolean(), nullable=False, default=False),
        sa.Column('program_element', sa.String(length=255), nullable=True),
        sa.Column('additional_funding_amount', sa.Integer(), nullable=True),
        sa.Column('is_scalable', sa.Boolean(), nullable=False, default=False),
        sa.Column('scalable_amount', sa.Integer(), nullable=True),
        sa.Column('fy26_bill_amount', sa.Integer(), nullable=True),
        sa.Column('unfunded_priority_list', sa.Boolean(), nullable=False, default=False),
        sa.Column('unfunded_ranking', sa.String(length=50), nullable=True),
        sa.Column('unfunded_amount', sa.Integer(), nullable=True),

        # Section III - Policy Legislative Proposal
        sa.Column('proposed_bill_language', sa.Text(), nullable=True),
        sa.Column('proposed_report_language', sa.Text(), nullable=True),
        sa.Column('items_of_special_interest', sa.Text(), nullable=True),

        # Section IV - Proposal Explanation
        sa.Column('justification', sa.Text(), nullable=True),
        sa.Column('program_description', sa.Text(), nullable=True),
        sa.Column('military_value', sa.Text(), nullable=True),
        sa.Column('tx11_impact', sa.Text(), nullable=True),
        sa.Column('partners', sa.Text(), nullable=True),
        sa.Column('other_offices_engaged', sa.Text(), nullable=True),
        sa.Column('committee_staff_engaged', sa.Text(), nullable=True),
        sa.Column('additional_notes', sa.Text(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),

        sa.ForeignKeyConstraint(['request_id'], ['requests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('request_id')
    )
    op.create_index(op.f('ix_ndaa_details_id'), 'ndaa_details', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ndaa_details_id'), table_name='ndaa_details')
    op.drop_table('ndaa_details')
