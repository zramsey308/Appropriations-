"""Change funding columns to BigInteger

Revision ID: 002
Revises: 001
Create Date: 2026-02-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002a'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Use batch_alter_table for SQLite compatibility (SQLite doesn't support ALTER COLUMN)
    with op.batch_alter_table('requests') as batch_op:
        batch_op.alter_column('requested_amount',
                              existing_type=sa.Integer(),
                              type_=sa.BigInteger(),
                              existing_nullable=True)

    with op.batch_alter_table('cpf_details') as batch_op:
        batch_op.alter_column('requested_amount',
                              existing_type=sa.Integer(),
                              type_=sa.BigInteger(),
                              existing_nullable=True)
        batch_op.alter_column('total_project_cost',
                              existing_type=sa.Integer(),
                              type_=sa.BigInteger(),
                              existing_nullable=True)
        batch_op.alter_column('cost_share_amount',
                              existing_type=sa.Integer(),
                              type_=sa.BigInteger(),
                              existing_nullable=True)


def downgrade():
    with op.batch_alter_table('requests') as batch_op:
        batch_op.alter_column('requested_amount',
                              existing_type=sa.BigInteger(),
                              type_=sa.Integer(),
                              existing_nullable=True)

    with op.batch_alter_table('cpf_details') as batch_op:
        batch_op.alter_column('requested_amount',
                              existing_type=sa.BigInteger(),
                              type_=sa.Integer(),
                              existing_nullable=True)
        batch_op.alter_column('total_project_cost',
                              existing_type=sa.BigInteger(),
                              type_=sa.Integer(),
                              existing_nullable=True)
        batch_op.alter_column('cost_share_amount',
                              existing_type=sa.BigInteger(),
                              type_=sa.Integer(),
                              existing_nullable=True)
