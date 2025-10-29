"""
Trigger a test analysis to verify new logging implementation.
"""
import sys
import os
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set up Flask app context
os.environ['TESTING'] = 'true'
from app.factory import create_app
from app.models import AnalysisTask, db
from app import constants

def main():
    """Trigger analysis on an existing app to test logging."""
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("TRIGGER TEST ANALYSIS")
        print("=" * 80)
        
        # Look for an existing app to analyze
        from app.models import GeneratedApplication
        
        # Get first available app
        app_to_analyze = db.session.query(GeneratedApplication).first()
        if app_to_analyze:
            print(f"\nFound app to analyze:")
            print(f"  Model: {app_to_analyze.model_slug}")
            print(f"  App Number: {app_to_analyze.app_number}")
            
            # Insert task using raw SQL to avoid model complexity
            task_id = f"test_{int(time.time())}"
            db.session.execute(
                db.text("""
                    INSERT INTO analysis_tasks (
                        task_id, target_model, target_app_number,
                        analyzer_config_id, status, task_name,
                        created_at, updated_at
                    ) VALUES (
                        :task_id, :model, :app_num,
                        1, 'PENDING', 'security',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                """),
                {
                    'task_id': task_id,
                    'model': app_to_analyze.model_slug,
                    'app_num': app_to_analyze.app_number
                }
            )
            db.session.commit()
            
            print(f"\nCreated task: {task_id}")
            print(f"Status: pending")
            print("\n✓ Task created successfully!")
            print("\nTaskExecutionService will pick it up within 5 seconds.")
            print("Watch Flask console output for [EXEC], [ORCH], [UNIFIED], [ANALYZER-SUBPROCESS] logs.")
            print("\nOr check: logs\\app.log")
            return
        
        print("\n❌ No apps found to analyze!")
        print("Generate an app first using the web UI.")

if __name__ == "__main__":
    main()
