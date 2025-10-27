"""Test the new result file writer functionality."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from app.services.result_file_writer import write_task_result_files_by_id

app = create_app()

with app.app_context():
    # Get a completed task
    task = AnalysisTask.query.filter_by(
        target_model='anthropic_claude-4.5-haiku-20251001',
        target_app_number=1,
        status='completed'
    ).first()
    
    if not task:
        print("❌ No completed task found!")
        sys.exit(1)
    
    print(f"✅ Found task: {task.task_id}")
    print(f"   Model: {task.target_model}")
    print(f"   App: {task.target_app_number}")
    print(f"   Type: {task.analysis_type}")
    
    # Get the result_summary
    result_summary = task.get_result_summary()
    
    if not result_summary:
        print("❌ Task has no result_summary!")
        sys.exit(1)
    
    print(f"✅ Task has result_summary")
    
    # Test writing files
    print("\n📝 Testing file writer...")
    success = write_task_result_files_by_id(task.task_id, result_summary)
    
    if success:
        print("✅ File writer works correctly!")
    else:
        print("❌ File writer failed!")
        sys.exit(1)
    
    # Verify the files exist
    from pathlib import Path
    project_root = Path(__file__).parent
    model_safe = task.target_model.replace('/', '_').replace('\\', '_')
    results_dir = project_root / 'results' / model_safe / f'app{task.target_app_number}'
    
    if results_dir.exists():
        task_dirs = list(results_dir.glob('task_*'))
        print(f"\n✅ Found {len(task_dirs)} task directories in results")
        
        # Check if ResultFileService can find them
        from app.services.result_file_service import ResultFileService
        service = ResultFileService()
        descriptors = service.list_results(task.target_model, task.target_app_number)
        
        print(f"✅ ResultFileService found {len(descriptors)} descriptors")
        
        if descriptors:
            desc = descriptors[0]
            print(f"\n📊 First descriptor:")
            print(f"   ID: {desc.identifier}")
            print(f"   Total findings: {desc.total_findings}")
            print(f"   Status: {desc.status}")
    else:
        print(f"❌ Results directory does not exist: {results_dir}")
        sys.exit(1)
    
    print("\n✨ All tests passed!")
