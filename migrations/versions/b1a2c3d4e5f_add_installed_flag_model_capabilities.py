"""Add installed boolean to model_capabilities

Revision ID: b1a2c3d4e5f
Revises: 19355bb85378
Create Date: 2025-08-18 09:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b1a2c3d4e5f'
down_revision = '19355bb85378'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('model_capabilities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('installed', sa.Boolean(), nullable=True, server_default=sa.false()))
        batch_op.create_index(batch_op.f('ix_model_capabilities_installed'), ['installed'], unique=False)
    # Remove server default so future inserts use model default
    op.alter_column('model_capabilities', 'installed', server_default=None)


def downgrade():
    with op.batch_alter_table('model_capabilities', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_model_capabilities_installed'))
        batch_op.drop_column('installed')
