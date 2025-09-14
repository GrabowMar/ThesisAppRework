"""
Migration module for routes not yet moved to their proper modules.
This is a temporary bridge to keep the application working during refactoring.
Routes in this file should be moved to their appropriate modules over time.
"""

from flask import Blueprint
from app.routes.api.common import api_error

# Create a temporary migration blueprint
migration_bp = Blueprint('api_migration', __name__)

@migration_bp.route('/migration-status')
def migration_status():
    """Endpoint to check migration status."""
    return api_error("Some routes are still being migrated to new modules", 501)