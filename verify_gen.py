import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from app.factory import create_app
from app.services.generation_v2.service import generate_app
from app.services.generation_v2.config import GenerationConfig

def trigger_gen(model_slug, template_slug, app_num):
    print(f"Triggering {template_slug} (App {app_num})...")
    result = generate_app(
        model_slug=model_slug,
        template_slug=template_slug,
        app_num=app_num
    )
    print(f"  Result: {'SUCCESS' if result.success else 'FAILED'}")
    if not result.success:
        print(f"  Errors: {result.errors}")
    return result

def main():
    app = create_app()
    with app.app_context():
        model = "qwen_qwen3-coder-30b-a3b-instruct"
        
        # Sequentially trigger generations to avoid any race conditions or loop issues
        trigger_gen(model, "api_url_shortener", 17)
        trigger_gen(model, "api_weather_display", 17)
        trigger_gen(model, "workflow_task_board", 17)

if __name__ == "__main__":
    main()
