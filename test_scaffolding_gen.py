"""Test generation with new stub scaffolding."""
import sys
sys.path.insert(0, 'src')

import json
import logging
from pathlib import Path

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from app.factory import create_app
from app.services.generation_v2 import generate_app, GenerationConfig, GenerationMode
from app.services.generation_v2.code_generator import get_code_generator
from app.paths import GENERATED_RAW_API_PAYLOADS_DIR, GENERATED_RAW_API_RESPONSES_DIR

# Test templates
TEST_TEMPLATES = [
    'crud_todo_list',
]

MODEL = 'anthropic_claude-3-5-haiku'
START_APP_NUM = 910  # Use fresh app numbers


def analyze_generation(template: str, app_num: int):
    """Generate one app and analyze what was sent/received."""
    print(f"\n{'='*60}")
    print(f"GENERATING: {template} (app{app_num})")
    print('='*60)
    
    result = generate_app(
        model_slug=MODEL,
        template_slug=template,
        app_num=app_num,
        mode='guarded'
    )
    
    print(f"\n✅ Success: {result.success}")
    print(f"📁 App dir: {result.app_dir}")
    
    if result.artifacts:
        print(f"📄 Files written: {len(result.artifacts)}")
        for f in result.artifacts[:10]:
            print(f"   - {f}")
    
    if result.metrics:
        print(f"⏱️  Duration: {result.metrics.get('duration_seconds', 0):.1f}s")
    
    if result.error:
        print(f"❌ Error: {result.error}")
    
    # Check generated files
    if result.app_dir:
        app_path = Path(result.app_dir)
        print(f"\n📂 Generated structure:")
        for f in sorted(app_path.rglob('*.py'))[:8]:
            rel = f.relative_to(app_path)
            lines = len(f.read_text().splitlines())
            print(f"   {rel} ({lines} lines)")
        for f in sorted(app_path.rglob('*.jsx'))[:8]:
            rel = f.relative_to(app_path)
            lines = len(f.read_text().splitlines())
            print(f"   {rel} ({lines} lines)")
    
    return result


def main():
    app = create_app()
    
    with app.app_context():
        results = []
        
        for i, template in enumerate(TEST_TEMPLATES):
            app_num = START_APP_NUM + i  # Use high app numbers for testing
            try:
                result = analyze_generation(template, app_num)
                results.append({
                    'template': template,
                    'app_num': app_num,
                    'success': result.success,
                    'files': len(result.artifacts) if result.artifacts else 0,
                    'error': result.error,
                })
            except Exception as e:
                print(f"❌ FAILED: {e}")
                results.append({
                    'template': template,
                    'app_num': app_num,
                    'success': False,
                    'error': str(e),
                })
        
        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print('='*60)
        for r in results:
            status = "✅" if r['success'] else "❌"
            print(f"{status} {r['template']}: {r.get('files', 0)} files")


if __name__ == '__main__':
    main()
