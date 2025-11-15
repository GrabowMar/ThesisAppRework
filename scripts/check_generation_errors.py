import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.factory import create_app
from app.models import GeneratedCodeResult

app = create_app()

with app.app_context():
    # Find all Claude Haiku 4.5 generation results
    results = GeneratedCodeResult.query.filter_by(
        model='anthropic_claude-4.5-haiku-20251001'
    ).order_by(GeneratedCodeResult.app_num, GeneratedCodeResult.timestamp).all()
    
    print(f"Found {len(results)} generation results for anthropic_claude-4.5-haiku-20251001\n")
    
    failed_count = 0
    for result in results:
        if not result.success:
            failed_count += 1
            print(f"{'='*80}")
            print(f"Result ID: {result.result_id}")
            print(f"App #{result.app_num}: {result.app_name}")
            print(f"Success: {result.success}")
            print(f"Duration: {result.duration}s" if result.duration else "Duration: N/A")
            print(f"Timestamp: {result.timestamp}")
            print(f"\nError Message:")
            print(result.error_message if result.error_message else "  None")
            print()
    
    print(f"{'='*80}")
    print(f"\nSummary: {failed_count} failed out of {len(results)} total generation attempts")
