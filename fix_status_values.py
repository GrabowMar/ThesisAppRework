"""
Migration script to normalize status values in analysis_tasks table.

The AnalysisStatus enum expects lowercase values, but some records have uppercase values.
This script converts all uppercase status values to lowercase.
"""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.extensions import db
from sqlalchemy import text

def fix_status_values():
    """Convert uppercase status values to lowercase in analysis_tasks table."""
    app = create_app()
    with app.app_context():
        # Show current status counts
        print("Current status distribution:")
        result = db.session.execute(text(
            'SELECT status, COUNT(*) FROM analysis_tasks GROUP BY status ORDER BY status'
        ))
        for row in result:
            print(f'  {row[0]}: {row[1]}')
        
        # Map uppercase to lowercase
        status_map = {
            'PENDING': 'pending',
            'RUNNING': 'running',
            'COMPLETED': 'completed',
            'FAILED': 'failed',
            'CANCELLED': 'cancelled'
        }
        
        total_updated = 0
        for old_status, new_status in status_map.items():
            result = db.session.execute(
                text('UPDATE analysis_tasks SET status = :new_status WHERE status = :old_status'),
                {'new_status': new_status, 'old_status': old_status}
            )
            count = result.rowcount
            if count > 0:
                print(f'\nUpdated {count} records from "{old_status}" to "{new_status}"')
                total_updated += count
        
        db.session.commit()
        print(f'\n✅ Total records updated: {total_updated}')
        
        # Show final status counts
        print("\nFinal status distribution:")
        result = db.session.execute(text(
            'SELECT status, COUNT(*) FROM analysis_tasks GROUP BY status ORDER BY status'
        ))
        for row in result:
            print(f'  {row[0]}: {row[1]}')

if __name__ == '__main__':
    print("Normalizing status values in analysis_tasks table...\n")
    fix_status_values()
    print("\n✅ Migration complete!")
