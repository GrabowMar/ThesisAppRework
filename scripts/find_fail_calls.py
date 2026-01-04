"""Find all places where pipeline.fail() or status='failed' could be set"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.models.pipeline import PipelineExecution

app = create_app()
with app.app_context():
    # Check the pipeline's fail method to understand how it sets error_message
    pipeline = PipelineExecution.query.filter_by(pipeline_id='pipeline_2775f4667b91').first()
    if pipeline:
        print(f"Pipeline: {pipeline.pipeline_id}")
        print(f"Status: {pipeline.status}")
        print(f"Error: {pipeline.error_message}")
        print()
        
        # Check the method signature of fail()
        import inspect
        print("=" * 60)
        print("PipelineExecution.fail() method source:")
        print("=" * 60)
        print(inspect.getsource(PipelineExecution.fail))
