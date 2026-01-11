"""Generate and evaluate prompts with 100% app parity.

This script uses the exact same prompt-building code paths as the web app:
- Requirements loaded from misc/requirements/*.json
- Jinja2 prompt templates in misc/templates/**
- System prompts in misc/prompts/system/**
- Scaffolding context loaded from generated/apps/<model>/app<N>/...

By default it generates the 30 guarded backend user prompts (Query 1) for all
requirement templates.

Usage:
  python scripts/generate_and_evaluate_prompts.py
  python scripts/generate_and_evaluate_prompts.py --all-queries
  python scripts/generate_and_evaluate_prompts.py --modes guarded unguarded

Exit codes:
  0: success
  1: evaluation failures
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"

sys.path.insert(0, str(SRC_DIR))


@dataclass
class PromptJob:
    component: str  # 'backend' | 'frontend'
    query_type: str  # 'user' | 'admin'


def _iter_jobs(all_queries: bool) -> List[PromptJob]:
    if not all_queries:
        # The 30 deterministic prompts: guarded Query 1 (backend_user)
        return [PromptJob(component="backend", query_type="user")]

    return [
        PromptJob(component="backend", query_type="user"),
        PromptJob(component="backend", query_type="admin"),
        PromptJob(component="frontend", query_type="user"),
        PromptJob(component="frontend", query_type="admin"),
    ]


def _expected_system_prompt_path(component: str, query_type: str, generation_mode: str) -> Optional[Path]:
    prompts_dir = PROJECT_ROOT / "misc" / "prompts" / "system"

    if generation_mode == "unguarded":
        p = prompts_dir / f"{component}_unguarded.md"
        return p if p.exists() else None

    # guarded mode prefers component_querytype, then component fallback for user
    p = prompts_dir / f"{component}_{query_type}.md"
    if p.exists():
        return p

    if query_type == "user":
        p = prompts_dir / f"{component}.md"
        return p if p.exists() else None

    return None


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _basic_prompt_checks(label: str, system_prompt: str, user_prompt: str) -> List[str]:
    issues: List[str] = []

    if not system_prompt.strip():
        issues.append(f"{label}: empty system prompt")

    if not user_prompt.strip():
        issues.append(f"{label}: empty user prompt")

    # Scaffolding placeholders indicate parity problems (scaffold not created or wrong paths)
    if "<!-- File not found" in user_prompt or "<!-- Error reading file" in user_prompt:
        issues.append(f"{label}: scaffolding context missing (prompt contains scaffolding placeholder)")

    # Output format is a critical constraint to keep generation stable
    if "## Output Format" not in user_prompt:
        issues.append(f"{label}: missing '## Output Format' section")

    # Guard against the known bad content that used to be in frontend_user
    if "Step 1: Define Models" in user_prompt and "Frontend" in user_prompt:
        issues.append(f"{label}: contains backend-only guidance in frontend prompt")

    return issues


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=str(PROJECT_ROOT / "generated" / "prompts_parity"))
    parser.add_argument("--model-slug", default="prompt_preview")
    parser.add_argument("--app-num", type=int, default=1)
    parser.add_argument("--modes", nargs="+", default=["guarded"], choices=["guarded", "unguarded"])
    parser.add_argument("--all-queries", action="store_true", help="Generate all 4 guarded queries (and both modes if selected)")
    parser.add_argument("--strict", action="store_true", help="Treat requirement warnings as failures")

    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)

    from app.factory import create_app
    from app.extensions import db
    from app.services.generation import CodeGenerator, GenerationConfig, ScaffoldingManager, get_generation_service

    # Requirement validation uses the same schema checks the repo ships with.
    sys.path.insert(0, str(PROJECT_ROOT))
    from scripts.validate_requirements_templates import validate_file  # type: ignore

    app = create_app()

    all_issues: List[str] = []

    with app.app_context():
        db.create_all()

        svc = get_generation_service()
        catalog = svc.get_template_catalog()
        if not catalog:
            print("No templates found in misc/requirements")
            return 1

        # Validate requirement JSONs
        warnings = 0
        errors = 0
        for item in catalog:
            slug = item["slug"]
            req_path = PROJECT_ROOT / "misc" / "requirements" / f"{slug.lower().replace('-', '_')}.json"
            report = validate_file(req_path)
            errors += len(report.errors)
            warnings += len(report.warnings)
        if errors:
            all_issues.append(f"requirements validation: {errors} errors")
        if args.strict and warnings:
            all_issues.append(f"requirements validation: {warnings} warnings (strict)")

        # Ensure scaffolding exists so prompts include real context
        scaffolder = ScaffoldingManager()
        for mode in args.modes:
            ok = scaffolder.scaffold(args.model_slug, args.app_num, generation_mode=mode)
            if not ok:
                all_issues.append(f"scaffolding failed for mode={mode}")

        generator = CodeGenerator()
        jobs = _iter_jobs(args.all_queries)

        for item in catalog:
            template_slug = item["slug"]

            for mode in args.modes:
                for job in jobs:
                    existing_models_summary = None
                    if mode == "guarded" and job.component == "backend" and job.query_type == "admin":
                        # For parity with the app, this summary is extracted from the generated app's models.py.
                        # In this offline run we can only extract what exists on disk.
                        app_dir = scaffolder.get_app_dir(args.model_slug, args.app_num, template_slug)
                        existing_models_summary = svc._extract_models_summary(app_dir)  # noqa: SLF001

                    cfg = GenerationConfig(
                        model_slug=args.model_slug,
                        app_num=args.app_num,
                        template_slug=template_slug,
                        component=job.component,
                        query_type=job.query_type,
                        generation_mode=mode,
                        existing_models_summary=existing_models_summary,
                    )

                    user_prompt = generator._build_prompt(cfg)
                    system_prompt = generator._get_system_prompt(job.component, job.query_type, mode)

                    # Parity check: if a system prompt file exists, the loaded content must match it exactly
                    expected = _expected_system_prompt_path(job.component, job.query_type, mode)
                    if expected is None:
                        all_issues.append(
                            f"{template_slug}/{mode}/{job.component}_{job.query_type}: missing system prompt file (will fall back to embedded prompt)"
                        )
                    else:
                        expected_text = expected.read_text(encoding="utf-8")
                        if expected_text != system_prompt:
                            all_issues.append(
                                f"{template_slug}/{mode}/{job.component}_{job.query_type}: system prompt mismatch vs {expected.name}"
                            )

                    label = f"{template_slug}/{mode}/{job.component}_{job.query_type}"
                    all_issues.extend(_basic_prompt_checks(label, system_prompt, user_prompt))

                    base = out_dir / template_slug / mode / f"{job.component}_{job.query_type}"
                    _write_text(base.with_suffix(".system.md"), system_prompt)
                    _write_text(base.with_suffix(".user.md"), user_prompt)

                    combined = f"=== SYSTEM ===\n{system_prompt}\n\n=== USER ===\n{user_prompt}\n"
                    _write_text(base.with_suffix(".combined.md"), combined)

    if all_issues:
        print("Prompt generation/evaluation FAILED:\n")
        for issue in all_issues:
            print(f"- {issue}")
        print(f"\nWrote prompts to: {out_dir}")
        return 1

    print(f"OK: generated prompts for {len(catalog)} templates")
    print(f"Wrote prompts to: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
