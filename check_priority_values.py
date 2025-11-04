import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # Check priority values
    result = db.session.execute(text('SELECT DISTINCT priority FROM analysis_tasks ORDER BY priority'))
    print('Distinct priority values in database:')
    for row in result:
        print(f'  "{row[0]}"')
    
    # Count by priority
    result2 = db.session.execute(text('SELECT priority, COUNT(*) FROM analysis_tasks GROUP BY priority ORDER BY priority'))
    print('\nPriority counts:')
    for row in result2:
        print(f'  {row[0]}: {row[1]}')
