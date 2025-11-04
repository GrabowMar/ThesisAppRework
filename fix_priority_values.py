"""
Migration script to normalize priority values in analysis_tasks table.

The Priority enum expects lowercase values, but some records have uppercase values.
This script converts all uppercase priority values to lowercase.
"""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.extensions import db
from sqlalchemy import text

def fix_priority_values():
    """Convert uppercase priority values to lowercase in analysis_tasks table."""
    app = create_app()
    with app.app_context():
        # Show current priority counts
        print("Current priority distribution:")
        result = db.session.execute(text(
            'SELECT priority, COUNT(*) FROM analysis_tasks GROUP BY priority ORDER BY priority'
        ))
        for row in result:
            print(f'  {row[0]}: {row[1]}')
        
        # Map uppercase to lowercase
        priority_map = {
            'LOW': 'low',
            'NORMAL': 'normal',
            'HIGH': 'high',
            'URGENT': 'urgent'
        }
        
        total_updated = 0
        for old_priority, new_priority in priority_map.items():
            result = db.session.execute(
                text('UPDATE analysis_tasks SET priority = :new_priority WHERE priority = :old_priority'),
                {'new_priority': new_priority, 'old_priority': old_priority}
            )
            count = result.rowcount
            if count > 0:
                print(f'\nUpdated {count} records from "{old_priority}" to "{new_priority}"')
                total_updated += count
        
        db.session.commit()
        print(f'\n✅ Total records updated: {total_updated}')
        
        # Show final priority counts
        print("\nFinal priority distribution:")
        result = db.session.execute(text(
            'SELECT priority, COUNT(*) FROM analysis_tasks GROUP BY priority ORDER BY priority'
        ))
        for row in result:
            print(f'  {row[0]}: {row[1]}')

if __name__ == '__main__':
    print("Normalizing priority values in analysis_tasks table...\n")
    fix_priority_values()
    print("\n✅ Migration complete!")
