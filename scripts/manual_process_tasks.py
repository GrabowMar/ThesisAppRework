"""Manually trigger task execution using process_once() method."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.factory import create_app
from app.services.task_execution_service import task_execution_service

def main():
    app = create_app()
    with app.app_context():
        if task_execution_service is None:
            print("ERROR: TaskExecutionService not initialized")
            return
        
        print(f"Processing tasks (batch_size={task_execution_service.batch_size})...")
        processed = task_execution_service.process_once(limit=5)
        print(f"Processed {processed} tasks")

if __name__ == "__main__":
    main()
