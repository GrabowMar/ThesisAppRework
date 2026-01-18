"""Generate a few sample apps for quick validation.

Usage:
  python scripts/run_sample_generations.py
"""
from __future__ import annotations

import subprocess
import sys
from typing import List

sys.path.insert(0, "src")

from app.factory import create_app
from app.services.generation_v2 import generate_app


MODEL_SLUG = "anthropic_claude-3-5-haiku"
TEMPLATES: List[str] = [
    "crud_todo_list",
    "validation_xml_checker",
    "utility_base64_tool",
]


def main() -> int:
    app = create_app()

    results = []
    for template_slug in TEMPLATES:
        with app.app_context():
            result = generate_app(
                model_slug=MODEL_SLUG,
                template_slug=template_slug,
                app_num=None,
            ).to_dict()
        results.append(result)
        status = "success" if result.get("success") else "failed"
        app_dir = result.get("app_dir")
        app_num = "?"
        if app_dir:
            app_num = app_dir.rsplit("app", 1)[-1]
        print(f"{template_slug}: {status} (app{app_num})")
        if not result.get("success"):
            print("  errors:", result.get("errors"))
            continue

        if app_dir:
            compose_path = f"{app_dir}\\docker-compose.yml"
            try:
                subprocess.run(
                    ["docker", "compose", "-f", compose_path, "build"],
                    check=True,
                )
                print(f"  build: success ({compose_path})")
            except subprocess.CalledProcessError as exc:
                print(f"  build: failed ({compose_path})")
                print(f"  build error: {exc}")

    failures = [r for r in results if not r.get("success")]
    if failures:
        print(f"\n{len(failures)} generation(s) failed.")
        return 1

    print("\nAll sample generations succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
