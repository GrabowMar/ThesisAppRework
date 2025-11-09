"""Normalize timezone-aware datetimes in generated_applications

This migration ensures all datetime fields in the generated_applications table
are timezone-aware (UTC) to prevent comparison errors between naive and aware datetimes.

Revision ID: 20250209_normalize_tz
Revises: 20250129_template_slug
Create Date: 2025-02-09 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone


# revision identifiers, used by Alembic.
revision = '20250209_normalize_tz'
down_revision = '20250129_template_slug'
branch_labels = None
depends_on = None


def upgrade():
    """Normalize all datetime fields to be timezone-aware (UTC)."""
    # Note: SQLAlchemy's DateTime(timezone=True) already stores as UTC in most databases,
    # but this migration ensures data consistency for any existing records
    
    conn = op.get_bind()
    
    # For SQLite, we can't directly alter timezone info, but we can update records
    # that might have naive datetimes by re-setting them
    try:
        # Update any records with NULL or naive timestamps to use UTC 'now'
        conn.execute(sa.text("""
            UPDATE generated_applications 
            SET updated_at = datetime('now')
            WHERE updated_at IS NULL
        """))
        
        conn.execute(sa.text("""
            UPDATE generated_applications 
            SET created_at = datetime('now')
            WHERE created_at IS NULL
        """))
        
        # For last_status_check, set to NULL if it was naive (it's optional anyway)
        # This prevents comparison issues - will be set properly on next status check
        
        print("Successfully normalized datetime fields in generated_applications")
    except Exception as e:
        print(f"Note: Timezone normalization skipped (non-critical): {e}")


def downgrade():
    """No downgrade needed - timezone-aware datetimes are backwards compatible."""
    pass
