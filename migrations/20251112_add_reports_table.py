"""
Database migration: Add reports table

This migration adds the reports table for storing generated analysis reports.

Run with: python migrations/20251112_add_reports_table.py
"""
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.extensions import db
from app.factory import create_app
from app.models import Report


def migrate():
    """Create reports table."""
    app = create_app()
    
    with app.app_context():
        print("Creating reports table...")
        
        # Create table
        db.create_all()
        
        print("✓ Reports table created successfully")
        print("\nTable structure:")
        print("  - id (primary key)")
        print("  - report_id (unique)")
        print("  - report_type")
        print("  - title")
        print("  - description")
        print("  - config (JSON)")
        print("  - format")
        print("  - file_path")
        print("  - file_size")
        print("  - status")
        print("  - error_message")
        print("  - progress_percent")
        print("  - created_by (FK to users)")
        print("  - created_at")
        print("  - completed_at")
        print("  - expires_at")
        print("  - summary (JSON)")
        print("  - analysis_task_id (FK to analysis_tasks)")
        print("  - generated_app_id (FK to generated_applications)")
        print("\nIndexes:")
        print("  - idx_report_type_status (report_type, status)")
        print("  - idx_report_created_at (created_at)")


if __name__ == '__main__':
    migrate()
