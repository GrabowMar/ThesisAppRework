"""Add advanced batch orchestration models

Revision ID: add_advanced_batch_models
Revises: 44361c0e780d
Create Date: 2025-08-26

NOTE: Using human-readable revision id for clarity in this prototype; in production
use `alembic revision` to auto-generate a hash id.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_advanced_batch_models'
down_revision = '44361c0e780d'
branch_labels = None
depends_on = None

def upgrade():
    # batch_queues
    op.create_table(
        'batch_queues',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_id', sa.String(length=100), sa.ForeignKey('batch_analyses.batch_id'), nullable=False, index=True),
        sa.Column('priority', sa.String(length=20), nullable=False, index=True),
        sa.Column('status', sa.String(length=30), nullable=False, index=True),
        sa.Column('position', sa.Integer(), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )

    # batch_dependencies
    op.create_table(
        'batch_dependencies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_id', sa.String(length=100), sa.ForeignKey('batch_analyses.batch_id'), nullable=False, index=True),
        sa.Column('depends_on_batch_id', sa.String(length=100), nullable=False, index=True),
        sa.Column('satisfied', sa.Boolean(), nullable=False, server_default=sa.text('0')), 
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('batch_id', 'depends_on_batch_id', name='uq_batch_dependency')
    )

    # batch_schedules
    op.create_table(
        'batch_schedules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_config_json', sa.Text(), nullable=False),
        sa.Column('cron_expression', sa.String(length=120), nullable=False, index=True),
        sa.Column('last_run', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_run', sa.DateTime(timezone=True), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # batch_resource_usage
    op.create_table(
        'batch_resource_usage',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('batch_id', sa.String(length=100), sa.ForeignKey('batch_analyses.batch_id'), nullable=False, index=True),
        sa.Column('analyzer_type', sa.String(length=50), nullable=False, index=True),
        sa.Column('peak_memory', sa.Float(), nullable=True),
        sa.Column('peak_cpu', sa.Float(), nullable=True),
        sa.Column('duration', sa.Float(), nullable=True),
        sa.Column('sample_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # batch_templates
    op.create_table(
        'batch_templates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False, unique=True, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('batch_config_json', sa.Text(), nullable=False),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table('batch_templates')
    op.drop_table('batch_resource_usage')
    op.drop_table('batch_schedules')
    op.drop_table('batch_dependencies')
    op.drop_table('batch_queues')
