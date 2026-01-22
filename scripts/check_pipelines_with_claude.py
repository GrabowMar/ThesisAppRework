"""Check for pipeline executions related to the deleted tasks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.models.pipeline import PipelineExecution

app = create_app()
with app.app_context():
    # Find pipelines that mention the claude model in their config
    all_pipelines = PipelineExecution.query.all()
    
    print(f"Checking {len(all_pipelines)} total pipelines\n")
    
    for p in all_pipelines:
        config = p.config
        models = config.get('generation', {}).get('models', [])
        
        if 'anthropic_claude-4.5-sonnet-20250929' in models:
            print(f"Pipeline: {p.pipeline_id}")
            print(f"  Status: {p.status}")
            print(f"  Stage: {p.current_stage}")
            print(f"  Created: {p.created_at}")
            
            # Check analysis task IDs in progress
            progress = p.progress
            main_task_ids = progress.get('analysis', {}).get('main_task_ids', [])
            print(f"  Main task IDs: {main_task_ids[:10]}...")  # Show first 10
            print()
