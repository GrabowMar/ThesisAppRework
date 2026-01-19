"""
Generate Sample Applications for Quick Validation
================================================

This script generates a few sample applications to quickly validate the generation pipeline.

The script generates applications for multiple AI models and requirement templates,
then attempts to build and run them to verify the generation quality.

Features:
- Generates apps for multiple models (Claude, GPT-4, Gemini)
- Tests multiple template types (CRUD, validation, utility)
- Builds and runs generated applications
- Checks for placeholder code that wasn't replaced
- Validates that applications start successfully

Outputs:
- generated/apps/test_model/app1/<template>/ - Generated application code
- Console output with build/run status for each combination

Usage:
    python scripts/run_sample_generations.py

Configuration:
- Models: anthropic_claude-3-5-haiku, openai_gpt-4, google_gemini-2.0-flash
- Templates: crud_todo_list, validation_xml_checker, utility_base64_tool
- Ports: Backend (5100+), Frontend (8100+)
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, "src")

from app.factory import create_app
from app.services.generation_v2 import generate_app
from app.services.generation_v2.config import GenerationConfig
from app.services.generation_v2.scaffolding import get_scaffolding_manager


MODEL_SLUGS: List[str] = [
    "anthropic_claude-3-5-haiku",
    "openai_gpt-4",
    "google_gemini-2.0-flash",
]
TEMPLATES: List[str] = [
    "crud_todo_list",
    "validation_xml_checker",
    "utility_base64_tool",
]

DEFAULT_BACKEND_PORT = 5100
DEFAULT_FRONTEND_PORT = 8100
DEFAULT_MODEL_SLUG = "test_model"
DEFAULT_APP_DIR = Path("generated/apps/test_model/app1")
PLACEHOLDER_MARKERS = (
    "This file will be completely replaced by LLM-generated code",
    "Placeholder implementations",
    "Implement your main interface here",
)


def _port_available(port: int, used_ports: set[int]) -> bool:
    if port in used_ports:
        return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            return False
    return True


def _find_free_port_pair(start_port: int, offset: int, used_ports: set[int]) -> tuple[int, int]:
    backend = start_port
    while True:
        frontend = backend + offset
        if _port_available(backend, used_ports) and _port_available(frontend, used_ports):
            return backend, frontend
        backend += 1


def _extract_backend_port(compose_path: str) -> int | None:
    import re

    content = Path(compose_path).read_text(encoding="utf-8", errors="ignore")
    match = re.search(r'BACKEND_PORT:-?(?P<host>\\d+)', content)
    if match:
        return int(match.group('host'))
    match = re.search(r"ports:\\n\\s*-\\s*[\"']?(?P<host>\\d+):", content)
    if match:
        return int(match.group('host'))
    return None


def _extract_frontend_port(compose_path: str) -> int | None:
    import re

    content = Path(compose_path).read_text(encoding="utf-8", errors="ignore")
    match = re.search(r'FRONTEND_PORT:-?(?P<host>\\d+)', content)
    if match:
        return int(match.group('host'))
    match = re.search(r"ports:\\n\\s*-\\s*[\"']?(?P<host>\\d+):\\s*80", content)
    if match:
        return int(match.group('host'))
    return None


def _frontend_is_placeholder(app_dir: str) -> bool:
    app_path = Path(app_dir) / "frontend" / "src" / "App.jsx"
    if not app_path.exists():
        return True
    content = app_path.read_text(encoding="utf-8", errors="ignore")
    return any(marker in content for marker in PLACEHOLDER_MARKERS)


def _filter_model_slugs(app, requested: List[str]) -> Tuple[List[str], List[str]]:
    from app.models import ModelCapability

    with app.app_context():
        available = {
            row[0] for row in ModelCapability.query.with_entities(ModelCapability.canonical_slug).all()
            if row[0]
        }
    missing = [slug for slug in requested if slug not in available]
    return [slug for slug in requested if slug in available], missing


def _load_openrouter_key_from_env_file() -> None:
    if os.getenv("OPENROUTER_API_KEY"):
        return
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    try:
        for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "OPENROUTER_API_KEY":
                cleaned = value.strip().strip('"').strip("'")
                if cleaned:
                    os.environ["OPENROUTER_API_KEY"] = cleaned
                return
    except Exception:
        return


def _sync_openrouter_models(app) -> dict:
    from app.services.data_initialization import DataInitializationService

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return {"loaded": 0, "errors": ["OPENROUTER_API_KEY not configured"]}
    with app.app_context():
        service = DataInitializationService()
        return service._load_from_openrouter_api(api_key)


def main() -> int:
    _load_openrouter_key_from_env_file()
    if not os.getenv("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY not set. Provide a key to generate real frontends.")
        return 1
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{os.path.abspath('instance/app.db')}")
    app = create_app()
    port_map: Dict[str, Tuple[int, int]] = {}
    placeholder_frontends: List[str] = []
    frontend_failures: List[str] = []
    used_ports: set[int] = set()
    model_failures: List[str] = []

    model_slugs, missing_models = _filter_model_slugs(app, MODEL_SLUGS)
    if missing_models:
        print("Missing models in database:", ", ".join(missing_models))
        print("Syncing models from OpenRouter...")
        sync_result = _sync_openrouter_models(app)
        if sync_result.get("errors"):
            print("OpenRouter sync errors:", "; ".join(sync_result["errors"]))
        elif sync_result.get("loaded", 0) > 0:
            print(f"Synced {sync_result['loaded']} models from OpenRouter.")
        model_slugs, missing_models = _filter_model_slugs(app, MODEL_SLUGS)
    if missing_models:
        model_failures.extend(missing_models)
    if not model_slugs:
        print("No available models found. Configure OPENROUTER_API_KEY and re-run.")
        return 1

    results = []
    app_index = 0
    next_backend_port = DEFAULT_BACKEND_PORT
    for model_slug in model_slugs:
        for template_slug in TEMPLATES:
            backend_port, frontend_port = _find_free_port_pair(
                next_backend_port,
                DEFAULT_FRONTEND_PORT - DEFAULT_BACKEND_PORT,
                used_ports,
            )
            used_ports.update({backend_port, frontend_port})
            next_backend_port = backend_port + 1
            with app.app_context():
                result = generate_app(
                    model_slug=model_slug,
                    template_slug=template_slug,
                    app_num=app_index + 1,
                    backend_port=backend_port,
                    frontend_port=frontend_port,
                ).to_dict()
            results.append(result)
            status = "success" if result.get("success") else "failed"
            app_dir = result.get("app_dir")
            app_num = "?"
            if app_dir:
                app_num = app_dir.rsplit("app", 1)[-1]
            print(f"{model_slug}/{template_slug}: {status} (app{app_num})")
            if not result.get("success"):
                print("  errors:", result.get("errors"))
                print("  generation failed; skipping build")
                app_index += 1
                continue

            if app_dir:
                if _frontend_is_placeholder(app_dir):
                    placeholder_frontends.append(str(app_dir))
                    print("  frontend: placeholder detected (skipping build)")
                else:
                    port_map[str(app_dir)] = (backend_port, frontend_port)
                    compose_path = os.path.join(app_dir, "docker-compose.yml")
                    try:
                        subprocess.run(
                            ["docker", "compose", "-f", compose_path, "build"],
                            check=True,
                        )
                        print(f"  build: success ({compose_path})")
                    except subprocess.CalledProcessError as exc:
                        print(f"  build: failed ({compose_path})")
                        print(f"  build error: {exc}")
            app_index += 1

    failures = [r for r in results if not r.get("success")]

    for app_dir, (backend_port, frontend_port) in port_map.items():
        compose_path = os.path.join(app_dir, "docker-compose.yml")
        try:
            subprocess.run(
                ["docker", "compose", "-f", compose_path, "down", "--remove-orphans"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["docker", "compose", "-f", compose_path, "up", "-d"],
                check=True,
            )
            actual_backend_port = _extract_backend_port(compose_path) or backend_port
            actual_frontend_port = _extract_frontend_port(compose_path) or frontend_port
            curl_ok = False
            last_error = None
            for _ in range(6):
                try:
                    curl_result = subprocess.run(
                        ["curl", "-fsS", f"http://localhost:{actual_backend_port}/api/health"],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    print(f"  curl: success ({app_dir}) {curl_result.stdout.strip()}")
                    curl_ok = True
                    break
                except subprocess.CalledProcessError as exc:
                    last_error = exc
                    subprocess.run(["sleep", "2"], check=False)
            if not curl_ok:
                raise last_error or subprocess.CalledProcessError(1, "curl")
            for endpoint in ("health", ""):
                try:
                    subprocess.run(
                        ["curl", "-fsS", f"http://localhost:{actual_frontend_port}/{endpoint}"],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except subprocess.CalledProcessError:
                    frontend_failures.append(app_dir)
                    print(f"  frontend: failed ({app_dir}) /{endpoint}")
        except subprocess.CalledProcessError as exc:
            print(f"  curl: failed ({app_dir}) {exc}")

    if failures or placeholder_frontends or frontend_failures or model_failures:
        print("\nSample generation completed with failures (see errors above).")
        if model_failures:
            print(f"Missing model slugs: {', '.join(model_failures)}")
        if placeholder_frontends:
            print(f"Placeholder frontends detected: {len(placeholder_frontends)}")
        if frontend_failures:
            print(f"Frontend curl failures detected: {len(frontend_failures)}")
    else:
        print("\nAll sample generations succeeded.")
    return 1 if failures or placeholder_frontends or frontend_failures or model_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
