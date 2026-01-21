"""Check error messages for failed apps."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import GeneratedApplication, AnalysisTask, PipelineExecution

app = create_app()
with app.app_context():
    # Check GeneratedApplication records
    apps = GeneratedApplication.query.filter_by(model_slug='deepseek_deepseek-r1-0528').filter(
        GeneratedApplication.app_number.in_([8, 9])
    ).all()
    
    print("=== GeneratedApplication Records ===")
    for a in apps:
        print(f"\nApp {a.app_number}:")
        print(f"  Template: {a.template_slug}")
        print(f"  Generation Status: {a.generation_status.value if a.generation_status else None}")
        print(f"  Is Generation Failed: {a.is_generation_failed}")
        print(f"  Failure Stage: {a.failure_stage}")
        print(f"  Error Message: {a.error_message}")
    
    # Check for pipeline executions
    print("\n=== Recent Pipeline Executions ===")
    pipelines = PipelineExecution.query.order_by(PipelineExecution.created_at.desc()).limit(5).all()
    for p in pipelines:
        print(f"\nPipeline {p.pipeline_id}:")
        print(f"  Status: {p.status}")
        print(f"  Error: {p.error_message}")
    
    # Check for analysis tasks
    print("\n=== Analysis Tasks ===")
    tasks = AnalysisTask.query.filter_by(model_slug='deepseek_deepseek-r1-0528').filter(
        AnalysisTask.app_number.in_([8, 9])
    ).all()
    for t in tasks:
        print(f"\nTask {t.task_id} (app{t.app_number}):")
        print(f"  Analysis Type: {t.analysis_type.value if t.analysis_type else None}")
        print(f"  Status: {t.status.value if t.status else None}")
        print(f"  Error: {t.error_message}")
