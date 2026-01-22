"""
Script to list all pipeline tasks in the database.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.extensions import db
from app.models.pipeline import PipelineExecution

def list_pipelines():
    """List all pipeline tasks."""
    app = create_app()
    
    with app.app_context():
        pipelines = PipelineExecution.query.order_by(PipelineExecution.created_at.desc()).all()
        
        print(f"Found {len(pipelines)} pipeline(s)\n")
        print("=" * 100)
        
        for p in pipelines:
            config = p.config
            gen_config = config.get('generation', {})
            models = gen_config.get('models', [])
            
            print(f"Pipeline ID: {p.pipeline_id}")
            print(f"  Status: {p.status}")
            print(f"  Stage: {p.current_stage}")
            print(f"  Models: {', '.join(models) if models else 'N/A'}")
            print(f"  Created: {p.created_at}")
            print(f"  Progress: {p.get_overall_progress()}%")
            print("-" * 100)

if __name__ == '__main__':
    list_pipelines()
