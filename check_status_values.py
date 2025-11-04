import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    result = db.session.execute(text('SELECT DISTINCT status FROM analysis_tasks ORDER BY status'))
    print('Distinct status values in database:')
    for row in result:
        print(f'  "{row[0]}"')
    
    # Count by status
    result2 = db.session.execute(text('SELECT status, COUNT(*) FROM analysis_tasks GROUP BY status ORDER BY status'))
    print('\nStatus counts:')
    for row in result2:
        print(f'  {row[0]}: {row[1]}')
