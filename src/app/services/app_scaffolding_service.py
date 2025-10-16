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
from app.paths import CODE_TEMPLATES_DIR, GENERATED_APPS_DIR, MISC_DIR, PROJECT_ROOT
from typing import Dict, List, Tuple, Optional, Any
import json
import re
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (mirrors values from legacy script where sensible)
# ---------------------------------------------------------------------------

class ScaffoldConfig:
    # Output directory now unified under generated/apps (no writing into legacy top-level models/)
    MODELS_DIR = GENERATED_APPS_DIR  # kept attribute name for minimal downstream change
    LOGS_DIR = "_logs"
    TEMPLATES_DIR = CODE_TEMPLATES_DIR
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
    errors: List[str] = field(default_factory=list)
    missing_templates: List[str] = field(default_factory=list)
    apps_created: int = 0

# ---------------------------------------------------------------------------
# Service implementation
# ---------------------------------------------------------------------------

class AppScaffoldingService:
    def __init__(self, base_path: Optional[Path] = None):
        # Use PROJECT_ROOT instead of os.getcwd() to avoid analyzer directory issues
        self.base_path = Path(base_path) if base_path else PROJECT_ROOT
        # All paths now come from centralized app.paths - use them directly
        self.models_dir = GENERATED_APPS_DIR
        self.templates_dir = CODE_TEMPLATES_DIR
        if not self.templates_dir.exists():
            logger.warning("Code templates directory not found at %s", self.templates_dir)
        self.logs_dir = self.models_dir / ScaffoldConfig.LOGS_DIR
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        # Use centralized port allocation service
        from app.services.port_allocation_service import get_port_allocation_service
        self.port_service = get_port_allocation_service()

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
    def calculate_port_range(self, model_index: int, apps_per_model: Optional[int] = None) -> Tuple[int, int]:
        """Calculate the port range for a model (for preview/display purposes only).
        
        Note: Actual port allocation now uses the centralized port allocation service.
        This method is kept for backward compatibility with preview generation.
        """
        apm = apps_per_model or ScaffoldConfig.APPS_PER_MODEL
        ports_needed = apm * ScaffoldConfig.PORTS_PER_APP + ScaffoldConfig.BUFFER_PORTS
        backend_start = ScaffoldConfig.BASE_BACKEND_PORT + (model_index * ports_needed)
        frontend_start = ScaffoldConfig.BASE_FRONTEND_PORT + (model_index * ports_needed)
        return backend_start, frontend_start

    def get_app_ports(self, model_name: str, model_index: int, app_number: int, apps_per_model: Optional[int] = None) -> PortAssignment:
        """Get or allocate ports for a specific model/app combination.
        
        Now uses the centralized port allocation service for robust port management.
        
        Args:
            model_name: The model name (e.g., "openai_gpt-4")
            model_index: The model index (for legacy calculations)
            app_number: The application number
            apps_per_model: Optional apps per model count
            
        Returns:
            PortAssignment with backend and frontend ports
        """
        try:
            port_pair = self.port_service.get_or_allocate_ports(model_name, app_number)
            return PortAssignment(backend=port_pair.backend, frontend=port_pair.frontend)
        except Exception as e:
            logger.error(f"Failed to allocate ports for {model_name}/app{app_number}: {e}")
            # Emergency fallback to old calculation method
            backend_base, frontend_base = self.calculate_port_range(model_index, apps_per_model=apps_per_model)
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
    def preview_generation(self, models: List[str], apps_per_model: Optional[int] = None) -> GenerationPreview:
        apm = apps_per_model or ScaffoldConfig.APPS_PER_MODEL
        plans: List[ModelPlan] = []
        for idx, name in enumerate(models):
            backend_start, _ = self.calculate_port_range(idx, apps_per_model=apm)
            last_backend_port = backend_start + apm * ScaffoldConfig.PORTS_PER_APP - 1
            plan = ModelPlan(name=name, index=idx, port_range=(backend_start, last_backend_port))
            for app_num in range(1, apm + 1):
                ports = self.get_app_ports(name, idx, app_num, apps_per_model=apm)
                plan.apps[app_num] = ports
            plans.append(plan)
        preview = GenerationPreview(
            models=plans,
            total_apps=len(models) * apm,
            config_summary={
                "apps_per_model": apm,
                "ports_per_app": ScaffoldConfig.PORTS_PER_APP,
                "base_backend_port": ScaffoldConfig.BASE_BACKEND_PORT,
                "base_frontend_port": ScaffoldConfig.BASE_FRONTEND_PORT,
            },
        )
        return preview

    # ----------------------------- Generation -----------------------------
    def generate(self, models: List[str], dry_run: bool = False, apps_per_model: Optional[int] = None, compose: bool = True) -> GenerationResult:
        preview = self.preview_generation(models, apps_per_model=apps_per_model)
        output_paths: List[Path] = []
        if dry_run:
            return GenerationResult(preview=preview, generated=False, output_paths=[])

        template_check = self.validate_templates()
        missing = template_check["missing"]
        if not template_check["ok"]:
            logger.warning("Proceeding with generation despite missing templates: %s", missing)

        errors: List[str] = []
        apps_created = 0

        for plan in preview.models:
            model_dir = self.models_dir / plan.name.replace('/', '_')
            model_dir.mkdir(parents=True, exist_ok=True)
            output_paths.append(model_dir)
            # Per-app structure
            for app_num, ports in plan.apps.items():
                app_dir = model_dir / f"app{app_num}"
                backend_dir = app_dir / 'backend'
                frontend_dir = app_dir / 'frontend'
                backend_dir.mkdir(parents=True, exist_ok=True)
                frontend_dir.mkdir(parents=True, exist_ok=True)

                # Process backend template files
                try:
                    self._materialize_backend(backend_dir, plan.name, app_num, ports)
                    self._materialize_frontend(frontend_dir, plan.name, app_num, ports)
                    # ALWAYS create a per-app docker-compose.yml from template
                    self._write_app_compose(app_dir, plan.name, app_num, ports)
                    apps_created += 1
                except Exception as e:  # noqa: BLE001
                    err = f"Failed generating app {plan.name}#{app_num}: {e}"
                    logger.exception(err)
                    errors.append(err)

            # (Optional legacy aggregated compose generation retained only if explicitly requested)
            if compose and False:  # Disabled: per-user requirement now mandates per-app compose only
                try:
                    self._generate_docker_compose(model_dir, plan)  # pragma: no cover
                except Exception as e:  # noqa: BLE001
                    err = f"Failed aggregated docker-compose for {plan.name}: {e}"
                    logger.exception(err)
                    errors.append(err)

        # Write configuration JSONs
        self._write_config_files(models, apps_per_model=preview.config_summary['apps_per_model'])
        return GenerationResult(preview=preview, generated=True, output_paths=output_paths, errors=errors, missing_templates=missing, apps_created=apps_created)

    def _template_subs(self, content: str, substitutions: Dict[str, Any]) -> str:
        """Perform simple double-brace placeholder replacement with pipe-default support.

        Example: {{model_name}}, {{backend_port}}, {{python_version|3.12}}
        Placeholders with pipe-defaults like {{key|default}} will use the provided value
        or keep the default if no value is provided.
        """
        import re as regex
        
        # Add default values for common placeholders if not provided
        defaults = {
            'python_version': '3.12',
            'node_version': '20',
            'app_file': 'app.py',
            'server_type': 'flask',
        }
        
        # Merge defaults with provided substitutions (provided values take precedence)
        all_subs = {**defaults, **substitutions}
        
        # First pass: Handle pipe-default syntax {{key|default}}
        # Pattern matches {{key|anything_here}}
        for k, v in all_subs.items():
            # Escape the key part, but not the pipe and default part
            # Pattern: {{key|<anything>}}
            pattern = r'\{\{' + regex.escape(k) + r'\|[^\}]+\}\}'
            content = regex.sub(pattern, str(v), content)
        
        # Second pass: Handle standard placeholders {{key}}
        for k, v in all_subs.items():
            # Double-brace style
            content = content.replace(f"{{{{{k}}}}}", str(v))
            # Additionally support single-brace placeholders like {port} (opt-in for known keys only)
            token = f"{{{k}}}"
            if token in content:
                content = content.replace(token, str(v))
        
        return content

    def _read_template(self, rel_path: str) -> Optional[str]:
        path = self.templates_dir / rel_path
        if not path.exists():
            return None
        return path.read_text(encoding='utf-8', errors='ignore')

    def _materialize_backend(self, backend_dir: Path, model_name: str, app_num: int, ports: PortAssignment):
        substitutions = {
            'model_name': model_name,
            'app_number': app_num,
            'backend_port': ports.backend,
            'python_base_image': ScaffoldConfig.PYTHON_BASE_IMAGE,
            'port': ports.backend,
            'model_name_lower': model_name.replace('/', '_').lower(),
            'model_prefix': model_name.replace('/', '_').lower(),
            'python_version': '3.12',  # Default Python version
            'app_file': 'app.py',  # Default app file name
            'server_type': 'flask',  # Default server type
        }
        # app.py
        app_tpl = self._read_template('backend/app.py.template')
        if app_tpl:
            (backend_dir / 'app.py').write_text(self._template_subs(app_tpl, substitutions), encoding='utf-8')
        else:
            # fallback simple file
            (backend_dir / 'app.py').write_text(
                f"from flask import Flask\napp = Flask(__name__)\n\n@app.get('/')\ndef index():\n    return 'Hello from {model_name} app{app_num}'\n", encoding='utf-8')
        # requirements
        req_tpl = self._read_template('backend/requirements.txt')
        if req_tpl:
            (backend_dir / 'requirements.txt').write_text(req_tpl, encoding='utf-8')
        # Dockerfile
        docker_tpl = self._read_template('backend/Dockerfile.template')
        if docker_tpl:
            (backend_dir / 'Dockerfile').write_text(self._template_subs(docker_tpl, substitutions), encoding='utf-8')

    def _materialize_frontend(self, frontend_dir: Path, model_name: str, app_num: int, ports: PortAssignment):
        substitutions = {
            'model_name': model_name,
            'app_number': app_num,
            'backend_port': ports.backend,
            'frontend_port': ports.frontend,
            'model_name_lower': model_name.replace('/', '_').lower(),
            'model_prefix': model_name.replace('/', '_').lower(),
            'port': ports.frontend,
            'node_version': '20',  # Default Node.js version
        }
        pkg_tpl = self._read_template('frontend/package.json.template')
        if pkg_tpl:
            (frontend_dir / 'package.json').write_text(self._template_subs(pkg_tpl, substitutions), encoding='utf-8')
        vite_tpl = self._read_template('frontend/vite.config.js.template')
        if vite_tpl:
            (frontend_dir / 'vite.config.js').write_text(self._template_subs(vite_tpl, substitutions), encoding='utf-8')
        appx_tpl = self._read_template('frontend/src/App.jsx.template')
        if appx_tpl:
            src_dir = frontend_dir / 'src'
            src_dir.mkdir(exist_ok=True)
            (src_dir / 'App.jsx').write_text(self._template_subs(appx_tpl, substitutions), encoding='utf-8')
        app_css = self._read_template('frontend/src/App.css')
        if app_css:
            css_dir = frontend_dir / 'src'
            css_dir.mkdir(exist_ok=True)
            (css_dir / 'App.css').write_text(app_css, encoding='utf-8')
        index_tpl = self._read_template('frontend/index.html.template')
        if index_tpl:
            (frontend_dir / 'index.html').write_text(self._template_subs(index_tpl, substitutions), encoding='utf-8')
        docker_tpl = self._read_template('frontend/Dockerfile.template')
        if docker_tpl:
            (frontend_dir / 'Dockerfile').write_text(self._template_subs(docker_tpl, substitutions), encoding='utf-8')

    def _generate_docker_compose(self, model_dir: Path, plan: ModelPlan):
        compose_tpl = self._read_template('docker-compose.yml.template')
        if not compose_tpl:
            return
        services_entries = []
        for app_num, ports in plan.apps.items():
            svc_name = f"{plan.name.replace('/', '_')}_app{app_num}"
            services_entries.append(
                f"  {svc_name}:%n    build: ./app{app_num}/backend%n    ports:%n      - \"{ports.backend}:{ports.backend}\"%n    environment:%n      - FLASK_ENV=production".replace('%n', '\n')
            )
        compose_content = compose_tpl.replace('{{services}}', '\n'.join(services_entries))
        (model_dir / 'docker-compose.generated.yml').write_text(compose_content, encoding='utf-8')

    def _write_app_compose(self, app_dir: Path, model_name: str, app_num: int, ports: PortAssignment):
        """Generate docker-compose.yml inside an individual app folder using template.

        The template expects (at minimum):
          - {{model_prefix}}
          - {{backend_port}}
          - {{frontend_port}}
        """
        compose_tpl = self._read_template('docker-compose.yml.template')
        if not compose_tpl:
            return  # silently skip; already logged in validate
        substitutions = {
            'model_prefix': model_name.replace('/', '_').lower(),
            'backend_port': ports.backend,
            'frontend_port': ports.frontend,
            'model_name': model_name,
            'app_number': app_num,
        }
        content = self._template_subs(compose_tpl, substitutions)
        (app_dir / 'docker-compose.yml').write_text(content, encoding='utf-8')

    def _write_config_files(self, models: List[str], apps_per_model: int):
        colors = self._generate_color_mapping(models)
        ports_config: List[Dict[str, Any]] = []
        for idx, m in enumerate(models):
            for app_num in range(1, apps_per_model + 1):
                p = self.get_app_ports(m, idx, app_num, apps_per_model=apps_per_model)
                ports_config.append({
                    "model": m,
                    "model_index": idx,
                    "app_number": app_num,
                    "backend_port": p.backend,
                    "frontend_port": p.frontend,
                })
        ports_path = MISC_DIR / 'port_config.json'
        ports_path.parent.mkdir(parents=True, exist_ok=True)
        # Merge with existing if present, keyed by (model, app_number)
        existing_ports: Dict[tuple, Dict[str, Any]] = {}
        if ports_path.exists():
            try:
                data = json.loads(ports_path.read_text(encoding='utf-8'))
                if isinstance(data, list):
                    for item in data:
                        try:
                            key = (item.get('model'), item.get('app_number'))
                            existing_ports[key] = item
                        except Exception:  # noqa: BLE001
                            continue
            except Exception:  # noqa: BLE001
                logger.warning("Failed reading existing port_config.json; rewriting fresh")
        for entry in ports_config:
            key = (entry['model'], entry['app_number'])
            existing_ports[key] = entry  # overwrite/refresh with latest calculation
        merged_ports = list(existing_ports.values())
        merged_ports.sort(key=lambda x: (x.get('model'), x.get('app_number')))
        ports_path.write_text(json.dumps(merged_ports, indent=2), encoding='utf-8')

        # Store colors in models_summary.json or similar (model_capabilities.json is deprecated)
        models_summary_path = MISC_DIR / 'models_summary.json'
        existing_summary: Dict[str, Any] = {}
        if models_summary_path.exists():
            try:
                existing_summary = json.loads(models_summary_path.read_text(encoding='utf-8'))
            except Exception:  # noqa: BLE001
                logger.warning("Failed reading existing models_summary.json; creating fresh")
        
        # Update colors in the summary file
        if 'colors' not in existing_summary:
            existing_summary['colors'] = {}
        existing_summary['colors'].update(colors)  # new mappings override
        models_summary_path.write_text(json.dumps(existing_summary, indent=2), encoding='utf-8')

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
        # Initialize with PROJECT_ROOT to ensure correct paths
        _scaffold_service = AppScaffoldingService(base_path=PROJECT_ROOT)
    return _scaffold_service
