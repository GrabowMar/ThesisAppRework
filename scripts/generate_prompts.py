"""Generate and analyze prompts for all requirement templates.

Outputs:
- generated/prompts/two-query/<template_slug>/*.md
- generated/prompts/four-query/<template_slug>/*.md
- reports/prompts_analysis.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

# Ensure src is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.paths import MISC_DIR, REQUIREMENTS_DIR, REPORTS_DIR, GENERATED_ROOT, GENERATED_RAW_API_PAYLOADS_DIR


def _format_endpoints(endpoints: List[Dict]) -> str:
    if not endpoints:
        return ""
    lines = []
    for ep in endpoints:
        method = ep.get("method", "GET")
        path = ep.get("path", "/")
        desc = ep.get("description", "")
        lines.append(f"- {method} {path}: {desc}")
    return "\n".join(lines)


def _load_requirements() -> Dict[str, Dict]:
    templates = {}
    for path in sorted(REQUIREMENTS_DIR.glob("*.json")):
        templates[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return templates


def _build_backend_api_context(reqs: Dict) -> str:
    user_eps = _format_endpoints(reqs.get("api_endpoints", []))
    admin_eps = _format_endpoints(reqs.get("admin_api_endpoints", []))
    parts = []
    if user_eps:
        parts.append("USER API ENDPOINTS:\n" + user_eps)
    if admin_eps:
        parts.append("\nADMIN API ENDPOINTS:\n" + admin_eps)
    return "\n".join(parts).strip() or "(No API endpoints specified)"


def _render_two_query_prompts(reqs: Dict, env: Environment) -> Dict[str, str]:
    backend_template = env.get_template("two-query/backend.md.jinja2")
    frontend_template = env.get_template("two-query/frontend.md.jinja2")

    backend_prompt = backend_template.render(
        name=reqs.get("name", "Application"),
        description=reqs.get("description", ""),
        backend_requirements=reqs.get("backend_requirements", []),
        admin_requirements=reqs.get("admin_requirements", []),
        api_endpoints=_format_endpoints(reqs.get("api_endpoints", [])),
        admin_api_endpoints=_format_endpoints(reqs.get("admin_api_endpoints", [])),
        data_model=reqs.get("data_model", {}),
    )

    frontend_prompt = frontend_template.render(
        name=reqs.get("name", "Application"),
        description=reqs.get("description", ""),
        frontend_requirements=reqs.get("frontend_requirements", []),
        admin_requirements=reqs.get("admin_requirements", []),
        backend_api_context=_build_backend_api_context(reqs),
    )

    return {
        "backend_user": backend_prompt,
        "frontend_user": frontend_prompt,
    }


def _render_four_query_prompts(reqs: Dict, env: Environment, scaffolding_context: Dict[str, str]) -> Dict[str, str]:
    prompts = {}
    context_base = {
        "name": reqs.get("name", "Application"),
        "description": reqs.get("description", ""),
        "backend_requirements": reqs.get("backend_requirements", []),
        "frontend_requirements": reqs.get("frontend_requirements", []),
        "admin_requirements": reqs.get("admin_requirements", []),
        "api_endpoints": _format_endpoints(reqs.get("api_endpoints", [])),
        "admin_api_endpoints": _format_endpoints(reqs.get("admin_api_endpoints", [])),
        "existing_models_summary": "No models defined yet.",
        **scaffolding_context,
    }

    prompts["backend_user"] = env.get_template("four-query/backend_user.md.jinja2").render(context_base)
    prompts["backend_admin"] = env.get_template("four-query/backend_admin.md.jinja2").render(context_base)
    prompts["frontend_user"] = env.get_template("four-query/frontend_user.md.jinja2").render(context_base)
    prompts["frontend_admin"] = env.get_template("four-query/frontend_admin.md.jinja2").render(context_base)

    return prompts


def _load_scaffolding_context() -> Dict[str, str]:
    scaffold_dir = MISC_DIR / "scaffolding" / "react-flask"
    backend_ctx = (scaffold_dir / "backend" / "SCAFFOLDING_CONTEXT.md").read_text(encoding="utf-8")
    frontend_ctx = (scaffold_dir / "frontend" / "SCAFFOLDING_CONTEXT.md").read_text(encoding="utf-8")
    return {
        "scaffolding_backend_context": backend_ctx,
        "scaffolding_frontend_context": frontend_ctx,
    }


def _write_prompt_files(base_dir: Path, template_slug: str, prompt_map: Dict[str, str], system_map: Dict[str, str]) -> None:
    out_dir = base_dir / template_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    for key, text in prompt_map.items():
        (out_dir / f"{key}.user.md").write_text(text, encoding="utf-8")

    for key, text in system_map.items():
        (out_dir / f"{key}.system.md").write_text(text, encoding="utf-8")


def _analyze_prompt(prompt_text: str) -> List[str]:
    issues = []
    lower = prompt_text.lower()
    if "would you like" in lower or "do you want" in lower or "may i" in lower:
        issues.append("Prompt contains question-like phrasing that may invite clarification.")
    if "access policy" not in lower and "public guest" not in lower and "public read-only" not in lower:
        issues.append("Prompt missing access policy guidance for public vs authenticated flows.")
    return issues


def _extract_system_prompt(source: str, func_name: str) -> str:
    marker = f"def {func_name}"
    start = source.find(marker)
    if start == -1:
        return ""
    snippet = source[start:]
    triple = 'return """'
    triple_pos = snippet.find(triple)
    if triple_pos == -1:
        return ""
    snippet = snippet[triple_pos + len(triple):]
    end = snippet.find('"""')
    if end == -1:
        return ""
    return snippet[:end].strip()


def main() -> None:
    templates = _load_requirements()

    env = Environment(
        loader=FileSystemLoader(str(MISC_DIR / "templates")),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    scaffolding_context = _load_scaffolding_context()

    out_root = GENERATED_ROOT / "prompts"
    two_query_dir = out_root / "two-query"
    four_query_dir = out_root / "four-query"
    two_query_dir.mkdir(parents=True, exist_ok=True)
    four_query_dir.mkdir(parents=True, exist_ok=True)

    # System prompts (2-query) extracted from generation_v2 source
    v2_source = (Path(__file__).parent.parent / "src" / "app" / "services" / "generation_v2" / "code_generator.py").read_text(encoding="utf-8")
    system_two = {
        "backend_user": _extract_system_prompt(v2_source, "_get_backend_system_prompt"),
        "frontend_user": _extract_system_prompt(v2_source, "_get_frontend_system_prompt"),
    }

    report_lines = ["# Prompt Analysis", "", "## Generated Prompt Files", ""]

    for slug, reqs in templates.items():
        # two-query
        two_prompts = _render_two_query_prompts(reqs, env)
        _write_prompt_files(two_query_dir, slug, two_prompts, system_two)

        # four-query
        four_prompts = _render_four_query_prompts(reqs, env, scaffolding_context)
        # load system prompts for guarded 4-query
        system_four = {
            "backend_user": (MISC_DIR / "prompts" / "system" / "backend_user.md").read_text(encoding="utf-8"),
            "backend_admin": (MISC_DIR / "prompts" / "system" / "backend_admin.md").read_text(encoding="utf-8"),
            "frontend_user": (MISC_DIR / "prompts" / "system" / "frontend_user.md").read_text(encoding="utf-8"),
            "frontend_admin": (MISC_DIR / "prompts" / "system" / "frontend_admin.md").read_text(encoding="utf-8"),
        }
        _write_prompt_files(four_query_dir, slug, four_prompts, system_four)

        # analysis
        report_lines.append(f"### {slug}")
        for key, prompt_text in {**two_prompts, **four_prompts}.items():
            issues = _analyze_prompt(prompt_text)
            if issues:
                report_lines.append(f"- {key}: " + "; ".join(issues))
        report_lines.append("")

    # Analyze existing raw payload prompts
    report_lines.append("## Existing Raw Payload Prompts")
    payload_files = sorted(GENERATED_RAW_API_PAYLOADS_DIR.glob("**/*_payload.json"))
    if not payload_files:
        report_lines.append("- No raw payloads found.")
    else:
        for payload_file in payload_files:
            try:
                data = json.loads(payload_file.read_text(encoding="utf-8"))
                messages = data.get("payload", {}).get("messages", [])
                content = "\n".join(
                    msg.get("content", "")
                    for msg in messages
                    if isinstance(msg.get("content", ""), str)
                )
                issues = _analyze_prompt(content)
                if issues:
                    report_lines.append(f"- {payload_file.name}: " + "; ".join(issues))
            except Exception as exc:
                report_lines.append(f"- {payload_file.name}: failed to analyze ({exc})")

    report_path = REPORTS_DIR / "prompts_analysis.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")


if __name__ == "__main__":
    main()
