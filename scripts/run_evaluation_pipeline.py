"""
Run Evaluation Pipeline for Generation/Build/Analyze
=====================================================

This script executes the complete evaluation pipeline for AI-generated applications.

The pipeline processes evaluation queries from data/evaluation_queries.json and:
1. Generates applications using the specified model and template
2. Builds the generated applications
3. Runs static, dynamic, and performance analysis
4. Collects results and metrics

Outputs:
- data/evaluation_responses.jsonl - Detailed evaluation results
- generated/apps/<model>/app<N>/ - Generated application code
- results/<model>/app<N>/task_<id>/ - Analysis results

The script detects consistency errors in build outputs and provides comprehensive
evaluation metrics for comparing different AI models and generation approaches.

Usage:
    python scripts/run_evaluation_pipeline.py
    python scripts/run_evaluation_pipeline.py --model-slug anthropic_claude-3-5-haiku
    python scripts/run_evaluation_pipeline.py --template-slug flask_blog

Arguments:
    --model-slug: AI model to use for generation (default: from queries)
    --template-slug: Template to evaluate (default: from queries)
    --app-num: Application number for results (default: auto-increment)
    --force: Overwrite existing results
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
import argparse
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, "src")

from app.factory import create_app
from app.services.generation_v2 import generate_app

ROOT = Path(__file__).resolve().parents[1]
QUERIES_PATH = ROOT / "data" / "evaluation_queries.json"
RESPONSES_PATH = ROOT / "data" / "evaluation_responses.jsonl"

CONSISTENCY_PATTERNS = [
    re.compile(r"is not exported", re.IGNORECASE),
    re.compile(r"Module not found", re.IGNORECASE),
    re.compile(r"Cannot find", re.IGNORECASE),
]


def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def run_cmd(args: List[str], cwd: Path | None = None, timeout: int = 0) -> Dict[str, Any]:
    result = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=None if timeout == 0 else timeout,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout or "",
        "stderr": result.stderr or "",
    }


def detect_consistency_errors(output: str) -> int:
    return sum(1 for pattern in CONSISTENCY_PATTERNS if pattern.search(output))


def _load_existing_results() -> Dict[str, Dict[str, Any]]:
    """Load existing responses for resume support."""
    existing: Dict[str, Dict[str, Any]] = {}
    if not RESPONSES_PATH.exists():
        return existing
    try:
        for line in RESPONSES_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            key = _make_key(item)
            existing[key] = item
    except Exception:
        return existing
    return existing


def _make_key(item: Dict[str, Any]) -> str:
    return f"{item.get('template')}|{item.get('model_slug')}|{item.get('mode')}|{item.get('run_index')}"


def _append_response(item: Dict[str, Any]) -> None:
    RESPONSES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RESPONSES_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run evaluation pipeline batches")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of templates processed")
    parser.add_argument("--runs", type=int, default=0, help="Override run_count per template")
    args = parser.parse_args()

    if not QUERIES_PATH.exists():
        print(f"Missing queries file: {QUERIES_PATH}")
        return 1

    queries = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    if args.limit and args.limit > 0:
        queries = queries[: args.limit]
    app = create_app()

    existing = _load_existing_results()
    responses: List[Dict[str, Any]] = []

    with app.app_context():
        for entry in queries:
            template = entry["template"]
            model_slug = entry["model_slug"]
            mode = entry.get("mode", "guarded")
            run_count = int(entry.get("run_count", 1))
            if args.runs and args.runs > 0:
                run_count = args.runs

            for run_idx in range(run_count):
                key = f"{template}|{model_slug}|{mode}|{run_idx + 1}"
                if key in existing:
                    responses.append(existing[key])
                    continue
                start_ts = now_iso()
                gen_result = generate_app(
                    model_slug=model_slug,
                    template_slug=template,
                    app_num=None,
                    mode=mode,
                )

                response: Dict[str, Any] = {
                    "timestamp": start_ts,
                    "template": template,
                    "model_slug": model_slug,
                    "mode": mode,
                    "run_index": run_idx + 1,
                    "generation": {
                        "success": gen_result.success,
                        "errors": gen_result.errors,
                        "app_dir": str(gen_result.app_dir) if gen_result.app_dir else None,
                    },
                    "build": {
                        "success": False,
                        "consistency_errors": 0,
                        "returncode": None,
                    },
                    "analysis": {
                        "success": False,
                        "returncode": None,
                    },
                }

                if not gen_result.success or not gen_result.app_dir:
                    responses.append(response)
                    continue

                app_dir = Path(gen_result.app_dir)
                compose_path = app_dir / "docker-compose.yml"

                if compose_path.exists():
                    build_result = run_cmd(
                        ["docker", "compose", "-f", str(compose_path), "build"],
                        cwd=app_dir,
                        timeout=0,
                    )
                    output = (build_result["stdout"] + "\n" + build_result["stderr"]).strip()
                    response["build"]["returncode"] = build_result["returncode"]
                    response["build"]["consistency_errors"] = detect_consistency_errors(output)
                    response["build"]["success"] = build_result["returncode"] == 0

                # Run comprehensive analysis
                app_num = app_dir.name.replace("app", "")
                analysis_result = run_cmd(
                    [
                        sys.executable,
                        "analyzer/analyzer_manager.py",
                        "analyze",
                        model_slug,
                        str(app_num),
                        "comprehensive",
                    ],
                    cwd=ROOT,
                    timeout=0,
                )
                response["analysis"]["returncode"] = analysis_result["returncode"]
                response["analysis"]["success"] = analysis_result["returncode"] == 0

                responses.append(response)
                _append_response(response)

    print(f"Saved {len(responses)} responses to {RESPONSES_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
