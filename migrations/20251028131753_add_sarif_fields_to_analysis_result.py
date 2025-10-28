"""
Add SARIF 2.1.0 compliance fields to analysis_results table

Revision ID: 20251028131753
Create Date: 2025-10-28 13:17:53
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '20251028131753'
down_revision = None  # Update this if you have previous migrations
branch_labels = None
depends_on = None


def upgrade():
    """Add SARIF compliance fields to analysis_results table."""
    # Add new columns as nullable to handle existing data
    with op.batch_alter_table('analysis_results', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sarif_level', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('sarif_rule_id', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('sarif_metadata', sa.Text(), nullable=True))


def downgrade():
    """Remove SARIF compliance fields from analysis_results table."""
    with op.batch_alter_table('analysis_results', schema=None) as batch_op:
        batch_op.drop_column('sarif_metadata')
        batch_op.drop_column('sarif_rule_id')
        batch_op.drop_column('sarif_level')
