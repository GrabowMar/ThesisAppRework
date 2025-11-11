import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.services.service_locator import ServiceLocator

app = create_app()
with app.app_context():
    service = ServiceLocator.get_unified_result_service()
    results = service.list_result_files('anthropic_claude-4.5-haiku-20251001', 1)
    print(f'Found {len(results)} result files')
    for r in results[:3]:
        print(f'  - Task: {r["task_id"]}')
        print(f'    Path: {r.get("path", "N/A")}')
        print()
