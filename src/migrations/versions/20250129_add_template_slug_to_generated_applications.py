"""Add template_slug to GeneratedApplication

Revision ID: 20250129_template_slug
Revises: e58483348f55
Create Date: 2025-01-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250129_template_slug'
down_revision = 'e58483348f55'
branch_labels = None
depends_on = None


def upgrade():
    """Add template_slug column to track which requirement template was used."""
    with op.batch_alter_table('generated_applications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('template_slug', sa.String(length=100), nullable=True))
        batch_op.create_index('ix_generated_applications_template_slug', ['template_slug'], unique=False)


def downgrade():
    """Remove template_slug column."""
    with op.batch_alter_table('generated_applications', schema=None) as batch_op:
        batch_op.drop_index('ix_generated_applications_template_slug')
        batch_op.drop_column('template_slug')
