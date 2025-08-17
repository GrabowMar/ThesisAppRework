"""Add model_capabilities table

Revision ID: 8f2b1c3d4e5f
Revises: 44361c0e780d
Create Date: 2025-08-17 22:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8f2b1c3d4e5f'
down_revision = '44361c0e780d'
branch_labels = None
depends_on = None


def upgrade():
    # Create model_capabilities table to match app.models.ModelCapability
    op.create_table(
        'model_capabilities',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('model_id', sa.String(length=200), nullable=False),
        sa.Column('canonical_slug', sa.String(length=200), nullable=False),
        sa.Column('provider', sa.String(length=100), nullable=False),
        sa.Column('model_name', sa.String(length=200), nullable=False),
        # Capabilities
        sa.Column('is_free', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column('context_window', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('max_output_tokens', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('supports_function_calling', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column('supports_vision', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column('supports_streaming', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column('supports_json_mode', sa.Boolean(), nullable=True, server_default=sa.false()),
        # Pricing
        sa.Column('input_price_per_token', sa.Float(), nullable=True, server_default='0'),
        sa.Column('output_price_per_token', sa.Float(), nullable=True, server_default='0'),
        # Metrics
        sa.Column('cost_efficiency', sa.Float(), nullable=True, server_default='0'),
        sa.Column('safety_score', sa.Float(), nullable=True, server_default='0'),
        # JSON blobs
        sa.Column('capabilities_json', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('model_id', name='uq_model_capabilities_model_id'),
        sa.UniqueConstraint('canonical_slug', name='uq_model_capabilities_canonical_slug'),
    )

    with op.batch_alter_table('model_capabilities', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_model_capabilities_model_id'), ['model_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_model_capabilities_canonical_slug'), ['canonical_slug'], unique=False)
        batch_op.create_index(batch_op.f('ix_model_capabilities_provider'), ['provider'], unique=False)


def downgrade():
    with op.batch_alter_table('model_capabilities', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_model_capabilities_provider'))
        batch_op.drop_index(batch_op.f('ix_model_capabilities_canonical_slug'))
        batch_op.drop_index(batch_op.f('ix_model_capabilities_model_id'))

    op.drop_table('model_capabilities')
