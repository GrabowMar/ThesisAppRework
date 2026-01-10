"""Check detailed pipeline status."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import PipelineExecution, AnalysisTask
from app.extensions import db

# Allow passing pipeline_id as argument
pipeline_id = sys.argv[1] if len(sys.argv) > 1 else None

app = create_app()
with app.app_context():
    # Check the active pipeline (newest running, or specified)
    if pipeline_id:
        pipeline = PipelineExecution.query.filter_by(pipeline_id=pipeline_id).first()
    else:
        pipeline = PipelineExecution.query.filter(
            PipelineExecution.status.in_(['running', 'pending'])
        ).order_by(PipelineExecution.created_at.desc()).first()
    
    if not pipeline:
        print("Pipeline not found!")
        sys.exit(1)
    
    print(f"=== Pipeline: {pipeline.pipeline_id} ===")
    print(f"Status: {pipeline.status}")
    print(f"Stage: {pipeline.current_stage}")
    print(f"Job Index: {pipeline.current_job_index}")
    print()
    
    progress = pipeline.progress
    task_ids = progress.get('analysis', {}).get('task_ids', [])
    print(f"Total tasks: {len(task_ids)}")
    print()
    
    for tid in task_ids:
        if tid.startswith('skipped') or tid.startswith('error:'):
            print(f"  {tid}")
            continue
            
        task = AnalysisTask.query.filter_by(task_id=tid).first()
        if task:
            status_val = task.status.value if task.status else 'N/A'
            print(f"Task: {tid}")
            print(f"  Target: {task.target_model}/app{task.target_app_number}")
            print(f"  Status: {status_val}")
            print(f"  Progress: {task.progress_percentage}%")
            if task.error_message:
                print(f"  Error: {task.error_message[:100]}...")
            
            # Check subtasks
            subtasks = list(task.subtasks) if hasattr(task, 'subtasks') else []
            if subtasks:
                print(f"  Subtasks ({len(subtasks)}):")
                for st in subtasks:
                    st_status = st.status.value if st.status else 'unknown'
                    err = f" - {st.error_message[:50]}..." if st.error_message else ""
                    print(f"    - {st.service_name}: {st_status}{err}")
            print()
