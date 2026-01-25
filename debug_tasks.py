
import os
import sys
from pathlib import Path

# Add src to path
src_path = str(Path(__file__).resolve().parent / 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from app.factory import create_cli_app
from app.models import AnalysisTask, AnalysisStatus
from app.services.service_locator import ServiceLocator

app = create_cli_app()
with app.app_context():
    failed_tasks = AnalysisTask.query.filter(
        AnalysisTask.status.in_([AnalysisStatus.FAILED, AnalysisStatus.CANCELLED])
    ).order_by(AnalysisTask.created_at.desc()).limit(20).all()

    print(f"Found {len(failed_tasks)} failed/cancelled tasks:")
    for task in failed_tasks:
        print(f"--- Task {task.task_id} ---")
        print(f"Service: {task.service_name}")
        print(f"Model: {task.target_model}")
        print(f"App: {task.target_app_number}")
        print(f"Status: {task.status}")
        print(f"Error: {task.error_message}")
        print(f"Duration: {task.actual_duration}")
        print(f"Created/Started: {task.created_at} / {task.started_at}")
        print("")

    # Also check overall worker health if possible
    try:
        from analyzer.analyzer_manager import AnalyzerManager
        manager = AnalyzerManager()
        status = manager.get_container_status()
        print(f"Container status: {status}")
        
        # Check port accessibility
        for service_name, service_info in manager.services.items():
            accessible = manager.check_port_accessibility('localhost', service_info.port)
            print(f"Service {service_name} on port {service_info.port}: {'Accessible' if accessible else 'NOT Accessible'}")

    except Exception as e:
        print(f"Could not get container status: {e}")
