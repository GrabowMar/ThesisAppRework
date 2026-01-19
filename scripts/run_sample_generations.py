"""Generate a few sample apps for quick validation.

Usage:
  python scripts/run_sample_generations.py [--skip-docker-build]

Prerequisites:
  - OPENROUTER_API_KEY must be set in .env file
  - Run 'python src/init_db.py' first to populate models
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import List

sys.path.insert(0, "src")

from app.factory import create_app
from app.services.generation_v2 import generate_app
from app.models import ModelCapability
from app.extensions import db


# Fallback model configuration
# These are used only if the database doesn't have the primary model
MODEL_SLUG = "anthropic_claude-3-5-haiku"
FALLBACK_MODELS = [
    ("anthropic_claude-3-5-haiku", "anthropic/claude-3.5-haiku"),
    ("anthropic_claude-3-haiku-20240307", "anthropic/claude-3-haiku-20240307"),
    ("google_gemini-2.0-flash-exp", "google/gemini-2.0-flash-exp"),
]

TEMPLATES: List[str] = [
    "crud_todo_list",
    "validation_xml_checker",
    "utility_base64_tool",
]


def ensure_model_exists(app) -> tuple[bool, str]:
    """Ensure a model exists in the database for generation.
    
    Returns:
        (success: bool, model_slug: str) - Whether setup succeeded and which model to use
    """
    with app.app_context():
        # Check if any models exist
        total_models = ModelCapability.query.count()
        
        if total_models > 0:
            # Check if our preferred model exists
            model = ModelCapability.query.filter_by(canonical_slug=MODEL_SLUG).first()
            if model:
                print(f"✓ Using model: {MODEL_SLUG}")
                return True, MODEL_SLUG
            
            # Try fallback models
            for slug, openrouter_id in FALLBACK_MODELS:
                model = ModelCapability.query.filter_by(canonical_slug=slug).first()
                if model:
                    print(f"✓ Using fallback model: {slug}")
                    return True, slug
            
            # Use any available model
            any_model = ModelCapability.query.first()
            if any_model:
                print(f"✓ Using available model: {any_model.canonical_slug}")
                return True, any_model.canonical_slug
        
        # No models in database - try to create a minimal fallback
        print("⚠ No models found in database.")
        
        # Check if OPENROUTER_API_KEY is set
        api_key = os.getenv('OPENROUTER_API_KEY')
        if not api_key:
            print("\n❌ Setup required:")
            print("   1. Set OPENROUTER_API_KEY in .env file")
            print("   2. Run: python src/init_db.py")
            print("   3. Try again\n")
            return False, ""
        
        # Create a minimal fallback model entry for testing
        # Use only the first fallback model
        slug, openrouter_id = FALLBACK_MODELS[0]
        print(f"   Creating minimal model entry for {slug}...")
        try:
            
            # Extract provider from model ID
            provider = openrouter_id.split('/')[0] if '/' in openrouter_id else 'unknown'
            model_name = openrouter_id.split('/')[-1] if '/' in openrouter_id else openrouter_id
            
            # base_model_id is the model ID without variant suffix (e.g., without :free)
            base_model_id = openrouter_id.split(':')[0] if ':' in openrouter_id else openrouter_id
            
            new_model = ModelCapability(
                model_id=openrouter_id,
                canonical_slug=slug,
                base_model_id=base_model_id,
                provider=provider,
                model_name=model_name,
                installed=True,
                context_window=200000,
                max_output_tokens=8192,
                input_price_per_token=0.000001,
                output_price_per_token=0.000005,
            )
            db.session.add(new_model)
            db.session.commit()
            print(f"   ✓ Created fallback model: {slug}")
            return True, slug
        except Exception as e:
            print(f"   ❌ Failed to create fallback model: {e}")
            db.session.rollback()
            return False, ""
    
    return False, ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate sample applications for testing")
    parser.add_argument(
        '--skip-docker-build',
        action='store_true',
        help='Skip Docker build step (faster for testing code generation only)'
    )
    args = parser.parse_args()
    
    app = create_app()
    
    # Ensure we have a model to use
    success, model_slug = ensure_model_exists(app)
    if not success:
        return 1
    
    print(f"\nGenerating {len(TEMPLATES)} sample apps...")
    print(f"Model: {model_slug}")
    print("-" * 60)

    results = []
    for template_slug in TEMPLATES:
        print(f"\n📦 {template_slug}")
        with app.app_context():
            result = generate_app(
                model_slug=model_slug,
                template_slug=template_slug,
                app_num=None,
            ).to_dict()
        results.append(result)
        status = "✓ success" if result.get("success") else "✗ failed"
        app_dir = result.get("app_dir")
        app_num = "?"
        if app_dir:
            app_num = app_dir.rsplit("app", 1)[-1]
        print(f"   {status} (app{app_num})")
        if not result.get("success"):
            errors = result.get("errors", [])
            for error in errors:
                print(f"   Error: {error}")
            continue

        # Docker build step (optional)
        if app_dir and not args.skip_docker_build:
            from pathlib import Path
            compose_path = Path(app_dir) / "docker-compose.yml"
            if compose_path.exists():
                print(f"   Building Docker containers...")
                try:
                    subprocess.run(
                        ["docker", "compose", "-f", str(compose_path), "build"],
                        check=True,
                        capture_output=True,
                    )
                    print(f"   ✓ Docker build successful")
                except subprocess.CalledProcessError as exc:
                    print(f"   ✗ Docker build failed")
                    print(f"   {exc.stderr.decode() if exc.stderr else exc}")
            else:
                print(f"   ⚠ docker-compose.yml not found at {compose_path}")

    failures = [r for r in results if not r.get("success")]
    
    print("\n" + "=" * 60)
    if failures:
        print(f"❌ {len(failures)} generation(s) failed.")
        return 1

    print(f"✅ All {len(TEMPLATES)} sample generations succeeded!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
