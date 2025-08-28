"""
Alembic migration (merge): make DateTime columns timezone-aware (UTC)

- Merges divergent heads and alters columns to use timezone-aware DateTime
- Uses batch_alter_table for SQLite compatibility and skips missing tables/columns

Revision ID: tz_aware_datetimes
Revises: 8f2b1c3d4e5f, b1a2c3d4e5f
Create Date: 2025-08-21
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'tz_aware_datetimes'
# Merge both heads: after 8f2b1c3d4e5f (model_capabilities table) and b1a2c3d4e5f (installed flag)
down_revision = ('8f2b1c3d4e5f', 'b1a2c3d4e5f')
branch_labels = None
depends_on = None


def upgrade():
    # Use batch_alter_table for SQLite compatibility
    tables_and_cols = {
        # Core analysis tables
        'security_analyses': ['started_at', 'completed_at', 'created_at', 'updated_at'],
        'performance_tests': ['started_at', 'completed_at', 'created_at', 'updated_at'],
        'zap_analyses': ['started_at', 'completed_at', 'created_at', 'updated_at'],
        'openrouter_analyses': ['started_at', 'completed_at', 'created_at', 'updated_at'],
        'batch_analyses': ['started_at', 'completed_at', 'estimated_completion', 'created_at', 'updated_at'],
        # Supporting entities
        'model_capabilities': ['created_at', 'updated_at'],
        'port_configurations': ['created_at', 'updated_at'],
        'generated_applications': ['created_at', 'updated_at'],
        'containerized_tests': ['created_at', 'updated_at', 'last_health_check', 'last_used'],
        # Caches
        'openrouter_model_cache': ['created_at', 'updated_at', 'cache_expires_at', 'last_accessed'],
        'external_model_info_cache': ['created_at', 'updated_at', 'cache_expires_at', 'last_refreshed'],
        # Configurations
        'analysis_configs': ['created_at', 'updated_at', 'last_used'],
        'config_presets': ['created_at', 'updated_at'],
    }

    for table, cols in tables_and_cols.items():
        try:
            with op.batch_alter_table(table) as batch_op:
                for col in cols:
                    try:
                        # For PostgreSQL, ensure existing naive timestamps are interpreted as UTC
                        batch_op.alter_column(
                            col,
                            type_=sa.DateTime(timezone=True),
                            postgresql_using=f"{col} AT TIME ZONE 'UTC'"
                        )
                    except Exception:
                        # Column might not exist in some environments; skip
                        pass
        except Exception:
            # Table might not exist depending on feature set; skip
            pass


def downgrade():
    # Revert to naive DateTime (not recommended, but needed for downgrade path)
    tables_and_cols = {
        'security_analyses': ['started_at', 'completed_at', 'created_at', 'updated_at'],
        'performance_tests': ['started_at', 'completed_at', 'created_at', 'updated_at'],
        'zap_analyses': ['started_at', 'completed_at', 'created_at', 'updated_at'],
        'openrouter_analyses': ['started_at', 'completed_at', 'created_at', 'updated_at'],
        'batch_analyses': ['started_at', 'completed_at', 'estimated_completion', 'created_at', 'updated_at'],
        'model_capabilities': ['created_at', 'updated_at'],
        'port_configurations': ['created_at', 'updated_at'],
        'generated_applications': ['created_at', 'updated_at'],
        'containerized_tests': ['created_at', 'updated_at', 'last_health_check', 'last_used'],
        'openrouter_model_cache': ['created_at', 'updated_at', 'cache_expires_at', 'last_accessed'],
        'external_model_info_cache': ['created_at', 'updated_at', 'cache_expires_at', 'last_refreshed'],
        'analysis_configs': ['created_at', 'updated_at', 'last_used'],
        'config_presets': ['created_at', 'updated_at'],
    }

    for table, cols in tables_and_cols.items():
        try:
            with op.batch_alter_table(table) as batch_op:
                for col in cols:
                    try:
                        batch_op.alter_column(col, type_=sa.DateTime(timezone=False))
                    except Exception:
                        pass
        except Exception:
            pass
