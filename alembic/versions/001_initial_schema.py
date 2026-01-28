"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    request_type_enum = sa.Enum('cpf', 'programmatic', 'language', name='requesttype')
    request_type_enum.create(op.get_bind(), checkfirst=True)

    subcommittee_enum = sa.Enum(
        'agriculture', 'commerce_justice_science', 'defense', 'energy_water',
        'financial_services_general_government', 'homeland_security', 'interior_environment',
        'labor_hhs_education', 'legislative_branch', 'milcon_va', 'state_foreign_operations',
        'transportation_hud',
        name='subcommittee'
    )
    subcommittee_enum.create(op.get_bind(), checkfirst=True)

    request_status_enum = sa.Enum('draft', 'submitted', 'under_review', 'approved', 'rejected', 'selected', name='requeststatus')
    request_status_enum.create(op.get_bind(), checkfirst=True)

    entity_type_enum = sa.Enum(
        'state_government', 'local_government', 'tribal_government',
        'nonprofit', 'public_higher_education', 'special_district',
        name='entitytype'
    )
    entity_type_enum.create(op.get_bind(), checkfirst=True)

    attachment_type_enum = sa.Enum(
        'cpf_support_letter', 'budget_document', 'project_description',
        'authorization_citation', 'other',
        name='attachmenttype'
    )
    attachment_type_enum.create(op.get_bind(), checkfirst=True)

    # Create eligible_accounts table
    op.create_table(
        'eligible_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('subcommittee', sa.Enum(
            'agriculture', 'commerce_justice_science', 'defense', 'energy_water',
            'financial_services_general_government', 'homeland_security', 'interior_environment',
            'labor_hhs_education', 'legislative_branch', 'milcon_va', 'state_foreign_operations',
            'transportation_hud',
            name='subcommittee', create_type=False
        ), nullable=False),
        sa.Column('subcategory', sa.String(length=255), nullable=True),
        sa.Column('agency', sa.String(length=255), nullable=False),
        sa.Column('account_name', sa.String(length=500), nullable=False),
        sa.Column('is_new', sa.Boolean(), nullable=False, default=False),
        sa.Column('notes', sa.String(length=1000), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, default=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_eligible_accounts_id'), 'eligible_accounts', ['id'], unique=False)
    op.create_index(op.f('ix_eligible_accounts_subcommittee'), 'eligible_accounts', ['subcommittee'], unique=False)

    # Create requests table
    op.create_table(
        'requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('fiscal_year', sa.Integer(), nullable=False, default=2027),
        sa.Column('request_type', sa.Enum('cpf', 'programmatic', 'language', name='requesttype', create_type=False), nullable=False),
        sa.Column('subcommittee', sa.Enum(
            'agriculture', 'commerce_justice_science', 'defense', 'energy_water',
            'financial_services_general_government', 'homeland_security', 'interior_environment',
            'labor_hhs_education', 'legislative_branch', 'milcon_va', 'state_foreign_operations',
            'transportation_hud',
            name='subcommittee', create_type=False
        ), nullable=False),
        sa.Column('status', sa.Enum('draft', 'submitted', 'under_review', 'approved', 'rejected', 'selected', name='requeststatus', create_type=False), nullable=False, default='draft'),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('requester_name', sa.String(length=255), nullable=True),
        sa.Column('requester_email', sa.String(length=255), nullable=True),
        sa.Column('requester_phone', sa.String(length=50), nullable=True),
        sa.Column('requester_organization', sa.String(length=255), nullable=True),
        sa.Column('program_name', sa.String(length=500), nullable=True),
        sa.Column('requested_amount', sa.Integer(), nullable=True),
        sa.Column('programmatic_justification', sa.Text(), nullable=True),
        sa.Column('bill_section', sa.String(length=255), nullable=True),
        sa.Column('proposed_language', sa.Text(), nullable=True),
        sa.Column('language_justification', sa.Text(), nullable=True),
        sa.Column('assigned_to', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_requests_id'), 'requests', ['id'], unique=False)
    op.create_index(op.f('ix_requests_fiscal_year'), 'requests', ['fiscal_year'], unique=False)
    op.create_index(op.f('ix_requests_request_type'), 'requests', ['request_type'], unique=False)
    op.create_index(op.f('ix_requests_subcommittee'), 'requests', ['subcommittee'], unique=False)
    op.create_index(op.f('ix_requests_status'), 'requests', ['status'], unique=False)

    # Create cpf_details table
    op.create_table(
        'cpf_details',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=False),
        sa.Column('cpf_account_id', sa.Integer(), nullable=True),
        sa.Column('tx11_nexus', sa.Boolean(), nullable=False, default=False),
        sa.Column('tx11_nexus_explanation', sa.Text(), nullable=True),
        sa.Column('entity_type', sa.Enum(
            'state_government', 'local_government', 'tribal_government',
            'nonprofit', 'public_higher_education', 'special_district',
            name='entitytype', create_type=False
        ), nullable=True),
        sa.Column('entity_name', sa.String(length=500), nullable=True),
        sa.Column('entity_address', sa.Text(), nullable=True),
        sa.Column('project_name', sa.String(length=500), nullable=True),
        sa.Column('project_address', sa.Text(), nullable=True),
        sa.Column('project_description', sa.Text(), nullable=True),
        sa.Column('requested_amount', sa.Integer(), nullable=True),
        sa.Column('total_project_cost', sa.Integer(), nullable=True),
        sa.Column('cost_share_amount', sa.Integer(), nullable=True),
        sa.Column('cost_share_required', sa.Boolean(), nullable=False, default=False),
        sa.Column('cost_share_explanation', sa.Text(), nullable=True),
        sa.Column('public_benefit_justification', sa.Text(), nullable=True),
        sa.Column('tx11_priority_justification', sa.Text(), nullable=True),
        sa.Column('stakeholders_support', sa.Text(), nullable=True),
        sa.Column('support_letters_received', sa.Integer(), nullable=False, default=0),
        sa.Column('eligibility_citations', sa.Text(), nullable=True),
        sa.Column('timeline', sa.Text(), nullable=True),
        sa.Column('future_federal_funding', sa.Boolean(), nullable=False, default=False),
        sa.Column('future_federal_funding_explanation', sa.Text(), nullable=True),
        sa.Column('partial_funding_acceptable', sa.Boolean(), nullable=False, default=False),
        sa.Column('partial_funding_explanation', sa.Text(), nullable=True),
        sa.Column('authorized_in_law', sa.Boolean(), nullable=False, default=False),
        sa.Column('authorization_citation', sa.Text(), nullable=True),
        sa.Column('in_presidential_budget', sa.Boolean(), nullable=False, default=False),
        sa.Column('presidential_budget_details', sa.Text(), nullable=True),
        sa.Column('prior_federal_funding', sa.Boolean(), nullable=False, default=False),
        sa.Column('prior_funding_details', sa.Text(), nullable=True),
        sa.Column('derogatory_info', sa.Boolean(), nullable=False, default=False),
        sa.Column('derogatory_info_explanation', sa.Text(), nullable=True),
        sa.Column('members_receiving_request', sa.Text(), nullable=True),
        sa.Column('selected', sa.Boolean(), nullable=False, default=False),
        sa.Column('selected_slot', sa.Integer(), nullable=True),
        sa.Column('selected_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['request_id'], ['requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cpf_account_id'], ['eligible_accounts.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('request_id'),
        sa.UniqueConstraint('selected_slot')
    )
    op.create_index(op.f('ix_cpf_details_id'), 'cpf_details', ['id'], unique=False)

    # Create attachments table
    op.create_table(
        'attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('original_filename', sa.String(length=500), nullable=False),
        sa.Column('file_path', sa.String(length=1000), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('content_type', sa.String(length=255), nullable=True),
        sa.Column('attachment_type', sa.Enum(
            'cpf_support_letter', 'budget_document', 'project_description',
            'authorization_citation', 'other',
            name='attachmenttype', create_type=False
        ), nullable=False, default='other'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['request_id'], ['requests.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_attachments_id'), 'attachments', ['id'], unique=False)
    op.create_index(op.f('ix_attachments_request_id'), 'attachments', ['request_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_attachments_request_id'), table_name='attachments')
    op.drop_index(op.f('ix_attachments_id'), table_name='attachments')
    op.drop_table('attachments')

    op.drop_index(op.f('ix_cpf_details_id'), table_name='cpf_details')
    op.drop_table('cpf_details')

    op.drop_index(op.f('ix_requests_status'), table_name='requests')
    op.drop_index(op.f('ix_requests_subcommittee'), table_name='requests')
    op.drop_index(op.f('ix_requests_request_type'), table_name='requests')
    op.drop_index(op.f('ix_requests_fiscal_year'), table_name='requests')
    op.drop_index(op.f('ix_requests_id'), table_name='requests')
    op.drop_table('requests')

    op.drop_index(op.f('ix_eligible_accounts_subcommittee'), table_name='eligible_accounts')
    op.drop_index(op.f('ix_eligible_accounts_id'), table_name='eligible_accounts')
    op.drop_table('eligible_accounts')

    # Drop enum types
    sa.Enum(name='attachmenttype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='entitytype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='requeststatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='subcommittee').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='requesttype').drop(op.get_bind(), checkfirst=True)
