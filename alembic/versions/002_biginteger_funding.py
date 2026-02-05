"""Change funding columns to BigInteger

Revision ID: 002
Revises: 001
Create Date: 2026-02-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Change requested_amount in requests table to BigInteger
    op.alter_column('requests', 'requested_amount',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=True)

    # Change funding columns in cpf_details table to BigInteger
    op.alter_column('cpf_details', 'requested_amount',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=True)

    op.alter_column('cpf_details', 'total_project_cost',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=True)

    op.alter_column('cpf_details', 'cost_share_amount',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=True)


def downgrade():
    # Revert to Integer (may cause data loss if values exceed Integer range)
    op.alter_column('requests', 'requested_amount',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=True)

    op.alter_column('cpf_details', 'requested_amount',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=True)

    op.alter_column('cpf_details', 'total_project_cost',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=True)

    op.alter_column('cpf_details', 'cost_share_amount',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=True)
