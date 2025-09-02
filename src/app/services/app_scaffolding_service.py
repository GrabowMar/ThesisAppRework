"""Application Scaffolding Service
=================================

Adapts a subset of the legacy `misc/generateApps.py` functionality into a Flask
service so the web UI can generate multi-app project scaffolds for multiple
AI models.

Initial capabilities (MVP):
 - Parse model input (OpenRouter URL or comma separated list)
 - Provide color mapping per provider (for future UI use)
 - Port allocation logic (backend + frontend) matching original algorithm
 - Template existence validation (non-destructive)
 - Dry-run preview of what would be generated (models, apps, port ranges)
 - Actual generation stub (creates directory tree & copies templates if found)
 - Configuration file emission (ports + model colors) similar to original JSON

Deferred for later parity (documented in parity roadmap):
 - Detailed per-file templating substitutions
 - Docker compose generation per model
 - Individual app backend/frontend templating (placeholders only for now)
 - Logging per model (currently a single logger)

Usage pattern:
    from app.services.app_scaffolding_service import get_app_scaffolding_service
    svc = get_app_scaffolding_service()
    models, colors = svc.parse_models(user_input)
    preview = svc.preview_generation(models)
    result = svc.generate(models, dry_run=False)

Thread safety: kept simple; not intended for heavy concurrent use yet.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import os
import json
import re
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (mirrors values from legacy script where sensible)
# ---------------------------------------------------------------------------

class ScaffoldConfig:
    MODELS_DIR = Path("models")
    LOGS_DIR = "_logs"
    TEMPLATES_DIR = Path("misc") / "z_code_templates"
    BASE_BACKEND_PORT = 5001
    BASE_FRONTEND_PORT = 8001
    PORTS_PER_APP = 2
    BUFFER_PORTS = 10
    APPS_PER_MODEL = 30
    PYTHON_BASE_IMAGE = "python:3.14-slim"  # placeholder

    PROVIDER_COLORS = {
        "mistralai": "#8B5CF6",
        "moonshotai": "#10B981",
        "deepseek": "#9333EA",
        "sarvamai": "#DC2626",
        "google": "#3B82F6",
        "meta-llama": "#F59E0B",
        "microsoft": "#6366F1",
        "opengvlab": "#6B7280",
        "qwen": "#F43F5E",
        "nvidia": "#0D9488",
        "anthropic": "#D97706",
        "x-ai": "#B91C1C",
        "minimax": "#7E22CE",
        "openai": "#14B8A6",
        "agentica-org": "#16A34A",
        "nousresearch": "#059669",
    }

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PortAssignment:
    backend: int
    frontend: int

@dataclass
class ModelPlan:
    name: str
    index: int
    port_range: Tuple[int, int]
    apps: Dict[int, PortAssignment] = field(default_factory=dict)

@dataclass
class GenerationPreview:
    models: List[ModelPlan]
    total_apps: int
    config_summary: Dict[str, Any]

@dataclass
class GenerationResult:
    preview: GenerationPreview
    generated: bool
    output_paths: List[Path]

# ---------------------------------------------------------------------------
# Service implementation
# ---------------------------------------------------------------------------

class AppScaffoldingService:
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = Path(base_path or os.getcwd())
        self.models_dir = self.base_path / ScaffoldConfig.MODELS_DIR
        self.templates_dir = self.base_path / ScaffoldConfig.TEMPLATES_DIR
        self.logs_dir = self.models_dir / ScaffoldConfig.LOGS_DIR
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------- Model Parsing --------------------------
    def parse_models(self, input_string: str) -> Tuple[List[str], Dict[str, str]]:
        input_string = input_string.strip()
        if not input_string:
            raise ValueError("Input string is empty")
        if input_string.startswith("http"):
            # Extract models= query parameter (simple regex, legacy-like)
            m = re.search(r"models=([^&#]+)", input_string)
            if not m:
                raise ValueError("Could not find 'models=' parameter in URL")
            raw_models = m.group(1)
        else:
            raw_models = input_string
        # Split and normalize
        models: List[str] = []
        for part in raw_models.split(','):
            part = part.strip()
            if not part:
                continue
            part = part.replace(' ', '')
            # Remove duplicates while preserving order
            if part not in models:
                models.append(part)
        if not models:
            raise ValueError("No models extracted")
        colors = self._generate_color_mapping(models)
        return models, colors

    def _generate_color_mapping(self, models: List[str]) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for m in models:
            provider = m.split('/', 1)[0] if '/' in m else 'unknown'
            mapping[m] = ScaffoldConfig.PROVIDER_COLORS.get(provider, '#999999')
        return mapping

    # ----------------------------- Ports ----------------------------------
    def calculate_port_range(self, model_index: int) -> Tuple[int, int]:
        ports_needed = ScaffoldConfig.APPS_PER_MODEL * ScaffoldConfig.PORTS_PER_APP + ScaffoldConfig.BUFFER_PORTS
        backend_start = ScaffoldConfig.BASE_BACKEND_PORT + (model_index * ports_needed)
        frontend_start = ScaffoldConfig.BASE_FRONTEND_PORT + (model_index * ports_needed)
        return backend_start, frontend_start

    def get_app_ports(self, model_index: int, app_number: int) -> PortAssignment:
        backend_base, frontend_base = self.calculate_port_range(model_index)
        offset = (app_number - 1) * ScaffoldConfig.PORTS_PER_APP
        return PortAssignment(backend=backend_base + offset, frontend=frontend_base + offset)

    # ----------------------------- Templates ------------------------------
    def validate_templates(self) -> Dict[str, Any]:
        required = [
            "backend/app.py.template",
            "backend/requirements.txt",
            "backend/Dockerfile.template",
            "frontend/package.json.template",
            "frontend/vite.config.js.template",
            "frontend/src/App.jsx.template",
            "frontend/src/App.css",
            "frontend/index.html.template",
            "frontend/Dockerfile.template",
            "docker-compose.yml.template",
        ]
        missing = []
        for rel in required:
            if not (self.templates_dir / rel).exists():
                missing.append(rel)
        return {"templates_dir": str(self.templates_dir), "missing": missing, "ok": len(missing) == 0}

    # ----------------------------- Preview --------------------------------
    def preview_generation(self, models: List[str]) -> GenerationPreview:
        plans: List[ModelPlan] = []
        for idx, name in enumerate(models):
            backend_start, _ = self.calculate_port_range(idx)
            last_backend_port = backend_start + ScaffoldConfig.APPS_PER_MODEL * ScaffoldConfig.PORTS_PER_APP - 1
            plan = ModelPlan(name=name, index=idx, port_range=(backend_start, last_backend_port))
            for app_num in range(1, ScaffoldConfig.APPS_PER_MODEL + 1):
                ports = self.get_app_ports(idx, app_num)
                plan.apps[app_num] = ports
            plans.append(plan)
        preview = GenerationPreview(
            models=plans,
            total_apps=len(models) * ScaffoldConfig.APPS_PER_MODEL,
            config_summary={
                "apps_per_model": ScaffoldConfig.APPS_PER_MODEL,
                "ports_per_app": ScaffoldConfig.PORTS_PER_APP,
                "base_backend_port": ScaffoldConfig.BASE_BACKEND_PORT,
                "base_frontend_port": ScaffoldConfig.BASE_FRONTEND_PORT,
            },
        )
        return preview

    # ----------------------------- Generation -----------------------------
    def generate(self, models: List[str], dry_run: bool = False) -> GenerationResult:
        preview = self.preview_generation(models)
        output_paths: List[Path] = []
        if dry_run:
            return GenerationResult(preview=preview, generated=False, output_paths=[])

        template_check = self.validate_templates()
        if not template_check["ok"]:
            logger.warning("Proceeding with generation despite missing templates: %s", template_check["missing"])

        for plan in preview.models:
            model_dir = self.models_dir / plan.name.replace('/', '_')
            (model_dir / 'backend').mkdir(parents=True, exist_ok=True)
            (model_dir / 'frontend').mkdir(parents=True, exist_ok=True)
            output_paths.append(model_dir)
            # Minimal placeholder files
            backend_main = model_dir / 'backend' / 'app.py'
            if not backend_main.exists():
                backend_main.write_text(f"# Backend placeholder for {plan.name}\nfrom flask import Flask\napp = Flask(__name__)\n\n@app.get('/')\ndef index():\n    return 'Hello from {plan.name} backend'\n", encoding='utf-8')
            frontend_readme = model_dir / 'frontend' / 'README.md'
            if not frontend_readme.exists():
                frontend_readme.write_text(f"# Frontend placeholder for {plan.name}\n\nPorts allocated start at {plan.port_range[0]} (backend).\n", encoding='utf-8')

        # Write configuration JSONs
        self._write_config_files(models)
        return GenerationResult(preview=preview, generated=True, output_paths=output_paths)

    def _write_config_files(self, models: List[str]):
        colors = self._generate_color_mapping(models)
        ports_config: List[Dict[str, Any]] = []
        for idx, m in enumerate(models):
            for app_num in range(1, ScaffoldConfig.APPS_PER_MODEL + 1):
                p = self.get_app_ports(idx, app_num)
                ports_config.append({
                    "model": m,
                    "model_index": idx,
                    "app_number": app_num,
                    "backend_port": p.backend,
                    "frontend_port": p.frontend,
                })
        ports_path = self.base_path / 'misc' / 'port_config.json'
        ports_path.parent.mkdir(parents=True, exist_ok=True)
        ports_path.write_text(json.dumps(ports_config, indent=2), encoding='utf-8')
        colors_path = self.base_path / 'misc' / 'model_capabilities.json'
        colors_path.write_text(json.dumps({"colors": colors}, indent=2), encoding='utf-8')

    # ----------------------------- Status ---------------------------------
    def status(self) -> Dict[str, Any]:
        return {
            "base_path": str(self.base_path),
            "models_dir": str(self.models_dir),
            "templates_dir": str(self.templates_dir),
            "apps_per_model": ScaffoldConfig.APPS_PER_MODEL,
            "ports_per_app": ScaffoldConfig.PORTS_PER_APP,
        }

# Singleton accessor (lazy)
_scaffold_service: Optional[AppScaffoldingService] = None

def get_app_scaffolding_service() -> AppScaffoldingService:
    global _scaffold_service
    if _scaffold_service is None:
        _scaffold_service = AppScaffoldingService()
    return _scaffold_service
