"""
Quick Generation and Evaluation
===============================

This script generates applications using lightweight models and performs basic evaluation.

The script uses smaller, faster AI models to quickly generate applications for
multiple templates, then runs basic validation checks to ensure generation quality.

Features:
- Uses lightweight models (Llama 3.2 3B, Ministral 3B, Gemma 3 4B)
- Tests multiple template types (CRUD, validation, utility)
- Performs basic structural validation
- Checks for clarification questions in AI responses
- Validates file structure and basic code presence

Outputs:
- Generated applications in generated/apps/<model>/app<N>/
- Console output with evaluation results
- Raw API responses for analysis

Usage:
    python scripts/run_quick_generations_and_eval.py

This script is useful for quick validation of the generation pipeline and
catching obvious issues with new models or templates.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(SRC_DIR))

from app.factory import create_app
from app.services.generation_v2 import generate_app
from app.paths import GENERATED_RAW_API_RESPONSES_DIR

MODELS = [
    "meta-llama_llama-3.2-3b-instruct",
    "mistralai_ministral-3b",
    "google_gemma-3-4b-it",
]

TEMPLATES = [
    "crud_todo_list",
    "validation_xml_checker",
    "api_url_shortener",
]


def _scan_response_text(response_path: Path) -> str:
    data = json.loads(response_path.read_text(encoding="utf-8"))
    choices = data.get("response", {}).get("choices", [])
    if not choices:
        return ""
    msg = choices[0].get("message", {})
    return msg.get("content", "") if isinstance(msg.get("content", ""), str) else ""


def _eval_generated_app(app_dir: Path, model_slug: str, app_num: int) -> List[str]:
    issues: List[str] = []
    backend_path = app_dir / "backend" / "app.py"
    frontend_path = app_dir / "frontend" / "src" / "App.jsx"

    if not backend_path.exists():
        issues.append("Missing backend/app.py")
    if not frontend_path.exists():
        issues.append("Missing frontend/src/App.jsx")

    # Check raw responses for clarification questions
    safe_model = model_slug
    response_dir = GENERATED_RAW_API_RESPONSES_DIR / safe_model / f"app{app_num}"
    if response_dir.exists():
        for resp in response_dir.glob("*_response.json"):
            text = _scan_response_text(resp).lower()
            if "would you like" in text or "do you want" in text or "may i" in text:
                issues.append(f"Clarification question in {resp.name}")
                break
    else:
        issues.append("Missing raw responses directory")

    return issues


def main() -> int:
    app = create_app()
    results: List[Dict[str, Any]] = []

    with app.app_context():
        for idx, model_slug in enumerate(MODELS, start=1):
            template_slug = TEMPLATES[(idx - 1) % len(TEMPLATES)]
            result = generate_app(
                model_slug=model_slug,
                template_slug=template_slug,
                app_num=None,
            ).to_dict()

            entry: Dict[str, Any] = {
                "model_slug": model_slug,
                "template_slug": template_slug,
                "success": result.get("success", False),
                "app_dir": result.get("app_dir"),
                "errors": result.get("errors"),
            }

            if result.get("success") and result.get("app_dir"):
                app_dir = Path(result["app_dir"])
                try:
                    app_num = int(app_dir.name.replace("app", ""))
                except Exception:
                    app_num = None
                if app_num is not None:
                    entry["eval_issues"] = _eval_generated_app(app_dir, model_slug, app_num)
            results.append(entry)

    out_path = PROJECT_ROOT / "reports" / "quick_generation_eval.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
