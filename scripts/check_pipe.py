"""Quick script to check pipeline status."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import PipelineExecution

app = create_app()
with app.app_context():
    pipeline = PipelineExecution.query.filter_by(pipeline_id='pipeline_285998fc1721').first()
    if not pipeline:
        print('Pipeline not found')
        sys.exit(0)
    
    print(f'Pipeline: {pipeline.pipeline_id}')
    print(f'Status: {pipeline.status}')
    print(f'Stage: {pipeline.current_stage}')
    print(f'Job Index: {pipeline.current_job_index}')
    
    gen = pipeline.progress.get('generation', {})
    print(f'\n=== Generation ===')
    print(f'Total: {gen.get("total")}, Completed: {gen.get("completed")}, Failed: {gen.get("failed")}')
    
    for i, r in enumerate(gen.get('results', [])):
        status = 'SUCCESS' if r.get('success') else 'FAILED'
        err = r.get('error', '')[:80] if r.get('error') else ''
        print(f'  Job {i}: {r.get("model_slug")}/app{r.get("app_number")} - {status} {err}')
