
from app.extensions import db
from app.models import PipelineExecution
from app import create_app

app = create_app()
with app.app_context():
    pipelines = PipelineExecution.query.all()
    print(f"Total pipelines: {len(pipelines)}")
    for p in pipelines:
        print(f"ID: {p.pipeline_id}, Status: {p.status}, Stage: {p.current_stage}, Progress: {p.progress.get('analysis', {}).get('completed', 0)}/{p.progress.get('analysis', {}).get('total', 0)}")
