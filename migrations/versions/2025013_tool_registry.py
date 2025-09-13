"""Add dynamic tool registry tables

Revision ID: 2025013_tool_registry
Revises: 
Create Date: 2025-01-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2025013_tool_registry'
down_revision = None  # Will be updated based on current HEAD
branch_labels = None
depends_on = None


def upgrade():
    """Add tables for dynamic tool registry system."""
    
    # Create analysis_tools table
    op.create_table('analysis_tools',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=20), nullable=False),
        sa.Column('compatibility', sa.JSON(), nullable=False),
        sa.Column('service_name', sa.String(length=50), nullable=False),
        sa.Column('command', sa.String(length=200), nullable=True),
        sa.Column('version', sa.String(length=20), nullable=True),
        sa.Column('homepage_url', sa.String(length=500), nullable=True),
        sa.Column('documentation_url', sa.String(length=500), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('requires_config', sa.Boolean(), nullable=False, default=False),
        sa.Column('default_config', sa.JSON(), nullable=True),
        sa.Column('config_schema', sa.JSON(), nullable=True),
        sa.Column('estimated_duration', sa.Integer(), nullable=True),
        sa.Column('resource_intensive', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for analysis_tools
    op.create_index('ix_analysis_tools_name', 'analysis_tools', ['name'], unique=True)
    op.create_index('ix_analysis_tools_category', 'analysis_tools', ['category'])
    
    # Create tool_configurations table
    op.create_table('tool_configurations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tool_id', sa.Integer(), nullable=False),
        sa.Column('configuration', sa.JSON(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_shared', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tool_id'], ['analysis_tools.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for tool_configurations
    op.create_index('ix_tool_configurations_name', 'tool_configurations', ['name'])
    
    # Create analysis_profiles table
    op.create_table('analysis_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_builtin', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('estimated_duration', sa.Integer(), nullable=True),
        sa.Column('recommended_for', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index for analysis_profiles
    op.create_index('ix_analysis_profiles_name', 'analysis_profiles', ['name'], unique=True)
    
    # Create association table for profiles and tool configurations
    op.create_table('profile_tool_configs',
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('tool_config_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['profile_id'], ['analysis_profiles.id'], ),
        sa.ForeignKeyConstraint(['tool_config_id'], ['tool_configurations.id'], ),
        sa.PrimaryKeyConstraint('profile_id', 'tool_config_id')
    )
    
    # Create custom_analysis_requests table
    op.create_table('custom_analysis_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_name', sa.String(length=200), nullable=False),
        sa.Column('model_slug', sa.String(length=100), nullable=False),
        sa.Column('app_number', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=True),
        sa.Column('custom_tools', sa.JSON(), nullable=True),
        sa.Column('priority', sa.String(length=20), nullable=True, default='normal'),
        sa.Column('timeout_seconds', sa.Integer(), nullable=True, default=1800),
        sa.Column('notification_settings', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, default='pending'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('results_json', sa.JSON(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('failed_tools', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['profile_id'], ['analysis_profiles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for custom_analysis_requests
    op.create_index('ix_custom_analysis_requests_model_slug', 'custom_analysis_requests', ['model_slug'])
    op.create_index('ix_custom_analysis_requests_app_number', 'custom_analysis_requests', ['app_number'])
    op.create_index('ix_custom_analysis_requests_status', 'custom_analysis_requests', ['status'])


def downgrade():
    """Remove dynamic tool registry tables."""
    
    # Drop tables in reverse order due to foreign key constraints
    op.drop_table('custom_analysis_requests')
    op.drop_table('profile_tool_configs')
    op.drop_table('analysis_profiles')
    op.drop_table('tool_configurations')
    op.drop_table('analysis_tools')