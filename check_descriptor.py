"""Check what the ResultFileDescriptor sees for these tasks."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from app.services.result_file_service import ResultFileService

app = create_app()

with app.app_context():
    service = ResultFileService()
    
    # Get task
    task = AnalysisTask.query.filter_by(
        target_model='anthropic_claude-4.5-haiku-20251001',
        target_app_number=1,
        analysis_type='security'
    ).order_by(AnalysisTask.created_at.desc()).first()
    
    if not task:
        print("No task found!")
        sys.exit(1)
    
    print(f"Task: {task.task_id}")
    print(f"Model: {task.target_model}")
    print(f"App: {task.target_app_number}")
    print()
    
    # Get descriptors
    descriptors = service.list_results(
        model_slug=task.target_model,
        app_number=task.target_app_number
    )
    
    print(f"Found {len(descriptors)} descriptors")
    print()
    
    for desc in descriptors:
        print(f"Descriptor: {desc.identifier}")
        print(f"  Status: {desc.status}")
        print(f"  Total findings: {desc.total_findings}")
        print(f"  Severity breakdown: {desc.severity_breakdown}")
        print(f"  Timestamp: {desc.timestamp}")
        print()
