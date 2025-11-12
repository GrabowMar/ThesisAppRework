"""
Quick DB check for tasks with actual data
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

import os
os.environ['TESTING'] = '1'

from app.factory import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app('development')

with app.app_context():
    # Check tasks with result_summary
    query = text("""
        SELECT 
            task_id, 
            target_model, 
            target_app_number, 
            status,
            result_summary IS NOT NULL as has_summary,
            LENGTH(result_summary) as summary_length
        FROM analysis_tasks 
        WHERE result_summary IS NOT NULL 
        ORDER BY created_at DESC 
        LIMIT 10
    """)
    
    results = db.session.execute(query).fetchall()
    
    print("\nTasks with result_summary data:")
    print("="*80)
    for row in results:
        print(f"\nTask: {row[0]}")
        print(f"  Model: {row[1]}")
        print(f"  App: {row[2]}")
        print(f"  Status: {row[3]}")
        print(f"  Has Summary: {row[4]}")
        print(f"  Summary Length: {row[5]} bytes")
    
    if not results:
        print("No tasks with result_summary found")
        print("\nLet's check all Haiku tasks:")
        query2 = text("""
            SELECT task_id, status, created_at
            FROM analysis_tasks
            WHERE target_model LIKE '%haiku%'
            ORDER BY created_at DESC
        """)
        results2 = db.session.execute(query2).fetchall()
        for row in results2:
            print(f"  {row[0]}: {row[1]} ({row[2]})")
