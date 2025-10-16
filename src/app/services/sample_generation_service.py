"""Sample Generation Service
=================================

Integrates the provided sample generation logic (templates, model info,
generation, extraction, and project organization) into the Flask backend.

This module adapts the user's standalone script into a cohesive service
registered with the application's ServiceLocator. It intentionally keeps
state in-memory (results cache) for simplicity; persistence or task queue
integration can be added later.

Key components:
 - Data models (Template, ModelInfo, CodeBlock, GenerationResult)
 - Services: ModelRegistry, TemplateRegistry, PortAllocator, CodeGenerator,
   CodeExtractor, ProjectOrganizer
 - Facade service: SampleGenerationService (public entrypoints)

Environment:
 - Uses OPENROUTER_API_KEY for generation requests (OpenAI-compatible
   chat completions endpoint via OpenRouter).

Thread / Async notes:
 - Generation uses aiohttp (async). Synchronous wrapper helpers are
   provided for Flask routes that call into asyncio.run().
 - For higher throughput or non-blocking behaviour, consider delegating
   to a Celery task or background thread.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple

import aiohttp
from app.paths import (
    CODE_TEMPLATES_DIR,
    APP_TEMPLATES_DIR,
    GENERATED_ROOT,
    GENERATED_LARGE_CONTENT_DIR,
    GENERATED_INDICES_DIR,
    GENERATED_APPS_DIR,
    GENERATED_RAW_API_PAYLOADS_DIR,
    GENERATED_RAW_API_RESPONSES_DIR,
    MODELS_SUMMARY_JSON,
)
import json

try:
    from app.extensions import db
    from app.models import GeneratedCodeResult  # type: ignore
except Exception:  # pragma: no cover - during early import or tests without DB init
    db = None
    GeneratedCodeResult = None  # type: ignore

logger = logging.getLogger(__name__)


# Default models presented when no registry data is available yet.
DEFAULT_MODEL_SLUGS = [
    'mock/basic-coder',
    'openrouter/gpt-4o-mini',
    'openrouter/gpt-4o',
    'anthropic/claude-3.5-sonnet',
    'google/gemini-1.5-flash',
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def to_openrouter_slug(raw: str) -> str:
    """Convert a filesystem directory name to provider/model slug."""
    if not raw:
        return raw
    slug = raw.strip().strip('/')
    if '/' in slug:
        return slug
    if '_' in slug:
        provider, rest = slug.split('_', 1)
        return f"{provider}/{rest}"
    return slug


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class BatchProgress:
    """Tracks progress of batch generation operations."""
    batch_id: str
    total_tasks: int
    completed_tasks: int = 0
    failed_tasks: int = 0
    start_time: float = field(default_factory=time.time)
    task_results: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "in_progress"  # in_progress, completed, failed
    
    @property
    def progress_percent(self) -> float:
        if self.total_tasks == 0:
            return 100.0
        return (self.completed_tasks + self.failed_tasks) / self.total_tasks * 100.0
    
    @property
    def is_complete(self) -> bool:
        return self.completed_tasks + self.failed_tasks >= self.total_tasks
    
    @property
    def elapsed_time(self) -> float:
        return time.time() - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "progress_percent": self.progress_percent,
            "elapsed_time": self.elapsed_time,
            "status": self.status,
            "task_results": self.task_results
        }


@dataclass
class Template:
    app_num: int
    name: str
    content: str
    requirements: List[str]
    file_path: Optional[Path] = None
    complexity_score: float = 0.5
    extra_prompt: Optional[str] = None  # enrichment from misc/app_templates
    template_type: str = "generic"
    display_name: Optional[str] = None


@dataclass
class ModelInfo:
    raw_slug: str
    standardized_name: str
    provider: str
    model_family: str
    variant: str = "standard"
    is_free: bool = False
    capabilities: Set[str] = field(default_factory=set)


@dataclass
class CodeBlock:
    language: str
    code: str
    file_type: Optional[str]
    model_info: ModelInfo
    app_num: int
    message_id: str = ""
    # Port management (from gen.py)
    backend_port: Optional[int] = None
    frontend_port: Optional[int] = None
    detected_backend_ports: List[int] = field(default_factory=list)
    detected_frontend_ports: List[int] = field(default_factory=list)
    # Processing metadata
    selected_for_save: bool = True
    extraction_issues: List[str] = field(default_factory=list)
    port_replacements: Dict[str, str] = field(default_factory=dict)
    # File handling (from gen.py)
    file_index: int = 0
    is_main_component: bool = False
    html_compatibility_score: float = 0.0
    # Computed attributes
    line_count: int = field(init=False)
    checksum: str = field(init=False)
    original_code: str = field(init=False)

    def __post_init__(self):
        self.line_count = len(self.code.splitlines())
        self.checksum = hashlib.md5(self.code.encode()).hexdigest()[:8]
        self.original_code = self.code
        self._detect_ports_in_code()
        
    def _detect_ports_in_code(self):
        """Detect ports in the code content"""
        port_pattern = r'(?:port[\s:=]*|PORT[\s:=]*|listen[\s:]*|LISTEN[\s:]*|localhost:)([0-9]{4,5})'
        matches = re.findall(port_pattern, self.code, re.IGNORECASE)
        
        detected_ports = [int(port) for port in matches if 3000 <= int(port) <= 9999]
        
        # Classify ports as frontend or backend based on common patterns
        for port in detected_ports:
            if 3000 <= port <= 3999 or 5000 <= port <= 5999:
                if port not in self.detected_frontend_ports:
                    self.detected_frontend_ports.append(port)
            elif 8000 <= port <= 8999 or 4000 <= port <= 4999:
                if port not in self.detected_backend_ports:
                    self.detected_backend_ports.append(port)
    
    def get_replaced_code(self) -> str:
        """Get code with port replacements applied"""
        replaced = self.original_code
        for old_port, new_port in self.port_replacements.items():
            replaced = replaced.replace(old_port, new_port)
        return replaced

    @property
    def model(self) -> str:
        """Compatibility property for legacy code"""
        return self.model_info.standardized_name if hasattr(self.model_info, 'standardized_name') else str(self.model_info)


@dataclass
class GenerationResult:
    app_num: int
    app_name: str
    model: str
    content: str
    requirements: List[str]
    success: bool
    timestamp: datetime = field(default_factory=datetime.utcnow)
    extracted_blocks: List[CodeBlock] = field(default_factory=list)
    error_message: Optional[str] = None
    attempts: int = 1
    duration: float = 0.0

    # Extended stats (populated for real API calls; mock path leaves zeros)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    # OpenRouter-specific metadata
    generation_id: Optional[str] = None  # Unique ID for this generation
    model_used: Optional[str] = None  # Actual model that processed the request
    created_timestamp: Optional[int] = None  # Unix timestamp when created
    native_tokens_prompt: Optional[int] = None  # Native tokenization count (prompt)
    native_tokens_completion: Optional[int] = None  # Native tokenization count (completion)
    generation_time_ms: Optional[float] = None  # Time taken to generate (milliseconds)
    provider_name: Optional[str] = None  # Provider that handled the request
    # Cost estimation (optional future use)
    estimated_cost: float = 0.0
    prompt_cost: Optional[float] = None  # Cost for prompt tokens
    completion_cost: Optional[float] = None  # Cost for completion tokens
    # Network / retries timing granularity (first token latency etc.)
    first_attempt_started: Optional[float] = None
    first_token_latency: Optional[float] = None
    finish_reason: Optional[str] = None
    # Request/response snapshots
    request_payload: Dict[str, Any] = field(default_factory=dict)
    request_headers: Dict[str, Any] = field(default_factory=dict)
    response_status: Optional[int] = None
    response_headers: Dict[str, Any] = field(default_factory=dict)
    response_json: Dict[str, Any] = field(default_factory=dict)
    response_text: Optional[str] = None
    # Artifact persistence
    raw_payload_paths: List[str] = field(default_factory=list)
    raw_response_paths: List[str] = field(default_factory=list)
    component_metadata: Dict[str, Any] = field(default_factory=dict)
    metadata_path: Optional[str] = None

    def to_dict(self, include_content: bool = True, meta_only: bool = False) -> Dict[str, Any]:
        data = {
            "app_num": self.app_num,
            "app_name": self.app_name,
            "model": self.model,
            "requirements": self.requirements,
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
            "error_message": self.error_message,
            "attempts": self.attempts,
            "duration": self.duration,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "generation_id": self.generation_id,
            "model_used": self.model_used,
            "created_timestamp": self.created_timestamp,
            "native_tokens_prompt": self.native_tokens_prompt,
            "native_tokens_completion": self.native_tokens_completion,
            "generation_time_ms": self.generation_time_ms,
            "provider_name": self.provider_name,
            "estimated_cost": self.estimated_cost,
            "prompt_cost": self.prompt_cost,
            "completion_cost": self.completion_cost,
            "finish_reason": self.finish_reason,
            "request_payload": self.request_payload,
            "request_headers": self.request_headers,
            "response_status": self.response_status,
            "response_headers": self.response_headers,
            "response_json": self.response_json,
            "response_text": self.response_text,
            "raw_payload_paths": list(self.raw_payload_paths),
            "raw_response_paths": list(self.raw_response_paths),
            "component_metadata": self.component_metadata,
            "metadata_path": self.metadata_path,
            "extracted_blocks": [
                {
                    "language": b.language,
                    "file_type": b.file_type,
                    "line_count": b.line_count,
                    "checksum": b.checksum,
                    "backend_port": b.backend_port,
                    "port_replacements": b.port_replacements,
                } for b in self.extracted_blocks
            ],
        }
        if include_content and not meta_only:
            data["content"] = self.content
        return data


# ============================================================================
# Model Management
# ============================================================================

# Configuration constants
MIN_CODE_BLOCK_SIZE = 20
SKIP_PORT_REPLACEMENT = frozenset([
    "package.json", "package-lock.json", "yarn.lock",
    ".env", ".env.example", ".gitignore", "README.md",
    "tsconfig.json", "jsconfig.json", ".eslintrc.js",
    "babel.config.js", ".prettierrc", "requirements.txt"
])


class FilePatternMatcher:
    """Identifies file types and paths from code content and language (adapted from gen.py)."""
    
    @staticmethod
    def identify_file_type(code: str, language: str) -> Optional[str]:
        """Identify file type from code content and language."""
        if not code.strip():
            return None
            
        # Direct language mapping
        if language.lower() in ['python', 'py']:
            if FilePatternMatcher._is_python_requirements_file(code):
                return "requirements.txt"
            elif 'Flask' in code or 'from flask' in code or 'app = Flask' in code:
                return "backend/app.py"
            elif 'def ' in code or 'class ' in code:
                return "backend/main.py"
            else:
                return "backend/utils.py"
                
        elif language.lower() in ['javascript', 'js']:
            if 'package.json' in code or '"name"' in code and '"version"' in code:
                return "package.json"
            elif 'React' in code or 'import React' in code or 'from "react"' in code:
                return "frontend/src/App.js"
            elif 'express' in code or 'app.listen' in code:
                return "backend/server.js"
            else:
                return "frontend/src/main.js"
                
        elif language.lower() == 'jsx':
            if 'export default' in code and ('function' in code or 'const' in code):
                return "frontend/src/App.jsx"
            else:
                return "frontend/src/Component.jsx"
                
        elif language.lower() == 'html':
            if '<html' in code or '<!DOCTYPE' in code:
                return "frontend/index.html"
            else:
                return "frontend/component.html"
                
        elif language.lower() == 'css':
            return "frontend/src/App.css"
            
        elif language.lower() == 'json':
            if '"name"' in code and '"version"' in code:
                return "package.json"
            else:
                return "config.json"
                
        elif language.lower() in ['dockerfile', 'docker']:
            return "Dockerfile"
            
        elif language.lower() in ['yaml', 'yml']:
            return "docker-compose.yml"
            
        return None
    
    @staticmethod
    def _is_python_requirements_file(code: str) -> bool:
        """Check if code represents a Python requirements file."""
        lines = [line.strip() for line in code.split('\n') if line.strip()]
        if not lines:
            return False
            
        # Check if most lines look like package specifications
        package_lines = 0
        for line in lines:
            if (re.match(r'^[a-zA-Z0-9_-]+([>=<]=?[\d.]+)?$', line) or 
                line.startswith('#') or 
                '==' in line or '>=' in line):
                package_lines += 1
                
        return package_lines >= len(lines) * 0.7  # 70% of lines should be package specs
    
    @staticmethod
    def identify_multiple_files(code: str, language: str, existing_files: Optional[List[str]] = None) -> List[Tuple[str, str, int, bool, float]]:
        """Identify multiple files in a single code block (adapted from gen.py)."""
        existing_files = existing_files or []
        
        if language.lower() == 'jsx':
            return FilePatternMatcher._identify_jsx_files(code, existing_files)
        elif language.lower() in ['python', 'py']:
            return FilePatternMatcher._identify_python_files(code, existing_files)
        elif language.lower() == 'html':
            return FilePatternMatcher._identify_html_files(code, existing_files)
        else:
            # Single file identification
            file_type = FilePatternMatcher.identify_file_type(code, language)
            if file_type:
                return [(file_type, code, 0, True, 0.0)]
            return []
    
    @staticmethod
    def _identify_jsx_files(code: str, existing_files: List[str]) -> List[Tuple[str, str, int, bool, float]]:
        """Identify JSX files and components (enhanced gen.py style)."""
        files = []
        
        # Enhanced patterns for better React component detection
        component_patterns = [
            r'export\s+default\s+function\s+(\w+)',  # export default function ComponentName
            r'function\s+(\w+)\s*\([^)]*\)\s*{[^}]*return\s*\(?<',  # function ComponentName() { return <
            r'const\s+(\w+)\s*=\s*\([^)]*\)\s*=>\s*{[^}]*return\s*\(?<',  # const ComponentName = () => { return <
            r'const\s+(\w+)\s*=\s*\([^)]*\)\s*=>\s*\(?<',  # const ComponentName = () => <
            r'export\s+const\s+(\w+)\s*=',  # export const ComponentName =
        ]
        
        components_found = []
        for pattern in component_patterns:
            matches = re.finditer(pattern, code, re.MULTILINE | re.DOTALL)
            for match in matches:
                comp_name = match.group(1)
                if comp_name and comp_name not in components_found:
                    # Filter out non-component names
                    if comp_name[0].isupper():  # React components start with uppercase
                        components_found.append(comp_name)
        
        # Check for JSX elements to determine if this is actually React code
        jsx_elements = re.findall(r'<[A-Z]\w*|<[a-z]+(?:\s|>|/>)', code)
        has_jsx = len(jsx_elements) > 0
        
        # Check for React imports
        has_react_import = bool(re.search(r'import.*React|from\s+[\'"]react[\'"]', code))
        
        if not has_jsx and not has_react_import:
            # Might not be JSX - treat as regular JavaScript
            return [("frontend/src/main.js", code, 0, True, 0.0)]
        
        # Handle different component scenarios
        if len(components_found) == 1:
            comp_name = components_found[0]
            # Main App component gets special treatment
            if comp_name.lower() in ['app', 'main', 'index']:
                files.append(("frontend/src/App.jsx", code, 0, True, 0.0))
            else:
                files.append((f"frontend/src/{comp_name}.jsx", code, 0, True, 0.0))
                
        elif len(components_found) > 1:
            # Multiple components - split if possible or create main file
            main_component = None
            for comp in components_found:
                if comp.lower() in ['app', 'main', 'index']:
                    main_component = comp
                    break
            
            if main_component:
                # Main component gets App.jsx
                files.append(("frontend/src/App.jsx", code, 0, True, 0.0))
            else:
                # Multiple components - create separate files for each
                for i, comp_name in enumerate(components_found):
                    file_path = f"frontend/src/{comp_name}.jsx" if i > 0 else "frontend/src/App.jsx"
                    files.append((file_path, code, i, i == 0, 0.0))
                    
        else:
            # No clear component names but has JSX - default to App
            files.append(("frontend/src/App.jsx", code, 0, True, 0.0))
        
        # Add package.json if imports are detected
        if has_react_import or 'import' in code:
            package_json_content = FilePatternMatcher._generate_package_json(code)
            files.append(("package.json", package_json_content, len(files), False, 0.0))
        
        # Add index.html for React apps
        if has_jsx:
            index_html_content = FilePatternMatcher._generate_index_html()
            files.append(("frontend/index.html", index_html_content, len(files), False, 0.0))
            
        return files
    
    @staticmethod
    def _generate_package_json(code: str) -> str:
        """Generate package.json for React projects."""
        # Detect dependencies from imports
        dependencies = {
            "react": "^18.2.0",
            "react-dom": "^18.2.0"
        }
        
        # Check for additional dependencies
        if 'react-router' in code:
            dependencies["react-router-dom"] = "^6.8.0"
        if 'axios' in code:
            dependencies["axios"] = "^1.3.0"
        if '@emotion' in code or 'styled' in code:
            dependencies["@emotion/react"] = "^11.10.0"
            dependencies["@emotion/styled"] = "^11.10.0"
        
        package_json = {
            "name": "generated-react-app",
            "version": "1.0.0",
            "type": "module",
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview"
            },
            "dependencies": dependencies,
            "devDependencies": {
                "@vitejs/plugin-react": "^4.0.0",
                "vite": "^4.1.0"
            }
        }
        
        return json.dumps(package_json, indent=2)
    
    @staticmethod
    def _generate_index_html() -> str:
        """Generate index.html for React projects."""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generated React App</title>
</head>
<body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
</body>
</html>'''
    
    @staticmethod
    def _identify_python_files(code: str, existing_files: List[str]) -> List[Tuple[str, str, int, bool, float]]:
        """Identify Python files."""
        if FilePatternMatcher._is_python_requirements_file(code):
            return [("requirements.txt", code, 0, True, 0.0)]
        
        # Check for Flask app
        if 'Flask' in code or 'from flask' in code:
            return [("backend/app.py", code, 0, True, 0.0)]
        
        # Default Python file
        return [("backend/main.py", code, 0, True, 0.0)]
    
    @staticmethod
    def _identify_html_files(code: str, existing_files: List[str]) -> List[Tuple[str, str, int, bool, float]]:
        """Identify HTML files."""
        if '<html' in code or '<!DOCTYPE' in code:
            return [("frontend/index.html", code, 0, True, 0.0)]
        else:
            return [("frontend/template.html", code, 0, True, 0.0)]


class ModelRegistry:
    def __init__(self, models_data: Optional[Dict[str, Any]] = None):
        self.available_models: List[str] = []
        self.model_capabilities: Dict[str, Dict] = {}
        if models_data:
            self._load_models_from_data(models_data)
        self.ensure_minimum_defaults()

    def _load_models_from_data(self, data: Dict[str, Any]):
        if 'models' in data:
            for model_info in data['models']:
                name = model_info.get('name')
                provider = model_info.get('provider')
                if name and provider and '_' in name and name.startswith(f"{provider}_"):
                    model_part = name[len(f"{provider}_"):]
                    openrouter_name = f"{provider}/{model_part}"
                    self.available_models.append(openrouter_name)

    def get_available_models(self) -> List[str]:
        return self.available_models

    def register_model(self, model_slug: str) -> None:
        slug = to_openrouter_slug(model_slug)
        if not slug:
            return
        if slug not in self.available_models:
            self.available_models.append(slug)
            self.available_models.sort()

    def ensure_minimum_defaults(self) -> None:
        if not self.available_models:
            for slug in DEFAULT_MODEL_SLUGS:
                self.register_model(slug)

    def get_model_info(self, model_slug: str) -> ModelInfo:
        clean_slug = model_slug.replace(':free', '')
        is_free = ':free' in model_slug
        if '/' in clean_slug:
            provider, model = clean_slug.split('/', 1)
        else:
            provider, model = 'unknown', clean_slug
        return ModelInfo(
            raw_slug=model_slug,
            standardized_name=clean_slug.replace('/', '_'),
            provider=provider,
            model_family=model.split('-')[0] if model else 'unknown',
            is_free=is_free,
            capabilities=self._detect_capabilities(model_slug)
        )

    def _detect_capabilities(self, model_slug: str) -> Set[str]:
        caps = set()
        m = model_slug.lower()
        if 'gpt-4' in m or 'claude' in m:
            caps.update(['coding', 'reasoning', 'long_context'])
        if 'gemini' in m:
            caps.update(['coding', 'multimodal'])
        if 'deepseek' in m:
            caps.update(['coding', 'reasoning'])
        return caps


# ============================================================================
# Template Management
# ============================================================================


class TemplateRegistry:
    APP_NAME_PATTERN = re.compile(
        r"app_(?P<num>\d+)(?:_(?P<section>backend|frontend))?(?:_(?P<label>.+))?$",
        re.IGNORECASE,
    )
    SPECIAL_LABEL_OVERRIDES = {
        'iot': 'IoT',
        'api': 'API',
        'crm': 'CRM',
        'erp': 'ERP',
        'ui': 'UI',
        'ux': 'UX',
        'devops': 'DevOps',
    }

    def __init__(self):
        self.templates: List[Template] = []
        self._by_name: Dict[str, Template] = {}

    def _sort_key(self, template: Template) -> Tuple[int, int, str]:
        type_rank_map = {'backend': 0, 'frontend': 1, 'generic': 2}
        app_num = template.app_num if template.app_num is not None else 9999
        template_type = (template.template_type or 'generic').lower()
        type_rank = type_rank_map.get(template_type, 3)
        return (app_num, type_rank, template.name.lower())

    def _resort(self) -> None:
        self.templates.sort(key=self._sort_key)

    def _extract_app_metadata(self, name: str) -> Tuple[Optional[int], Optional[str], Optional[str]]:
        match = self.APP_NAME_PATTERN.match(name)
        if match:
            try:
                number = int(match.group('num'))
            except (ValueError, TypeError):
                number = None
            section = (match.group('section') or '').lower() or None
            label = match.group('label') or ''
            return number, section, label
        digits = re.findall(r'\d+', name)
        number = int(digits[0]) if digits else None
        return number, None, name

    def _humanize_label(self, raw_label: str) -> str:
        if not raw_label:
            return ''
        cleaned = raw_label.replace('_', ' ').replace('-', ' ')
        cleaned = re.sub(r'(?<=[a-z0-9])([A-Z])', r' \1', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        parts = cleaned.split(' ')
        humanized: List[str] = []
        for part in parts:
            key = part.lower()
            if not part:
                continue
            if key in self.SPECIAL_LABEL_OVERRIDES:
                humanized.append(self.SPECIAL_LABEL_OVERRIDES[key])
            elif part.isupper():
                humanized.append(part)
            else:
                humanized.append(part.capitalize())
        return ' '.join(humanized) if humanized else cleaned

    def _build_display_name(
        self,
        app_num: Optional[int],
        template_type: Optional[str],
        raw_label: Optional[str],
        fallback_name: str,
    ) -> str:
        human_label = self._humanize_label(raw_label or fallback_name)
        prefix_parts: List[str] = []
        if app_num is not None:
            prefix_parts.append(f"App {app_num:02d}")
        normalized_type = (template_type or '').strip().lower()
        if normalized_type and normalized_type != 'generic':
            prefix_parts.append(normalized_type.capitalize())
        prefix = ' '.join(prefix_parts)
        if prefix and human_label:
            return f"{prefix} – {human_label}"
        if prefix:
            return prefix
        return human_label or fallback_name

    def _apply_metadata(self, template: Template, *, stem: Optional[str] = None) -> None:
        source_name = stem or template.name
        app_num, section, label = self._extract_app_metadata(source_name)
        if app_num is not None:
            template.app_num = app_num
        if section:
            template.template_type = section
        elif not template.template_type:
            template.template_type = 'generic'
        template.display_name = self._build_display_name(
            template.app_num,
            template.template_type,
            label,
            template.name,
        )

    def load_from_dicts(self, data: List[Dict[str, Any]]) -> List[Template]:
        self.templates.clear()
        self._by_name.clear()
        for item in data:
            try:
                app_num_raw = item.get('app_num')
                app_num = int(app_num_raw) if app_num_raw is not None else 0
                t = Template(
                    app_num=app_num,
                    name=item['name'],
                    content=item.get('content', ''),
                    requirements=item.get('requirements', []),
                    template_type=item.get('template_type', item.get('type', 'generic')) or 'generic',
                    display_name=item.get('display_name'),
                )
                if item.get('extra_prompt'):
                    t.extra_prompt = item.get('extra_prompt')
                self._apply_metadata(t)
                t.complexity_score = self._calculate_complexity(t)
                self.templates.append(t)
                self._by_name[t.name] = t
            except KeyError as e:
                logger.warning("Skipping template missing key: %s", e)
        self._resort()
        return self.templates

    def load_from_directory(self, directory: Path) -> List[Template]:
        """Load simple text/markdown templates from a directory.
        Files named *template*.md or .txt become templates; app_num inferred by order.
        """
        self.templates.clear()
        self._by_name.clear()
        if not directory.exists():
            logger.warning("Template directory does not exist: %s", directory)
            return []
        files = sorted([p for p in directory.glob('**/*') if p.is_file() and p.suffix in ('.md', '.txt')])
        for idx, path in enumerate(files, start=1):
            content = path.read_text(encoding='utf-8', errors='ignore')
            meta_num, meta_type, _ = self._extract_app_metadata(path.stem)
            app_num = meta_num if meta_num is not None else idx
            template_type = meta_type or 'generic'
            t = Template(app_num=app_num, name=path.stem, content=content, requirements=[], template_type=template_type)
            t.file_path = path
            self._apply_metadata(t, stem=path.stem)
            t.complexity_score = self._calculate_complexity(t)
            self.templates.append(t)
            self._by_name[t.name] = t
        self._resort()
        return self.templates

    def load_frontend_backend_pairs(self, directory: Path) -> int:
        """Load frontend and backend template pairs following the standalone script pattern.
        
        Looks for files named like: app_N_frontend_name.md and app_N_backend_name.md
        This matches the pattern from the standalone script's AppTemplateLoader.
        """
        if not directory.exists():
            logger.warning("Template directory does not exist: %s", directory)
            return 0
            
        files = list(directory.glob("*.md"))
        if not files:
            logger.warning("No markdown files found in %s", directory)
            return 0
        
        # Group files by app number and type
        app_groups = {}
        for file_path in files:
            match = re.match(r'app_(\d+)_(frontend|backend)_(.+)\.md', file_path.name)
            if match:
                app_num = int(match.group(1))
                file_type = match.group(2)
                app_name = match.group(3)
                
                if app_num not in app_groups:
                    app_groups[app_num] = {
                        'name': app_name,
                        'frontend': None,
                        'backend': None
                    }
                
                app_groups[app_num][file_type] = file_path
        
        loaded_count = 0
        for app_num, files_info in sorted(app_groups.items()):
            app_name = files_info['name'].replace('_', ' ').title()
            requirements = ["Modern application requirements", "Production-ready code", "Clean architecture"]
            
            # Load frontend template if exists
            if files_info['frontend']:
                try:
                    frontend_content = files_info['frontend'].read_text(encoding='utf-8')
                    frontend_template = Template(
                        app_num=app_num,
                        name=f"{app_name}_frontend",
                        content=frontend_content,
                        requirements=requirements + ["React", "TypeScript", "Vite"],
                        template_type="frontend",
                        file_path=files_info['frontend']
                    )
                    frontend_template.display_name = f"App {app_num:02d} Frontend – {app_name}"
                    self.templates.append(frontend_template)
                    self._by_name[frontend_template.name] = frontend_template
                    loaded_count += 1
                    logger.info("Loaded frontend template: %s", frontend_template.name)
                except Exception as e:  # noqa: BLE001
                    logger.warning("Failed to load frontend template %s: %s", files_info['frontend'], e)
            
            # Load backend template if exists
            if files_info['backend']:
                try:
                    backend_content = files_info['backend'].read_text(encoding='utf-8')
                    backend_template = Template(
                        app_num=app_num,
                        name=f"{app_name}_backend",
                        content=backend_content,
                        requirements=requirements + ["Flask", "Python", "SQLAlchemy"],
                        template_type="backend",
                        file_path=files_info['backend']
                    )
                    backend_template.display_name = f"App {app_num:02d} Backend – {app_name}"
                    self.templates.append(backend_template)
                    self._by_name[backend_template.name] = backend_template
                    loaded_count += 1
                    logger.info("Loaded backend template: %s", backend_template.name)
                except Exception as e:  # noqa: BLE001
                    logger.warning("Failed to load backend template %s: %s", files_info['backend'], e)
        
        self._resort()
        logger.info("Loaded %d paired frontend/backend templates from %s", loaded_count, directory)
        return loaded_count

    def enrich_from_app_templates(self, directory: Path) -> int:
        """Enrich existing templates (or add new ones) with additional prompt context.

        Each markdown/txt file in directory is matched by numeric part (app number) or stem name.
        If a template is found, its extra_prompt is set. Otherwise a new template is created.
        Returns the number of templates enriched/added.
        """
        if not directory.exists():
            return 0
        files = sorted([p for p in directory.glob('**/*') if p.is_file() and p.suffix in ('.md', '.txt')])
        if not files:
            return 0
        max_num = max((t.app_num for t in self.templates), default=0)
        enriched = 0
        for path in files:
            try:
                raw = path.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            stem = path.stem
            meta_num, meta_type, label = self._extract_app_metadata(stem)
            target: Optional[Template] = self._by_name.get(stem)
            if not target and meta_num is not None:
                candidates = [t for t in self.templates if t.app_num == meta_num]
                if meta_type:
                    meta_type_lower = meta_type.lower()
                    for cand in candidates:
                        if (cand.template_type or '').lower() == meta_type_lower:
                            target = cand
                            break
                if not target and len(candidates) == 1:
                    target = candidates[0]
            if target:
                target.extra_prompt = raw
                if not target.display_name:
                    self._apply_metadata(target, stem=stem)
                enriched += 1
            else:
                app_num = meta_num if meta_num is not None else max_num + 1
                template_type = meta_type or 'generic'
                t = Template(app_num=app_num, name=stem, content=raw, requirements=[], template_type=template_type)
                t.extra_prompt = raw
                t.file_path = path
                self._apply_metadata(t, stem=stem)
                t.complexity_score = self._calculate_complexity(t)
                self.templates.append(t)
                self._by_name[t.name] = t
                max_num = max(max_num, t.app_num)
                enriched += 1
        self._resort()
        return enriched

    def get(self, identifier: str) -> Optional[Template]:
        for t in self.templates:
            if str(t.app_num) == str(identifier) or t.name == identifier:
                return t
        return None

    def list(self) -> List[Dict[str, Any]]:
        if not self.templates:
            return []
        self._resort()
        items: List[Dict[str, Any]] = []
        for template in self.templates:
            if not template.display_name:
                self._apply_metadata(template)
            items.append(
                {
                    'app_num': template.app_num,
                    'name': template.name,
                    'display_name': template.display_name or template.name,
                    'template_type': template.template_type,
                    'requirements': template.requirements,
                    'complexity_score': template.complexity_score,
                    'has_extra_prompt': bool(template.extra_prompt),
                }
            )
        return items

    def _calculate_complexity(self, template: Template) -> float:
        score = 0.0
        patterns = ['database', 'authentication', 'api', 'websocket', 'queue', 'cache', 'microservice', 'distributed']
        cl = template.content.lower()
        for p in patterns:
            if p in cl:
                score += 0.1
        score += min(0.3, len(template.requirements) * 0.05)
        lines = len(template.content.splitlines())
        score += min(0.2, lines / 1000)
        return min(1.0, score)


# ============================================================================
# Port Allocation
# ============================================================================


class PortAllocator:
    """Enhanced port allocator that uses the centralized port allocation service."""
    
    def __init__(self, base_port: int = 5001, config_file: Optional[Path] = None):
        self.base_port = base_port
        self.allocations: Dict[str, int] = {}
        self.config_file = config_file or Path("misc/port_config.json")
        # Use centralized port allocation service
        from app.services.port_allocation_service import get_port_allocation_service
        self.port_service = get_port_allocation_service(config_file=self.config_file)

    def get_port(self, model_name: str, app_num: int) -> int:
        """Get backend port for model/app combination (legacy method)."""
        backend_port, _ = self.get_ports_for_model_app(model_name, app_num)
        return backend_port or self.base_port

    def get_ports_for_model_app(self, model_name: str, app_num: int) -> Tuple[Optional[int], Optional[int]]:
        """Get backend and frontend ports for model/app combination using centralized service."""
        try:
            port_pair = self.port_service.get_or_allocate_ports(model_name, app_num)
            logger.debug(f"Allocated ports for {model_name}/app{app_num}: "
                        f"backend={port_pair.backend}, frontend={port_pair.frontend}")
            return port_pair.backend, port_pair.frontend
        except Exception as e:
            logger.error(f"Failed to allocate ports for {model_name}/app{app_num}: {e}")
            # Emergency fallback: use old method
            backend_port = self.base_port + (app_num * 2)
            frontend_port = backend_port + 3000
            return backend_port, frontend_port

    def reload_configuration(self):
        """Reload port configuration from service."""
        # Force recreation of service to reload config
        from app.services.port_allocation_service import get_port_allocation_service
        self.port_service = get_port_allocation_service(config_file=self.config_file)

    def reset(self):
        """Reset local allocation cache."""
        self.allocations.clear()


# ============================================================================
# Generation (AI calls)
# ============================================================================


class CodeGenerator:
    def __init__(self, api_key: str, api_url: str = "https://openrouter.ai/api/v1/chat/completions"):
        self.api_key = api_key
        self.api_url = api_url
        self.default_temperature = 0.3
        self.default_max_tokens = 16_000
        self.max_retries = 2
        self.timeout = 300

    def _mock_generation(self, template: Template, model: str) -> GenerationResult:
        """Return a deterministic mock result (used when no API key is configured).

        This allows local testing of extraction / organization without consuming
        model credits or requiring network access. Triggered automatically if
        the API key is blank or model starts with 'mock/'.
        """
        start_time = time.time()
        fake_code = (
            "```python\n"
            f"# Mock backend for {template.name} (model: {model})\n"
            "from flask import Flask, jsonify\n"
            "app = Flask(__name__)\n\n"
            "@app.route('/health')\n"
            "def health():\n"
            f"    return jsonify(status='ok', template='{template.name}', model='{model}')\n\n"
            "if __name__ == '__main__':\n"
            "    app.run(port=5000)\n"
            "```\n"
            "```text\nflask\n```"
        )
        return GenerationResult(
            app_num=template.app_num,
            app_name=template.name,
            model=model,
            content=fake_code,
            requirements=template.requirements or ["Flask"],
            success=True,
            attempts=1,
            duration=time.time() - start_time,
        )

    async def generate(self, template: Template, model: str, temperature: Optional[float] = None,
                       max_tokens: Optional[int] = None, is_frontend: bool = False,
                       overrides: Optional[Dict[str, Any]] = None) -> GenerationResult:
        # Mock path shortcut
        if not self.api_key or model.startswith('mock/'):
            return self._mock_generation(template, model)
        start_time = time.time()
        prompt = self._build_prompt(template, is_frontend)
        overrides = overrides or {}
        # Allow overrides to supply explicit temperature/max_tokens if not provided directly
        if temperature is None and 'temperature' in overrides and overrides['temperature'] is not None:
            try:
                temperature = float(overrides['temperature'])
            except (TypeError, ValueError):
                logger.debug("Ignoring invalid temperature override: %r", overrides['temperature'])
        if max_tokens is None and 'max_tokens' in overrides and overrides['max_tokens'] is not None:
            try:
                max_tokens = int(overrides['max_tokens'])
            except (TypeError, ValueError):
                logger.debug("Ignoring invalid max_tokens override: %r", overrides['max_tokens'])
        if temperature is None:
            temperature = max(0.2, self.default_temperature - (template.complexity_score * 0.1))
        if max_tokens is None:
            max_tokens = min(20_000, int(self.default_max_tokens * (1 + template.complexity_score * 0.5)))
        
        # Improved system prompts with explicit instructions
        if is_frontend:
            system_prompt = """You are an expert frontend developer. Generate production-ready, complete, and working code.

TEMPLATE GUIDANCE (Use as a foundation, not a strict constraint):
The provided template shows a working React application structure with useful patterns:
- ApiService class for API calls (use or adapt as needed)
- Custom hooks like useFetch, useForm (use if helpful, or create your own)
- UI components (LoadingSpinner, ErrorMessage, etc.) - use or create alternatives
- Component organization and styling patterns

You have creative freedom to:
- Design your own component architecture that fits the requirements
- Use different state management approaches (Context, Redux, Zustand, etc.)
- Create custom hooks and utilities that match your needs
- Implement your own styling approach (CSS modules, Tailwind, styled-components, etc.)
- Organize code in the way that makes most sense for this specific application

CODE QUALITY REQUIREMENTS (Non-negotiable):
- Generate COMPLETE files with ALL imports, functions, and code
- NEVER use placeholders like "... rest of the code" or "// TODO" or "// implement this"
- Each code block MUST be a complete, runnable file that works immediately
- Include proper error handling and validation
- Use modern React patterns (hooks, functional components)
- Format code properly with consistent indentation
- Wrap each complete file in ```javascript or ```jsx or ```html or ```css code blocks
- Include file paths as comments at the top: // File: frontend/src/ComponentName.jsx

Generate complete, production-ready code that fulfills the requirements creatively."""
        else:
            system_prompt = """You are an expert backend developer. Generate production-ready, complete, and working code.

TEMPLATE GUIDANCE (Use as a foundation, not a strict constraint):
The provided template shows a working Flask application structure with useful patterns:
- Configuration section with app setup
- Database management with context manager pattern
- Model classes with static methods
- API routes organized by feature
- Error handlers

You have creative freedom to:
- Choose your framework (Flask, FastAPI, Django, etc.) based on requirements
- Design your own database architecture (SQL, NoSQL, ORM, raw queries)
- Implement authentication however you see fit (JWT, sessions, OAuth, etc.)
- Structure your code in the way that makes most sense
- Use different patterns (blueprints, routers, dependency injection, etc.)
- Add or modify dependencies as needed

CODE QUALITY REQUIREMENTS (Non-negotiable):
- Generate COMPLETE files with ALL imports, functions, and code
- NEVER use placeholders like "... rest of the code" or "# TODO" or "# implement this"
- Each code block MUST be a complete, runnable file that works immediately
- Include proper error handling, logging, and validation
- Add docstrings for functions and classes
- Use proper typing/type hints where beneficial
- Format code properly with consistent indentation
- Wrap each complete file in ```python code blocks
- Include file paths as comments at the top: # File: backend/app.py
- Include necessary configuration files (requirements.txt with ALL dependencies)

Generate complete, production-ready code that fulfills the requirements creatively."""
        
        # Convert model slug to OpenRouter format (e.g., x-ai_grok-4-fast -> x-ai/grok-4-fast)
        openrouter_model = to_openrouter_slug(model)
        
        payload = {
            "model": openrouter_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        extra_override_types: Dict[str, Any] = {
            "top_p": float,
            "top_k": int,
            "min_p": float,
            "frequency_penalty": float,
            "presence_penalty": float,
            "repetition_penalty": float,
            "seed": int,
        }
        for key, caster in extra_override_types.items():
            if key not in overrides or overrides[key] in (None, ""):
                continue
            try:
                payload[key] = caster(overrides[key])
            except (TypeError, ValueError):
                logger.debug("Ignoring invalid override %s=%r", key, overrides[key])
        payload_snapshot = copy.deepcopy(payload)
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        request_headers = dict(headers)
        last_response_snapshot: Optional[Dict[str, Any]] = None
        for attempt in range(self.max_retries):
            try:
                logger.info(f"[OPENROUTER] Attempt {attempt+1}/{self.max_retries} - POST to {self.api_url} for {template.name} ({model} -> {openrouter_model})")
                async with aiohttp.ClientSession() as session:
                    async with session.post(self.api_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=self.timeout)) as resp:
                        response_text = await resp.text()
                        response_headers = dict(resp.headers)
                        status = resp.status
                        logger.info(f"[OPENROUTER] Response status: {status}, content_length: {len(response_text)}")
                        try:
                            raw_data = json.loads(response_text)
                        except json.JSONDecodeError:
                            raw_data = {"raw_text": response_text}
                        
                        # Log errors for debugging
                        if status != 200:
                            if isinstance(raw_data, dict):
                                error_detail = raw_data.get('error', {})
                                if isinstance(error_detail, dict):
                                    error_msg = error_detail.get('message', str(error_detail))
                                else:
                                    error_msg = str(error_detail)
                            else:
                                error_msg = str(raw_data)
                            logger.error(f"[OPENROUTER] API Error (status {status}): {error_msg}")
                        if isinstance(raw_data, dict):
                            parsed_data: Dict[str, Any] = raw_data
                        else:
                            parsed_data = {"raw": raw_data}
                        last_response_snapshot = {
                            "status": status,
                            "headers": response_headers,
                            "json": parsed_data,
                            "text": response_text,
                        }
                        if status == 200:
                            choice = (parsed_data.get("choices") or [{}])[0]
                            content = choice.get("message", {}).get("content", "").strip()
                            finish_reason = choice.get("finish_reason") or choice.get("finishReason")
                            usage = parsed_data.get("usage") or {}
                            prompt_tokens = usage.get("prompt_tokens") or usage.get("promptTokens") or 0
                            completion_tokens = usage.get("completion_tokens") or usage.get("completionTokens") or 0
                            total_tokens = usage.get("total_tokens") or usage.get("totalTokens") or (prompt_tokens + completion_tokens)
                            # Extract OpenRouter-specific metadata
                            generation_id = parsed_data.get("id")
                            model_used = parsed_data.get("model")
                            created_timestamp = parsed_data.get("created")
                            native_tokens_prompt = usage.get("native_tokens_prompt")
                            native_tokens_completion = usage.get("native_tokens_completion")
                            # Generation time might be in different fields
                            generation_time_ms = parsed_data.get("generation_time") or parsed_data.get("inference_time")
                            provider_name = parsed_data.get("provider") or parsed_data.get("provider_name")
                            # Cost fields (if provided by OpenRouter)
                            prompt_cost = usage.get("prompt_cost")
                            completion_cost = usage.get("completion_cost")
                            total_cost = usage.get("total_cost")
                            if content:
                                logger.info(f"[OPENROUTER] SUCCESS: Received {len(content)} characters for {template.name}")
                                gr = GenerationResult(
                                    app_num=template.app_num,
                                    app_name=template.name,
                                    model=model,
                                    content=content,
                                    requirements=template.requirements,
                                    success=True,
                                    attempts=attempt + 1,
                                    duration=time.time() - start_time,
                                )
                                gr.prompt_tokens = int(prompt_tokens or 0)
                                gr.completion_tokens = int(completion_tokens or 0)
                                gr.total_tokens = int(total_tokens or 0)
                                gr.generation_id = generation_id
                                gr.model_used = model_used
                                gr.created_timestamp = created_timestamp
                                gr.native_tokens_prompt = native_tokens_prompt
                                gr.native_tokens_completion = native_tokens_completion
                                gr.generation_time_ms = generation_time_ms
                                gr.provider_name = provider_name
                                gr.prompt_cost = prompt_cost
                                gr.completion_cost = completion_cost
                                gr.estimated_cost = total_cost or 0.0
                                gr.finish_reason = finish_reason
                                gr.request_payload = payload_snapshot
                                gr.request_headers = request_headers
                                gr.response_status = status
                                gr.response_headers = response_headers
                                gr.response_json = parsed_data
                                gr.response_text = response_text
                                return gr
                        elif status == 429:
                            await asyncio.sleep(30 * (attempt + 1))
                            continue
            except asyncio.TimeoutError:
                logger.error("Timeout generating %s with %s", template.name, model)
            except Exception as e:  # noqa: BLE001
                logger.error("Error generating %s with %s: %s", template.name, model, e)
            if attempt < self.max_retries - 1:
                await asyncio.sleep(5 * (attempt + 1))
        failure_result = GenerationResult(
            app_num=template.app_num,
            app_name=template.name,
            model=model,
            content="",
            requirements=template.requirements,
            success=False,
            error_message="Generation failed after all retries",
            attempts=self.max_retries,
            duration=time.time() - start_time,
        )
        failure_result.request_payload = payload_snapshot
        failure_result.request_headers = request_headers
        if last_response_snapshot:
            failure_result.response_status = last_response_snapshot.get("status")
            failure_result.response_headers = last_response_snapshot.get("headers", {})
            failure_result.response_json = last_response_snapshot.get("json", {})
            failure_result.response_text = last_response_snapshot.get("text")
        return failure_result

    def _build_prompt(self, template: Template, is_frontend: bool = False) -> str:
        requirements_text = "\n".join(f"- {r}" for r in template.requirements)
        
        # Build comprehensive prompt with balanced guidance
        if is_frontend:
            component_type = "frontend React"
            template_guidance = (
                "\n\n📋 TEMPLATE REFERENCE (Use as inspiration, not strict rules):\n"
                "The template below shows one way to structure a React application.\n"
                "Feel free to use these patterns or create your own approach:\n"
                "- API service layer for backend communication\n"
                "- Custom hooks for common operations (data fetching, forms)\n"
                "- Reusable UI components\n"
                "- Component-based architecture\n\n"
                "You can:\n"
                "- Use the template as-is and extend it\n"
                "- Adapt parts of it to fit your design\n"
                "- Create a completely different structure that better suits the requirements\n"
                "- Use different libraries, patterns, or approaches\n\n"
                "What matters: Complete, working, well-structured code.\n"
            )
        else:
            component_type = "backend API"
            template_guidance = (
                "\n\n📋 TEMPLATE REFERENCE (Use as inspiration, not strict rules):\n"
                "The template below shows one way to structure a backend application.\n"
                "Feel free to use these patterns or create your own approach:\n"
                "- Configuration and setup\n"
                "- Database management\n"
                "- Model/data layer\n"
                "- API routes\n"
                "- Error handling\n\n"
                "You can:\n"
                "- Use the template as-is and extend it\n"
                "- Adapt parts of it to fit your design\n"
                "- Create a completely different structure that better suits the requirements\n"
                "- Use different frameworks, databases, or patterns\n\n"
                "What matters: Complete, working, well-structured code.\n"
            )
        
        # Include extra_prompt with better formatting
        extra_requirements = ""
        if template.extra_prompt:
            extra_requirements = (
                f"\n\n{'='*80}\n"
                f"SPECIFIC REQUIREMENTS FOR THIS APPLICATION:\n"
                f"{'='*80}\n\n"
                f"{template.extra_prompt}\n\n"
                f"Use the above requirements to guide what new features to ADD to the template.\n"
                f"The template provides the foundation - you add the specific functionality.\n"
            )
        
        return (
            f"# Generate Complete {component_type} Implementation\n\n"
            f"## Application: {template.name}\n\n"
            f"## Requirements:\n{requirements_text}\n"
            f"{extra_requirements}"
            f"{template_guidance}"
            f"{'='*80}\n"
            f"TEMPLATE CODE (Reference example):\n"
            f"{'='*80}\n\n"
            f"{template.content}\n\n"
            f"{'='*80}\n"
            f"YOUR TASK:\n"
            f"{'='*80}\n\n"
            f"Generate a complete {component_type} implementation.\n\n"
            f"Requirements:\n"
            f"• Generate COMPLETE, working code (no placeholders or TODOs)\n"
            f"• Make it immediately runnable\n"
            f"• Include proper error handling\n"
            f"• Use the template as reference, but feel free to adapt or redesign\n"
            f"• Ensure all dependencies are included\n\n"
            f"Wrap your code in appropriate code blocks (```python or ```jsx).\n"
        )


# ============================================================================
# Extraction
# ============================================================================


class CodeExtractor:
    """Enhanced code extractor following gen.py patterns."""
    
    def __init__(self, port_allocator: Optional[PortAllocator] = None):
        self.port_allocator = port_allocator or PortAllocator()
        self.file_matcher = FilePatternMatcher()
        self.min_code_size = MIN_CODE_BLOCK_SIZE
        self.batch_app_number: Optional[int] = None
        # More robust pattern for code block extraction
        self.pattern = re.compile(r"```(?:(\w+))?\s*\n(.*?)```", re.DOTALL | re.MULTILINE)

    def set_batch_app_number(self, app_number: int):
        """Set the current batch application number for processing."""
        self.batch_app_number = app_number

    def extract(self, content: str, model_info: ModelInfo, app_num: int) -> List[CodeBlock]:
        """Extract code blocks using gen.py-style logic with multiple file support."""
        blocks: List[CodeBlock] = []
        
        # Set app number for this extraction
        if self.batch_app_number is None:
            self.batch_app_number = app_num
        
        # Use gen.py style extraction with multiple files
        code_blocks_found = []
        for match in self.pattern.finditer(content):
            language = match.group(1) or 'plaintext'
            code = match.group(2).strip()
            
            if len(code) < self.min_code_size:
                continue
                
            code_blocks_found.append((language, code))
        
        # If no code blocks, check if entire content is markdown-like
        if not code_blocks_found and len(content) > self.min_code_size and '```' in content:
            code_blocks_found.append(('markdown', content))
        
        # Track existing file types to avoid duplicates
        existing_files = []
        
        # Process each code block with multiple file detection (gen.py style)
        for language, code in code_blocks_found:
            cleaned_code, issues = self._clean_code_gen_style(code, model_info)
            
            # Try multiple file identification first
            multiple_files = self.file_matcher.identify_multiple_files(cleaned_code, language, existing_files)
            
            if multiple_files:
                # Multiple files detected (gen.py approach)
                for file_type, code_segment, file_index, is_main, html_compatibility in multiple_files:
                    # Get ports for this model/app combination (gen.py style)
                    backend_port, frontend_port = self.port_allocator.get_ports_for_model_app(model_info.standardized_name, app_num)
                    
                    block = CodeBlock(
                        language=language,
                        code=code_segment,
                        file_type=file_type,
                        model_info=model_info,
                        app_num=app_num,
                        message_id=f"msg_{app_num}_{language}_{file_index}",
                        backend_port=backend_port,
                        frontend_port=frontend_port,
                        extraction_issues=issues,
                        file_index=file_index,
                        is_main_component=is_main,
                        html_compatibility_score=html_compatibility
                    )
                    
                    # Apply enhanced port replacement (gen.py style with auto-swap)
                    try:
                        self._apply_enhanced_port_replacement(block)
                    except Exception as e:  # noqa: BLE001
                        logger.debug("Enhanced port replacement skipped due to error: %s", e)
                    
                    blocks.append(block)
                    existing_files.append(file_type)
                    
                    logger.info(f"Extracted {file_type} (index: {file_index}, main: {is_main}) from {model_info.standardized_name}")
            else:
                # Single file identification (fallback to original logic)
                file_type = self._identify_file_type(cleaned_code, language)
                
                if not file_type:
                    logger.warning(f"Could not identify file type for {language} block from {model_info.standardized_name}")
                    continue
                
                backend_port, frontend_port = self.port_allocator.get_ports_for_model_app(model_info.standardized_name, app_num)
                
                block = CodeBlock(
                    language=language, 
                    code=cleaned_code, 
                    file_type=file_type, 
                    model_info=model_info, 
                    app_num=app_num,
                    backend_port=backend_port,
                    frontend_port=frontend_port,
                    extraction_issues=issues
                )
                
                # Apply enhanced port replacement
                try:
                    self._apply_enhanced_port_replacement(block)
                except Exception as e:  # noqa: BLE001
                    logger.debug("Enhanced port replacement skipped due to error: %s", e)
                    
                blocks.append(block)
                existing_files.append(file_type)
        
        # Post-process JSX blocks to determine best main component (gen.py style)
        self._optimize_jsx_main_component(blocks)
        
        # Validate extracted code blocks
        for block in blocks:
            is_valid, validation_issues = CodeValidator.validate_code_block(block)
            if not is_valid:
                logger.warning(
                    f"Validation issues for {block.file_type} from {model_info.standardized_name}: "
                    f"{', '.join(validation_issues)}"
                )
                # Add validation issues to extraction issues
                block.extraction_issues.extend(validation_issues)
        
        return blocks

    # ---------------- Port Replacement ----------------
    def _apply_port_replacement(self, block: CodeBlock) -> None:
        """Replace hard-coded port literals in backend code with allocated backend_port.

        Strategy:
        - Target only code that looks like an app server invocation (Flask, FastAPI, Uvicorn, Node-like listen)
        - Find patterns specifying a port (common dev defaults: 5000, 8000, 3000, 8080)
        - Replace numeric literal with block.backend_port; record mapping in block.port_replacements
        - Avoid replacing numbers that are clearly not ports (e.g., timeouts < 1000, array indices)
        """
        if not block.backend_port or not block.code:
            return
        # Only attempt for languages where we expect inline run statements
        if block.language not in {"python", "javascript", "typescript", "bash", "sh", "shell"}:
            return
        original_code = block.code
        new_code = original_code
        replacements: dict[str, str] = {}
        port_literal_pattern = re.compile(r"(?P<prefix>(?:port\s*=\s*|:\s*|listen\(\s*))(?P<port>(?:5000|8000|3000|8080))\b")
        # Specific framework patterns (Flask/FastAPI/Uvicorn)
        run_call_pattern = re.compile(r"app\.run\((?P<args>[^)]*)\)")
    # (Reserved for future advanced uvicorn pattern handling)
        # Replace generic literals first
        def _generic_sub(m: re.Match) -> str:  # type: ignore[name-defined]
            port = m.group('port')
            if port not in replacements:
                replacements[port] = str(block.backend_port)
            return f"{m.group('prefix')}{block.backend_port}"
        new_code = port_literal_pattern.sub(_generic_sub, new_code)
        # Handle app.run without explicit port but default usage
        # If app.run() present without port kwarg, append one
        def _augment_flask(match: re.Match) -> str:  # type: ignore[name-defined]
            args = match.group('args')
            if 'port=' in args:
                return match.group(0)  # Already handled by generic substitution above
            # Insert port argument before closing
            prefix = 'app.run('
            trimmed = args.strip()
            if trimmed:
                return f"{prefix}{args}, port={block.backend_port})"
            return f"{prefix}port={block.backend_port})"
        new_code = run_call_pattern.sub(_augment_flask, new_code)
        # Uvicorn style may already have been replaced by generic pattern; no special handling beyond that
        # Only commit if changed
        if new_code != original_code:
            block.code = new_code
            for old, new in replacements.items():
                block.port_replacements[old] = new

    def _extract_code_blocks_robust(self, content: str) -> List[Tuple[str, str]]:
        """Extract code blocks with better handling of nested backticks and edge cases."""
        blocks = []
        lines = content.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Look for opening code block
            if line.startswith('```'):
                language = line[3:].strip().lower() if len(line) > 3 else 'text'
                # Remove any additional characters after language
                language = language.split()[0] if language.split() else 'text'
                
                # Collect code until we find a closing ```
                code_lines = []
                i += 1
                
                while i < len(lines):
                    current_line = lines[i]
                    
                    # Check for closing code block (must be on its own line or start of line)
                    if current_line.strip() == '```' or current_line.startswith('```'):
                        # Found end of code block
                        code = '\n'.join(code_lines)
                        if code.strip():  # Only add non-empty blocks
                            blocks.append((language, code))
                        break
                    else:
                        code_lines.append(current_line)
                    i += 1
            i += 1
        
        return blocks

    def _clean_extracted_code(self, code: str) -> str:
        """Clean extracted code to handle common edge cases."""
        # Remove common artifacts
        code = code.strip()
        
        # Remove trailing backticks that might have been captured
        while code.endswith('`'):
            code = code[:-1].strip()
        
        # Handle cases where language identifier got mixed into code
        lines = code.split('\n')
        if lines and lines[0].strip() and not any(char in lines[0] for char in ['=', '{', '(', 'import', 'from', 'def', 'class']):
            # First line might be a language identifier, check if it's suspicious
            first_line = lines[0].strip().lower()
            if first_line in ['python', 'javascript', 'typescript', 'bash', 'sql', 'dockerfile', 'yaml', 'json', 'html', 'css']:
                code = '\n'.join(lines[1:])
        
        return code.strip()

    def _identify_file_type(self, code: str, language: str) -> Optional[str]:
        if language == 'python':
            if 'from flask import' in code or 'app = Flask' in code:
                return 'app.py'
            if 'from fastapi import' in code:
                return 'main.py'
            if 'from django' in code:
                return 'manage.py'
            return 'server.py'
        if language == 'dockerfile':
            return 'Dockerfile'
        if language in ('yaml', 'yml'):
            if 'version:' in code and 'services:' in code:
                return 'docker-compose.yml'
            return 'config.yml'
        if language in ('text', 'txt', 'plaintext'):
            if any(pkg in code for pkg in ['flask', 'django', 'fastapi', 'requests']):
                return 'requirements.txt'
        if language == 'sql':
            return 'schema.sql' if 'CREATE TABLE' in code.upper() else 'queries.sql'
        if language in ('bash', 'sh', 'shell'):
            return 'deploy.sh'
        if language == 'json':
            return 'config.json'
        ext_map = {
            'javascript': 'server.js',
            'typescript': 'server.ts',
            'go': 'main.go',
            'rust': 'main.rs',
            'java': 'Server.java',
            'ruby': 'server.rb',
            'php': 'index.php',
        }
        return ext_map.get(language)


# ============================================================================


    def _clean_code_gen_style(self, code: str, model_info: ModelInfo) -> Tuple[str, List[str]]:
        """Clean extracted code from AI commentary (gen.py style)."""
        issues = []
        cleaned = code
        
        # Remove common AI commentary patterns
        commentary_patterns = [
            r'^(?:Here\'s|Here is|This is|I\'ll|Let me).*?:\s*\n',
            r'^(?:```.*?\n)?(?:# )?(?:File:|Filename:).*?\n',
            r'^\s*(?:Note:|TODO:|FIXME:|Important:).*?\n',
        ]
        
        for pattern in commentary_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE)
        
        if cleaned.count('...') > 2:
            issues.append("Code may contain ellipsis indicating incomplete content")
        
        return cleaned.strip(), issues
    
    def _optimize_jsx_main_component(self, blocks: List[CodeBlock]):
        """Optimize JSX main component selection based on structure (gen.py style)."""
        jsx_blocks = [block for block in blocks if block.language.lower() in ['jsx', 'javascript', 'js']]
        html_blocks = [block for block in blocks if block.language.lower() == 'html']
        
        if not jsx_blocks:
            return
        
        # If there are HTML blocks, find the JSX with best compatibility
        if html_blocks and jsx_blocks:
            best_jsx = None
            best_score = 0.0
            
            for jsx_block in jsx_blocks:
                for html_block in html_blocks:
                    score = self._calculate_jsx_html_compatibility(jsx_block.code, html_block.code)
                    jsx_block.html_compatibility_score = max(jsx_block.html_compatibility_score, score)
                    
                    if score > best_score:
                        best_score = score
                        best_jsx = jsx_block
            
            # Mark the best matching JSX as main component
            if best_jsx:
                for jsx_block in jsx_blocks:
                    jsx_block.is_main_component = (jsx_block == best_jsx)
        else:
            # No HTML blocks - mark first JSX as main
            if jsx_blocks:
                jsx_blocks[0].is_main_component = True
                for jsx_block in jsx_blocks[1:]:
                    jsx_block.is_main_component = False
    
    def _calculate_jsx_html_compatibility(self, jsx_code: str, html_code: str) -> float:
        """Calculate how well JSX code matches with HTML structure (gen.py style)."""
        score = 0.0
        
        # Extract HTML elements from both
        jsx_elements = set(re.findall(r'<(\w+)', jsx_code))
        html_elements = set(re.findall(r'<(\w+)', html_code))
        
        # Calculate element overlap
        if html_elements:
            overlap = len(jsx_elements.intersection(html_elements))
            score += overlap / len(html_elements) * 0.4
        
        # Check for id/class patterns
        html_ids = set(re.findall(r'id="([^"]+)"', html_code))
        jsx_ids = set(re.findall(r'id="([^"]+)"', jsx_code))
        
        if html_ids and jsx_ids:
            id_overlap = len(html_ids.intersection(jsx_ids))
            score += id_overlap / len(html_ids) * 0.3
        
        # Check for React root mounting pattern
        if 'root' in html_code and any(pattern in jsx_code for pattern in ['createRoot', 'render', 'ReactDOM']):
            score += 0.3
        
        return min(score, 1.0)

    def _apply_enhanced_port_replacement(self, block: CodeBlock):
        """Apply enhanced port replacement with auto-swap functionality (gen.py style)."""
        if not block.backend_port and not block.frontend_port:
            return
            
        original_code = block.code
        new_code = original_code
        replacements = {}
        
        # Determine which ports to replace based on file type
        is_backend_file = (
            block.file_type and ('backend' in block.file_type or 
            block.language.lower() in ['python', 'py'] or 
            'app.py' in block.file_type or 'server.py' in block.file_type)
        )
        
        is_frontend_file = (
            block.file_type and ('frontend' in block.file_type or 
            block.language.lower() in ['jsx', 'javascript', 'js', 'html'] or
            'App.jsx' in block.file_type or 'index.html' in block.file_type)
        )
        
        # Backend port replacement patterns (more comprehensive)
        if is_backend_file and block.backend_port:
            backend_patterns = [
                # Flask app.run patterns
                (r'app\.run\(\s*host\s*=\s*[\'"][^\'\"]*[\'"]\s*,\s*port\s*=\s*(\d+)', f'app.run(host="0.0.0.0", port={block.backend_port}'),
                (r'app\.run\(\s*port\s*=\s*(\d+)', f'app.run(port={block.backend_port}'),
                (r'app\.run\(\s*debug\s*=\s*\w+\s*,\s*port\s*=\s*(\d+)', f'app.run(debug=True, port={block.backend_port}'),
                (r'app\.run\(\s*(\d+)\s*\)', f'app.run(port={block.backend_port})'),
                
                # Generic port patterns
                (r'port\s*=\s*(\d+)', f'port={block.backend_port}'),
                (r'PORT\s*=\s*(\d+)', f'PORT={block.backend_port}'),
                (r'listen\(\s*(\d+)', f'listen({block.backend_port}'),
                
                # Common development ports
                (r'\b(5000|8000|3000|4000|8080)\b', str(block.backend_port)),
            ]
            
            for pattern, replacement in backend_patterns:
                if re.search(pattern, new_code):
                    old_matches = re.findall(r'\d+', re.findall(pattern, new_code)[0] if re.findall(pattern, new_code) else '')
                    new_code = re.sub(pattern, replacement, new_code)
                    for old_port in old_matches:
                        if old_port.isdigit():
                            replacements[old_port] = str(block.backend_port)
        
        # Frontend port replacement patterns
        if is_frontend_file and block.frontend_port:
            frontend_patterns = [
                # Vite dev server patterns
                (r'port:\s*(\d+)', f'port: {block.frontend_port}'),
                (r'PORT\s*=\s*(\d+)', f'PORT={block.frontend_port}'),
                
                # API endpoint patterns (pointing to backend)
                (r'http://localhost:(\d+)', f'http://localhost:{block.backend_port or 5000}'),
                (r'https://localhost:(\d+)', f'https://localhost:{block.backend_port or 5000}'),
                (r'fetch\(\s*[\'\"]/api', f'fetch(`http://localhost:{block.backend_port or 5000}/api'),
                
                # Common frontend ports
                (r'\b(3000|5173|8080|4000)\b', str(block.frontend_port)),
            ]
            
            for pattern, replacement in frontend_patterns:
                if re.search(pattern, new_code):
                    old_matches = re.findall(r'\d+', re.findall(pattern, new_code)[0] if re.findall(pattern, new_code) else '')
                    new_code = re.sub(pattern, replacement, new_code)
                    for old_port in old_matches:
                        if old_port.isdigit():
                            replacements[old_port] = str(block.frontend_port)
        
        # Handle package.json dev script ports
        if block.file_type == 'package.json' and block.frontend_port:
            package_patterns = [
                (r'"dev":\s*"vite\s*--port\s*(\d+)"', f'"dev": "vite --port {block.frontend_port}"'),
                (r'"start":\s*".*--port\s*(\d+)"', f'"start": "vite --port {block.frontend_port}"'),
            ]
            
            for pattern, replacement in package_patterns:
                if re.search(pattern, new_code):
                    new_code = re.sub(pattern, replacement, new_code)
        
        # Apply changes if any replacements were made
        if new_code != original_code:
            block.code = new_code
            block.port_replacements.update(replacements)
            logger.info(f"Applied enhanced port replacements to {block.file_type}: {replacements}")


# ==============================================================================
# Code Validation
# ==============================================================================


class CodeValidator:
    """Validates generated code for completeness, correctness, and template adherence."""
    
    @staticmethod
    def validate_python_code(code: str, file_type: str) -> tuple[bool, list[str]]:
        """Validate Python code for syntax and required patterns."""
        issues = []
        
        # Check for placeholders that indicate incomplete code
        placeholder_patterns = [
            r'\.\.\..*rest of.*code',
            r'#\s*TODO',
            r'#\s*FIXME',
            r'#\s*Add.*here',
            r'#\s*Implement.*',
            r'pass\s*#.*implement',
            r'raise\s+NotImplementedError',
        ]
        
        for pattern in placeholder_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append(f"Found placeholder or incomplete code pattern: {pattern}")
        
        # Check for Flask app structure (app.py)
        if 'app.py' in file_type or file_type == 'app.py':
            required_patterns = {
                'Flask import': r'from flask import',
                'CORS': r'from flask_cors import CORS|CORS\(',
                'app initialization': r'app\s*=\s*Flask\(__name__\)',
                'if __name__': r'if __name__\s*==\s*[\'"]__main__[\'"]',
                'app.run': r'app\.run\(',
            }
            
            for name, pattern in required_patterns.items():
                if not re.search(pattern, code):
                    issues.append(f"Missing required pattern for Flask app: {name}")
        
        # Check for proper imports
        if code.strip() and not code.startswith('#'):
            first_lines = code.split('\n')[:30]
            first_non_comment = None
            for line in first_lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('#') and not stripped.startswith('"""') and not stripped.startswith("'''"):
                    first_non_comment = stripped
                    break
            
            if first_non_comment and not any(first_non_comment.startswith(kw) for kw in ['from', 'import', '"""', "'''"]):
                issues.append("Code may be missing imports at the top")
        
        # Basic syntax check (try to compile)
        try:
            compile(code, '<string>', 'exec')
        except SyntaxError as e:
            issues.append(f"Python syntax error: {e}")
        
        return len(issues) == 0, issues
    
    @staticmethod
    def validate_jsx_code(code: str, file_type: str) -> tuple[bool, list[str]]:
        """Validate JSX/React code for required patterns."""
        issues = []
        
        # Check for placeholders
        placeholder_patterns = [
            r'\.\.\..*rest of.*code',
            r'//\s*TODO',
            r'//\s*FIXME',
            r'//\s*Add.*here',
            r'//\s*Implement.*',
        ]
        
        for pattern in placeholder_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append(f"Found placeholder or incomplete code pattern: {pattern}")
        
        # Check for React patterns (App.jsx or similar)
        if 'App.jsx' in file_type or file_type == 'App.jsx':
            required_patterns = {
                'React import': r'import React',
                'ReactDOM import': r'import ReactDOM',
                'App component': r'(function App|const App|class App)',
                'ReactDOM.createRoot': r'ReactDOM\.createRoot',
                'export': r'export default',
            }
            
            for name, pattern in required_patterns.items():
                if not re.search(pattern, code):
                    issues.append(f"Missing required pattern for React app: {name}")
        
        # Check for balanced brackets
        open_braces = code.count('{')
        close_braces = code.count('}')
        if abs(open_braces - close_braces) > 2:  # Allow small variance for code blocks
            issues.append(f"Unbalanced braces: {open_braces} open, {close_braces} close")
        
        return len(issues) == 0, issues
    
    @staticmethod
    def validate_requirements_txt(code: str) -> tuple[bool, list[str]]:
        """Validate requirements.txt has expected dependencies."""
        issues = []
        
        # Check for required base packages
        required_packages = ['flask', 'flask-cors']
        
        code_lower = code.lower()
        for package in required_packages:
            if package not in code_lower:
                issues.append(f"Missing required package: {package}")
        
        # Check for valid format
        lines = code.strip().split('\n')
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Should match package==version or package>=version
            if not re.match(r'^[a-zA-Z0-9\-_\.]+[>=<]=[\d\.]+', line):
                # Allow simple package names too
                if not re.match(r'^[a-zA-Z0-9\-_\.]+$', line):
                    issues.append(f"Line {i} has invalid format: {line}")
        
        return len(issues) == 0, issues
    
    @staticmethod
    def validate_code_block(block: CodeBlock) -> tuple[bool, list[str]]:
        """Validate a code block based on its type."""
        if not block.code or len(block.code.strip()) < 10:
            return False, ["Code block is too short or empty"]
        
        if block.language.lower() in ['python', 'py']:
            return CodeValidator.validate_python_code(block.code, block.file_type or '')
        elif block.language.lower() in ['jsx', 'javascript', 'js']:
            return CodeValidator.validate_jsx_code(block.code, block.file_type or '')
        elif block.file_type == 'requirements.txt':
            return CodeValidator.validate_requirements_txt(block.code)
        
        # For other file types, just check for placeholders
        placeholder_patterns = [
            r'\.\.\..*rest of.*code',
            r'(//|#)\s*(TODO|FIXME|Add.*here|Implement)',
        ]
        
        issues = []
        for pattern in placeholder_patterns:
            if re.search(pattern, block.code, re.IGNORECASE):
                issues.append(f"Found placeholder pattern: {pattern}")
        
        return len(issues) == 0, issues


# ==============================================================================
# Project Organization
# ==============================================================================


class ProjectOrganizer:
    def __init__(self, output_dir: Path = Path('generated'), code_templates_dir: Path | None = None):
        # Root (GENERATED_ROOT). Apps live under apps/ subfolder for clarity.
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.apps_root = self.output_dir / 'apps'
        self.apps_root.mkdir(parents=True, exist_ok=True)
        # Directory containing skeleton backend/frontend/docker-compose templates
        self.code_templates_dir = code_templates_dir or Path('src') / 'misc' / 'code_templates'
        self._scaffold_cache: Set[str] = set()  # model_app key cache to avoid redundant copies
        # Use centralized port allocation service
        from app.services.port_allocation_service import get_port_allocation_service
        self.port_service = get_port_allocation_service()

    # ---------------- Internal helpers ----------------
    def _scaffold_if_needed(self, model_name: str, app_num: int) -> Path:
        """Create complete base backend/frontend/docker-compose structure.

        Copies ALL files from misc/code_templates into the target app directory. 
        Files ending with .template have the suffix stripped. This ensures every
        generated app has the complete scaffolding including:
        - docker-compose.yml
        - Dockerfiles (backend/frontend)
        - .dockerignore files
        - .env.example files
        - Package configuration files
        
        Existing files are not overwritten (idempotent), but missing files are added.
        """
        safe_model = re.sub(r'[^\w\-_.]', '_', model_name)
        app_dir = self.apps_root / safe_model / f"app{app_num}"
        app_dir.mkdir(parents=True, exist_ok=True)
        key = f"{safe_model}_app{app_num}"
        
        # Always scaffold - don't skip if in cache (to ensure completeness)
        # Only skip if we're sure ALL files exist
        should_scaffold = key not in self._scaffold_cache
        
        if not self.code_templates_dir.exists():
            logger.warning(f"Code templates directory not found: {self.code_templates_dir}")
            self._scaffold_cache.add(key)
            return app_dir
        
        try:
            # Get ports for this model/app
            backend_port, frontend_port = self._compute_ports(model_name, app_num)
            model_prefix = re.sub(r'[^\w\-]', '_', model_name.lower())
            
            # Comprehensive substitutions map
            substitutions = {
                'model_name': model_name,
                'model_name_lower': model_prefix,
                'backend_port': str(backend_port),
                'frontend_port': str(frontend_port),
                'model_prefix': model_prefix,
                'python_version': '3.12',
                'node_version': '20',
                'app_file': 'app.py',
                'server_type': 'flask',
            }
            
            files_copied = 0
            files_skipped = 0
            files_failed = 0
            
            # Recursively copy all files from code_templates
            for src in self.code_templates_dir.rglob('*'):
                if not src.is_file():
                    continue
                
                rel = src.relative_to(self.code_templates_dir)
                
                # Drop .template suffix
                target_name = rel.name[:-9] if rel.name.endswith('.template') else rel.name
                target_path = app_dir / rel.parent / target_name
                
                # Check if file already exists
                if target_path.exists():
                    files_skipped += 1
                    continue
                
                # Ensure target directory exists
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                try:
                    # Read template content
                    content = src.read_text(encoding='utf-8', errors='ignore')
                    
                    # Determine context-sensitive port
                    contextual_port = str(backend_port) if 'backend' in rel.parts else str(frontend_port)
                    substitutions['port'] = contextual_port
                    
                    # Replace placeholders - handle pipe-default syntax {{key|default}}
                    import re as regex
                    for key, value in substitutions.items():
                        # Pattern matches {{key|<anything>}}
                        pattern = r'\{\{' + regex.escape(key) + r'\|[^\}]+\}\}'
                        content = regex.sub(pattern, str(value), content)
                    
                    # Replace standard placeholders {{key}}
                    for key, value in substitutions.items():
                        content = content.replace(f"{{{{{key}}}}}", value)
                    
                    # Write file
                    target_path.write_text(content, encoding='utf-8')
                    files_copied += 1
                    logger.debug(f"Scaffolded: {rel} -> {target_path.relative_to(self.apps_root)}")
                    
                except Exception as e:  # noqa: BLE001
                    files_failed += 1
                    logger.warning(f"Failed copying scaffold file {src}: {e}")
            
            # Log summary
            if should_scaffold:
                logger.info(
                    f"Scaffolding complete for {safe_model}/app{app_num}: "
                    f"{files_copied} copied, {files_skipped} existed, {files_failed} failed"
                )
            
        except Exception as e:  # noqa: BLE001
            logger.error(f"Scaffold process encountered an error for {safe_model}/app{app_num}: {e}")
        
        self._scaffold_cache.add(key)
        return app_dir

    def _compute_ports(self, model_name: str, app_num: int) -> tuple[int, int]:
        """Compute ports for a model/app combination using centralized allocation.
        
        Args:
            model_name: The model name for port allocation
            app_num: The application number
            
        Returns:
            Tuple of (backend_port, frontend_port)
        """
        port_pair = self.port_service.get_or_allocate_ports(model_name, app_num)
        return port_pair.backend, port_pair.frontend

    def save_block(self, block: CodeBlock, model_name: str, force_overwrite: bool = True, 
                   create_backup: bool = False, generate_frontend: bool = True, 
                   generate_backend: bool = True) -> bool:
        """Save a code block to the filesystem, replacing existing files.
        
        This method follows the file replacement pattern from the standalone script,
        always replacing existing files rather than generating new ones.
        
        Args:
            block: The code block to save
            model_name: The model name for path construction
            force_overwrite: Whether to overwrite existing files (default True for replacement mode)
            create_backup: Whether to create backup files before replacement (disabled by default)
            generate_frontend: Whether to generate frontend files
            generate_backend: Whether to generate backend files
        
        Returns:
            True if the file was successfully saved/replaced, False otherwise
        """
        try:
            app_dir = self._scaffold_if_needed(model_name, block.app_num)
            # Check if this file should be generated based on frontend/backend settings
            is_backend_file = block.file_type in {'app.py', 'server.py', 'main.py', 'requirements.txt', 'Dockerfile'}
            is_frontend_file = block.file_type in {'package.json', 'App.jsx', 'index.html', 'App.css', 'vite.config.js'}
            
            # Skip files that shouldn't be generated based on user settings
            if is_backend_file and not generate_backend:
                logger.info(f"Skipping backend file {block.file_type} (backend generation disabled)")
                return True
            elif is_frontend_file and not generate_frontend:
                logger.info(f"Skipping frontend file {block.file_type} (frontend generation disabled)")
                return True
            
            # Attempt to place known file types into backend/ by convention
            target_root = app_dir
            if is_backend_file:
                backend_dir = app_dir / 'backend'
                backend_dir.mkdir(parents=True, exist_ok=True)
                target_root = backend_dir
            elif is_frontend_file:
                frontend_dir = app_dir / 'frontend'
                frontend_dir.mkdir(parents=True, exist_ok=True)
                target_root = frontend_dir
            elif block.file_type == 'docker-compose.yml':
                # Place at app root
                target_root = app_dir
            
            if block.file_type:
                file_path = target_root / block.file_type
            else:
                ext = '.txt' if block.language == 'text' else f'.{block.language}'
                file_path = target_root / f"code_{block.checksum}{ext}"
            
            # Get the final code with any port replacements applied
            final_code = self._get_replaced_code(block)
            
            # Create backup before replacing (if enabled)
            if file_path.exists() and create_backup:
                backup_path = file_path.parent / f"{file_path.name}.bak"
                if not backup_path.exists():  # Only create backup if one doesn't exist
                    try:
                        shutil.copy2(file_path, backup_path)
                        logger.info(f"Created backup: {backup_path}")
                    except Exception as copy_err:  # noqa: BLE001
                        logger.debug("Unable to create backup for %s: %s", file_path, copy_err)
            
            # Clean up legacy generated_ artifacts from previous behaviour
            legacy_path = file_path.parent / f"generated_{file_path.name}"
            if legacy_path.exists():
                try:
                    legacy_path.unlink()
                    logger.debug(f"Cleaned up legacy file: {legacy_path}")
                except Exception as cleanup_err:  # noqa: BLE001
                    logger.debug("Unable to remove legacy generated file %s: %s", legacy_path, cleanup_err)
            
            # Replace the file content (always overwrite in replacement mode)
            file_path.write_text(final_code, encoding='utf-8')
            
            # Log port replacements if any were applied
            if hasattr(block, 'port_replacements') and block.port_replacements:
                logger.info(f"Applied port replacements to {file_path.name}: {block.port_replacements}")
            
            logger.info(f"Successfully replaced file: {file_path}")
            return True
            
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to replace file for code block: %s", e)
            return False
    
    def save_code_blocks_gen_style(self, blocks: List[CodeBlock], model_name: str, create_backup: bool = False) -> int:
        """Save multiple code blocks following gen.py patterns with enhanced file organization."""
        saved_count = 0
        
        # Group blocks by app_num for organized processing
        blocks_by_app = {}
        for block in blocks:
            app_num = block.app_num
            if app_num not in blocks_by_app:
                blocks_by_app[app_num] = []
            blocks_by_app[app_num].append(block)
        
        # Process each app
        for app_num, app_blocks in blocks_by_app.items():
            logger.info(f"Organizing {len(app_blocks)} code blocks for app {app_num}")
            
            # Create app directory structure
            app_dir = self._scaffold_if_needed(model_name, app_num)
            
            # Organize by file type and handle multiple files
            for block in app_blocks:
                try:
                    success = self._save_block_enhanced(block, model_name, app_dir, create_backup)
                    if success:
                        saved_count += 1
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Failed to save block {block.file_type}: {e}")
                    
            # Create project index for this app
            self._create_project_index_gen_style(app_blocks, model_name, app_num, app_dir)
            
            # Auto-create React project structure if JSX files are detected
            jsx_blocks = [b for b in app_blocks if b.language.lower() in ['jsx', 'javascript', 'js'] and 'jsx' in (b.file_type or '')]
            if jsx_blocks:
                # Get ports for React project setup
                first_jsx = jsx_blocks[0]
                if first_jsx.backend_port and first_jsx.frontend_port:
                    self.create_react_project_structure(model_name, app_num, first_jsx.frontend_port, first_jsx.backend_port)
                    logger.info(f"Auto-created React project structure for {len(jsx_blocks)} JSX components")
        
        return saved_count
    
    def _save_block_enhanced(self, block: CodeBlock, model_name: str, app_dir: Path, create_backup: bool) -> bool:
        """Save a single block with enhanced gen.py-style organization."""
        if not block.file_type:
            logger.warning("Block has no file_type, skipping")
            return False
            
        # Handle file indexing for multiple files of same type
        file_path = self._determine_file_path_gen_style(block, app_dir)
        
        # Get final code with port replacements
        final_code = block.get_replaced_code() if hasattr(block, 'get_replaced_code') else block.code
        
        # Add metadata comments for JSX files
        if block.language.lower() in ['jsx', 'js', 'javascript'] and hasattr(block, 'is_main_component'):
            final_code = self._add_jsx_metadata_comments(final_code, block)
        
        # Create backup if needed
        if file_path.exists() and create_backup:
            backup_path = file_path.parent / f"{file_path.name}.bak"
            if not backup_path.exists():
                try:
                    shutil.copy2(file_path, backup_path)
                    logger.debug(f"Created backup: {backup_path}")
                except Exception as e:  # noqa: BLE001
                    logger.debug(f"Backup creation failed: {e}")
        
        # Write the file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(final_code, encoding='utf-8')
        
        logger.info(f"Saved {file_path} (main_component: {getattr(block, 'is_main_component', False)})")
        return True
    
    def _determine_file_path_gen_style(self, block: CodeBlock, app_dir: Path) -> Path:
        """Determine file path following gen.py patterns with indexing support."""
        base_file_type = block.file_type
        
        # Guard against None file_type
        if not base_file_type:
            base_file_type = f"unknown_{block.language}"
        
        # Handle indexed files (e.g., multiple JSX components)
        if hasattr(block, 'file_index') and block.file_index > 0:
            # Extract directory and filename parts
            if '/' in base_file_type:
                dir_part, file_part = base_file_type.rsplit('/', 1)
                name_part, ext_part = file_part.rsplit('.', 1) if '.' in file_part else (file_part, '')
                indexed_name = f"{name_part}_{block.file_index:02d}"
                indexed_file_type = f"{dir_part}/{indexed_name}.{ext_part}" if ext_part else f"{dir_part}/{indexed_name}"
            else:
                name_part, ext_part = base_file_type.rsplit('.', 1) if '.' in base_file_type else (base_file_type, '')
                indexed_name = f"{name_part}_{block.file_index:02d}"
                indexed_file_type = f"{indexed_name}.{ext_part}" if ext_part else indexed_name
        else:
            indexed_file_type = base_file_type
        
        return app_dir / indexed_file_type
    
    def _add_jsx_metadata_comments(self, code: str, block: CodeBlock) -> str:
        """Add metadata comments to JSX files (gen.py style)."""
        comments = []
        
        if hasattr(block, 'is_main_component') and block.is_main_component:
            comments.append("// Main component - primary app entry point")
        
        if hasattr(block, 'html_compatibility_score') and block.html_compatibility_score > 0:
            comments.append(f"// HTML compatibility score: {block.html_compatibility_score:.2f}")
        
        if hasattr(block, 'extraction_issues') and block.extraction_issues:
            for issue in block.extraction_issues[:2]:  # Limit to 2 issues
                comments.append(f"// Note: {issue}")
        
        if comments:
            header = "\n".join(comments) + "\n\n"
            return header + code
        
        return code
    
    def _create_project_index_gen_style(self, blocks: List[CodeBlock], model_name: str, app_num: int, app_dir: Path):
        """Create a project index file similar to gen.py."""
        try:
            index_content = f"# Project Index - {model_name} App {app_num}\n\n"
            index_content += f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            # Group blocks by type
            frontend_blocks = [b for b in blocks if b.file_type and ('frontend' in b.file_type or b.language.lower() in ['jsx', 'html', 'css', 'js'])]
            backend_blocks = [b for b in blocks if b.file_type and ('backend' in b.file_type or b.language.lower() in ['python', 'py'])]
            other_blocks = [b for b in blocks if b not in frontend_blocks and b not in backend_blocks]
            
            if frontend_blocks:
                index_content += "## Frontend Files\n\n"
                for block in frontend_blocks:
                    main_marker = " (main)" if getattr(block, 'is_main_component', False) else ""
                    index_content += f"- `{block.file_type}`{main_marker} - {block.language} ({block.line_count} lines)\n"
                index_content += "\n"
            
            if backend_blocks:
                index_content += "## Backend Files\n\n" 
                for block in backend_blocks:
                    index_content += f"- `{block.file_type}` - {block.language} ({block.line_count} lines)\n"
                index_content += "\n"
            
            if other_blocks:
                index_content += "## Other Files\n\n"
                for block in other_blocks:
                    index_content += f"- `{block.file_type or 'unknown'}` - {block.language} ({block.line_count} lines)\n"
            
            # Write index file
            index_file = app_dir / "PROJECT_INDEX.md"
            index_file.write_text(index_content, encoding='utf-8')
            logger.info(f"Created project index: {index_file}")
            
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to create project index: {e}")

    def create_react_project_structure(self, model_name: str, app_num: int, frontend_port: int, backend_port: int):
        """Create a complete React project structure with proper configuration."""
        try:
            app_dir = self._scaffold_if_needed(model_name, app_num)
            frontend_dir = app_dir / "frontend"
            frontend_dir.mkdir(parents=True, exist_ok=True)
            
            # Create src directory
            src_dir = frontend_dir / "src"
            src_dir.mkdir(parents=True, exist_ok=True)
            
            # Create vite.config.js
            vite_config = f'''import {{ defineConfig }} from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({{
  plugins: [react()],
  server: {{
    port: {frontend_port},
    proxy: {{
      '/api': {{
        target: 'http://localhost:{backend_port}',
        changeOrigin: true,
      }}
    }}
  }}
}})
'''
            (frontend_dir / "vite.config.js").write_text(vite_config, encoding='utf-8')
            
            # Create main.jsx entry point
            main_jsx = '''import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './App.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
'''
            (src_dir / "main.jsx").write_text(main_jsx, encoding='utf-8')
            
            # Create basic App.css if it doesn't exist
            if not (src_dir / "App.css").exists():
                app_css = '''#root {
  max-width: 1280px;
  margin: 0 auto;
  padding: 2rem;
  text-align: center;
}

.card {
  padding: 2em;
}

.read-the-docs {
  color: #888;
}
'''
                (src_dir / "App.css").write_text(app_css, encoding='utf-8')
            
            logger.info(f"Created React project structure for {model_name}/app{app_num}")
            
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to create React project structure: {e}")

    def _get_replaced_code(self, block: CodeBlock) -> str:
        """Get code with port replacements applied, similar to the standalone script pattern.
        
        Args:
            block: The code block with potential port replacements
            
        Returns:
            The code with any necessary port replacements applied
        """
        if not hasattr(block, 'port_replacements') or not block.port_replacements:
            return block.code
        
        # Apply port replacements (this follows the pattern from your script)
        modified_code = block.code
        
        # Apply any stored port replacements
        for old_port, new_port in block.port_replacements.items():
            # Use word boundary replacement to avoid partial matches
            import re
            pattern = r'\b' + re.escape(old_port) + r'\b'
            modified_code = re.sub(pattern, new_port, modified_code)
        
        return modified_code

    def save_markdown(self, result: GenerationResult) -> bool:
        try:
            safe_model = re.sub(r'[^\w\-_.]', '_', result.model)
            md_dir = self.output_dir / 'markdown' / safe_model
            md_dir.mkdir(parents=True, exist_ok=True)
            safe_name = re.sub(r'[^\w\-_]', '_', result.app_name)
            filename = f"app_{result.app_num}_{safe_name}.md"
            (md_dir / filename).write_text(result.content, encoding='utf-8')
            return True
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to save markdown: %s", e)
            return False

    def structure(self) -> Dict[str, Any]:
        structure: Dict[str, Any] = {}
        for model_dir in (self.apps_root.iterdir() if self.apps_root.exists() else []):
            if model_dir.is_dir():
                apps: Dict[str, List[str]] = {}
                for app_dir in model_dir.iterdir():
                    if app_dir.is_dir():
                        files = [f.name for f in app_dir.iterdir() if f.is_file()]
                        apps[app_dir.name] = files
                structure[model_dir.name] = apps
        return structure


# ============================================================================
# Facade Service
# ============================================================================


class SampleGenerationService:
    """Facade that wires together registries, generator, extractor, and organizer."""

    def __init__(self):
        self.model_registry = ModelRegistry()
        self.template_registry = TemplateRegistry()
        # Initialize port allocator with config file path
        config_file = Path("misc/port_config.json")
        self.port_allocator = PortAllocator(config_file=config_file)
        # Centralized directories
        self.app_templates_dir = APP_TEMPLATES_DIR
        # API key loaded lazily; supports runtime rotation
        api_key = os.getenv('OPENROUTER_API_KEY', '')
        logger.info(f"SampleGenerationService: API key loaded, length={len(api_key)}")
        self.generator = CodeGenerator(api_key=api_key)
        self.extractor = CodeExtractor(self.port_allocator)
        # Use unified generated root (apps will live under generated/apps via organizer logic)
        self.organizer = ProjectOrganizer(
            GENERATED_ROOT,
            code_templates_dir=CODE_TEMPLATES_DIR
        )
        # Feature flag: optionally persist full raw markdown output
        # Default OFF to reduce clutter / disk usage; enable with SAMPLE_GEN_SAVE_MARKDOWN=1
        self._save_markdown = os.getenv('SAMPLE_GEN_SAVE_MARKDOWN', '0').lower() in {'1', 'true', 'yes', 'on'}
        # In-memory results store: id -> GenerationResult
        self._results: Dict[str, GenerationResult] = {}
        self._last_api_key_check = 0.0
        # Concurrency controls
        self._in_flight_generations = set()
        self._max_concurrent_generations = 5
        # Batch progress tracking
        self._batch_operations = {}  # batch_id -> BatchProgress
        # Content size limits (in characters)
        self._max_content_size = 100_000  # 100KB
        self._filesystem_storage_dir = GENERATED_LARGE_CONTENT_DIR
        self._filesystem_storage_dir.mkdir(parents=True, exist_ok=True)
        # Manifest / index file
        self._manifest_path = GENERATED_INDICES_DIR / 'generation_manifest.json'
        GENERATED_INDICES_DIR.mkdir(parents=True, exist_ok=True)
        if not self._manifest_path.exists():
            try:
                self._manifest_path.write_text('[]', encoding='utf-8')
            except Exception:  # noqa: BLE001
                pass
        try:
            if MODELS_SUMMARY_JSON.exists():
                with MODELS_SUMMARY_JSON.open('r', encoding='utf-8') as f:
                    models_data = json.load(f)
                self.model_registry = ModelRegistry(models_data=models_data)
                logger.info(
                    "Loaded %d models from %s",
                    len(self.model_registry.get_available_models()),
                    MODELS_SUMMARY_JSON,
                )
        except Exception as e:
            logger.warning("Could not auto-load models summary: %s", e)
        finally:
            self._bootstrap_models_from_generated_apps()
            
        # Try to load paired frontend/backend templates first (standalone script pattern)
        try:
            logger.info(f"Attempting to load paired templates from: {self.app_templates_dir}")
            paired_count = self.template_registry.load_frontend_backend_pairs(self.app_templates_dir)
            if paired_count:
                logger.info("Loaded %d paired frontend/backend templates", paired_count)
            else:
                logger.warning("No paired templates were loaded from %s", self.app_templates_dir)
        except Exception as e:  # noqa: BLE001
            logger.warning("Paired template loading failed: %s", e)
            
        # Then try enrichment from app_templates (if any base templates exist)
        try:
            enriched_count = self.template_registry.enrich_from_app_templates(self.app_templates_dir)
            if enriched_count:
                logger.info("Template enrichment applied: %d additional contexts", enriched_count)
        except Exception as e:  # noqa: BLE001
            logger.warning("Template enrichment failed: %s", e)
            
        # If no templates loaded yet (fresh start), attempt generic load from app_templates dir as fallback
        if not self.template_registry.templates:
            try:
                base_loaded = self.template_registry.load_from_directory(self.app_templates_dir)
                if base_loaded:
                    logger.info("Loaded %d base templates from %s", len(base_loaded), self.app_templates_dir)
            except Exception as e:  # noqa: BLE001
                logger.warning("Initial template directory load failed: %s", e)

    def _refresh_api_key_if_needed(self):
        """Refresh API key every 60s to pick up .env changes without restart."""
        now = time.time()
        if now - self._last_api_key_check > 60:
            new_key = os.getenv('OPENROUTER_API_KEY', '')
            if new_key != self.generator.api_key:
                self.generator.api_key = new_key
            self._last_api_key_check = now

    def _bootstrap_models_from_generated_apps(self) -> None:
        """Ensure registry includes models discovered on disk."""
        discovered: Set[str] = set()
        try:
            if GENERATED_APPS_DIR.exists():
                for model_dir in GENERATED_APPS_DIR.iterdir():
                    if not model_dir.is_dir():
                        continue
                    slug = to_openrouter_slug(model_dir.name)
                    if not slug:
                        continue
                    discovered.add(slug)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to bootstrap models from %s: %s", GENERATED_APPS_DIR, exc)
        finally:
            for slug in sorted(discovered):
                self.model_registry.register_model(slug)
            self.model_registry.ensure_minimum_defaults()

    # ---------------- Templates ----------------
    def list_templates(self) -> List[Dict[str, Any]]:
        return self.template_registry.list()

    def load_templates_from_directory(self, directory: str | Path) -> Dict[str, Any]:
        path = Path(directory)
        templates = self.template_registry.load_from_directory(path)
        return {"count": len(templates), "directory": str(path)}

    def upsert_templates(self, templates: List[Dict[str, Any]]) -> Dict[str, Any]:
        loaded = self.template_registry.load_from_dicts(templates)
        return {"count": len(loaded)}

    # ---------------- Generation ----------------
    def _compute_content_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content for duplicate detection."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _find_duplicate_by_content(self, content_hash: str) -> Optional[str]:
        """Find existing result with matching content hash."""
        # Check in-memory results first
        for rid, result in self._results.items():
            if result.success and result.content:
                if self._compute_content_hash(result.content) == content_hash:
                    logger.info("Found in-memory duplicate for hash %s: %s", content_hash[:8], rid)
                    return rid
        
        # Check database if available
        if GeneratedCodeResult and db:
            try:
                # Look for results with matching content hash in error_message field
                # (we'll store hash there as a secondary index)
                recs = GeneratedCodeResult.query.filter(
                    GeneratedCodeResult.error_message.like(f"%CONTENT_HASH:{content_hash}%")
                ).all()
                if recs:
                    logger.info("Found DB duplicate for hash %s: %s", content_hash[:8], recs[0].result_id)
                    return recs[0].result_id
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to check for duplicates in DB: %s", e)
        
        return None

    def _should_store_to_filesystem(self, content: str) -> bool:
        """Check if content exceeds size limit and should be stored to filesystem."""
        return len(content) > self._max_content_size

    def _store_large_content(self, result_id: str, content: str) -> str:
        """Store large content to filesystem and return file reference."""
        file_path = self._filesystem_storage_dir / f"{result_id}.md"
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return str(file_path)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to store large content for %s: %s", result_id, e)
            # Fallback: truncate content
            return content[:self._max_content_size] + "\n\n[CONTENT TRUNCATED - Original too large]"

    def _retrieve_large_content(self, file_reference: str) -> str:
        """Retrieve large content from filesystem."""
        try:
            with open(file_reference, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to retrieve large content from %s: %s", file_reference, e)
            return f"[CONTENT UNAVAILABLE - File error: {e}]"

    def _truncate_content_for_db(self, content: str) -> str:
        """Truncate content for database storage if needed."""
        if len(content) <= self._max_content_size:
            return content
        return content[:self._max_content_size] + "\n\n[CONTENT TRUNCATED - Full content stored separately]"

    def _persist_generation_artifacts(
        self,
        *,
        result: GenerationResult,
        result_id: str,
        component_type: str,
        generation_options: Optional[Dict[str, Any]] = None,
        template: Optional[Template] = None,
    ) -> None:
        """Write request/response snapshots and metadata to the generated folder."""
        try:
            safe_model = re.sub(r"[^\w\-_.]", "_", result.model or "unknown_model")
            safe_component = re.sub(r"[^\w\-_]", "_", component_type or "combined")
            safe_result_id = re.sub(r"[^\w\-_]", "_", result_id)
            app_label = f"app{result.app_num}"
            timestamp_tag = result.timestamp.strftime("%Y%m%dT%H%M%S")
            base_name = f"{timestamp_tag}_{safe_component}_{safe_result_id}"

            payload_path: Optional[Path] = None
            if result.request_payload or result.request_headers:
                payload_dir = GENERATED_RAW_API_PAYLOADS_DIR / safe_model / app_label
                payload_dir.mkdir(parents=True, exist_ok=True)
                payload_path = payload_dir / f"{base_name}_payload.json"
                payload_content = {
                    "headers": result.request_headers,
                    "payload": result.request_payload,
                }
                payload_path.write_text(json.dumps(payload_content, indent=2, sort_keys=True), encoding="utf-8")
                result.raw_payload_paths.append(str(payload_path))

            response_path: Optional[Path] = None
            if result.response_status is not None or result.response_headers or result.response_json:
                response_dir = GENERATED_RAW_API_RESPONSES_DIR / safe_model / app_label
                response_dir.mkdir(parents=True, exist_ok=True)
                response_path = response_dir / f"{base_name}_response.json"
                response_content = {
                    "status": result.response_status,
                    "headers": result.response_headers,
                    "body": result.response_json,
                    "text": result.response_text,
                }
                response_path.write_text(json.dumps(response_content, indent=2, sort_keys=True), encoding="utf-8")
                result.raw_response_paths.append(str(response_path))

            metadata_dir = GENERATED_INDICES_DIR / "runs" / safe_model / app_label
            metadata_dir.mkdir(parents=True, exist_ok=True)
            metadata_path = metadata_dir / f"{base_name}_metadata.json"

            metadata: Dict[str, Any] = {
                "result_id": result_id,
                "component": component_type,
                "timestamp": result.timestamp.isoformat(),
                "app_num": result.app_num,
                "app_name": result.app_name,
                "model": result.model,
                "success": result.success,
                "duration": result.duration,
                "attempts": result.attempts,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "total_tokens": result.total_tokens,
                "finish_reason": result.finish_reason,
                "error_message": result.error_message,
                "requirements": result.requirements,
                "payload_path": str(payload_path) if payload_path else None,
                "response_path": str(response_path) if response_path else None,
                "generation_options": generation_options or {},
                "request_headers": result.request_headers,
                "response_status": result.response_status,
                "response_headers": result.response_headers,
                "extracted_blocks": [
                    {
                        "language": block.language,
                        "file_type": block.file_type,
                        "checksum": block.checksum,
                        "line_count": block.line_count,
                    }
                    for block in result.extracted_blocks
                ],
            }
            if template:
                metadata["template"] = {
                    "name": template.name,
                    "type": template.template_type,
                    "app_num": template.app_num,
                }

            metadata["metadata_path"] = str(metadata_path)
            if component_type not in {"frontend", "backend"}:
                linked_components: Dict[str, Any] = {}
                for key, component_meta in result.component_metadata.items():
                    if key == component_type or not isinstance(component_meta, dict):
                        continue
                    linked_entry: Dict[str, Any] = {}
                    if component_meta.get("metadata_path"):
                        linked_entry["metadata_path"] = component_meta.get("metadata_path")
                    if component_meta.get("payload_path"):
                        linked_entry["payload_path"] = component_meta.get("payload_path")
                    if component_meta.get("response_path"):
                        linked_entry["response_path"] = component_meta.get("response_path")
                    if linked_entry:
                        linked_components[key] = linked_entry
                if linked_components:
                    metadata["linked_components"] = linked_components

            metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
            result.component_metadata[component_type] = metadata
            if not result.metadata_path:
                result.metadata_path = str(metadata_path)
        except Exception as err:  # noqa: BLE001
            logger.warning("Failed to persist raw IO artifacts for %s (%s): %s", result_id, component_type, err)

    def get_generation_status(self) -> dict:
        """Get information about current generation activity."""
        return {
            "in_flight_count": len(self._in_flight_generations),
            "max_concurrent": self._max_concurrent_generations,
            "available_slots": self._max_concurrent_generations - len(self._in_flight_generations),
            "in_flight_keys": list(self._in_flight_generations)
        }

    def get_summary_metrics(self) -> Dict[str, Any]:
        """Return aggregate metrics for dashboards and status cards."""
        total_results = len(self._results)
        if GeneratedCodeResult and db:
            try:
                db_total = GeneratedCodeResult.query.count()
                total_results = max(total_results, db_total)
            except Exception:  # noqa: BLE001
                pass

        total_templates = len(self.template_registry.templates)
        total_models = len(self.model_registry.get_available_models())
        active_tasks = len(self._in_flight_generations)
        system_healthy = bool(total_templates) and bool(total_models)

        return {
            "total_results": total_results,
            "total_templates": total_templates,
            "total_models": total_models,
            "active_tasks": active_tasks,
            "system_healthy": system_healthy,
            "available_templates": total_templates,
            "connected_models": total_models,
        }

    async def generate_frontend_backend_async(self, template_id: str, model: str, temperature: Optional[float] = None,
                                             max_tokens: Optional[int] = None, create_backup: bool = False,
                                             generate_frontend: bool = True, generate_backend: bool = True,
                                             generation_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate frontend and backend separately like the standalone script.
        
        Makes two separate API calls - one for frontend and one for backend - then combines results.
        This matches the pattern from the standalone script's AppTemplateLoader approach.
        """
        logger.info(f"Starting dual generation: template_id={template_id}, model={model}")
        logger.info(f"Component flags: frontend={generate_frontend}, backend={generate_backend}")
        
        results = {
            "frontend_result": None,
            "backend_result": None,
            "frontend_success": False,
            "backend_success": False,
            "total_requests": 0,
            "successful_requests": 0,
            "error_message": None
        }
        
        # Snapshot overrides for logging / reuse
        options = dict(generation_options or {})
        if options:
            logger.info("Model override parameters: %s", options)

        # Find templates
        app_num = int(template_id) if template_id.isdigit() else None
        frontend_template = None
        backend_template = None
        
        if app_num:
            for template in self.template_registry.templates:
                if template.app_num == app_num:
                    if template.template_type and 'frontend' in template.template_type.lower():
                        frontend_template = template
                    elif template.template_type and 'backend' in template.template_type.lower():
                        backend_template = template
        
        # Generate frontend if requested and template exists
        if generate_frontend and frontend_template:
            try:
                results["total_requests"] += 1
                logger.info(f"Making frontend API call for {frontend_template.name}")
                
                frontend_result_id, frontend_result = await self._generate_single_component_async(
                    frontend_template, model, temperature, max_tokens, create_backup, is_frontend=True,
                    generation_options=options
                )
                
                results["frontend_result"] = {
                    "result_id": frontend_result_id,
                    "success": frontend_result.success,
                    "content_length": len(frontend_result.content) if frontend_result.content else 0,
                    "extracted_blocks": len(frontend_result.extracted_blocks),
                    "metadata_path": frontend_result.metadata_path,
                    "raw_payload_paths": list(frontend_result.raw_payload_paths),
                    "raw_response_paths": list(frontend_result.raw_response_paths),
                }
                results["frontend_success"] = frontend_result.success
                if frontend_result.success:
                    results["successful_requests"] += 1
                    
            except Exception as e:
                logger.error(f"Frontend generation failed: {e}")
                results["frontend_result"] = {"error": str(e)}
        
        # Generate backend if requested and template exists
        if generate_backend and backend_template:
            try:
                results["total_requests"] += 1
                logger.info(f"Making backend API call for {backend_template.name}")
                
                backend_result_id, backend_result = await self._generate_single_component_async(
                    backend_template, model, temperature, max_tokens, create_backup, is_frontend=False,
                    generation_options=options
                )
                
                results["backend_result"] = {
                    "result_id": backend_result_id,
                    "success": backend_result.success,
                    "content_length": len(backend_result.content) if backend_result.content else 0,
                    "extracted_blocks": len(backend_result.extracted_blocks),
                    "metadata_path": backend_result.metadata_path,
                    "raw_payload_paths": list(backend_result.raw_payload_paths),
                    "raw_response_paths": list(backend_result.raw_response_paths),
                }
                results["backend_success"] = backend_result.success
                if backend_result.success:
                    results["successful_requests"] += 1
                    
            except Exception as e:
                logger.error(f"Backend generation failed: {e}")
                results["backend_result"] = {"error": str(e)}
        
        # Set overall success
        if results["total_requests"] == 0:
            results["error_message"] = "No templates found or no components selected"
        elif results["successful_requests"] == 0:
            results["error_message"] = "All generation requests failed"
        
        logger.info(f"Dual generation complete: {results['successful_requests']}/{results['total_requests']} successful")
        return results

    async def _generate_single_component_async(self, template: Template, model: str, 
                                             temperature: Optional[float] = None, max_tokens: Optional[int] = None,
                                             create_backup: bool = False, is_frontend: bool = False,
                                             generation_options: Optional[Dict[str, Any]] = None) -> Tuple[str, GenerationResult]:
        """Generate a single component (frontend or backend) using the specified template.
        
        This is the core generation method that makes a single API call for one component type.
        """
        # Check concurrency limits
        if len(self._in_flight_generations) >= self._max_concurrent_generations:
            raise ValueError(f"Too many concurrent generations (limit: {self._max_concurrent_generations})")
        
        component_type = "frontend" if is_frontend else "backend"
        generation_key = f"{template.app_num}_{model}_{component_type}_{int(time.time() * 1000)}"
        self._in_flight_generations.add(generation_key)
        
        try:
            self._refresh_api_key_if_needed()
            
            logger.info(f"Generating {component_type} for {template.name} with model {model}")
            
            # Generate the content using the appropriate template and prompt
            result = await self.generator.generate(
                template,
                model,
                temperature,
                max_tokens,
                is_frontend,
                generation_options,
            )
            model_info = self.model_registry.get_model_info(model)
            
            if result.success and result.content:
                # Extract code blocks from the generated content
                blocks = self.extractor.extract(result.content, model_info, result.app_num)
                result.extracted_blocks = blocks
                
                # Save/replace files based on component type and create_backup flag
                for block in blocks:
                    # Only save blocks that match the component type we're generating
                    should_save = False
                    if is_frontend:
                        # Frontend files: jsx, js, css, html, package.json, etc.
                        should_save = block.file_type in ['App.jsx', 'index.html', 'App.css', 'package.json', 'vite.config.js'] or \
                                    block.language.lower() in ['jsx', 'javascript', 'css', 'html']
                    else:
                        # Backend files: python, requirements.txt, etc.
                        should_save = block.file_type in ['app.py', 'server.py', 'main.py', 'requirements.txt', 'Dockerfile'] or \
                                    block.language.lower() in ['python', 'dockerfile']
                    
                    if should_save:
                        self.organizer.save_block(
                            block, model, force_overwrite=True, create_backup=create_backup,
                            generate_frontend=is_frontend, generate_backend=not is_frontend
                        )
                
                # Save raw markdown if enabled
                if self._save_markdown:
                    self.organizer.save_markdown(result)
            
            # Generate result ID and store
            result_id = f"{model.replace('/', '_')}_{template.app_num}_{component_type}_{int(time.time())}"
            self._results[result_id] = result

            options_snapshot: Dict[str, Any] = dict(generation_options or {})
            if temperature is not None:
                options_snapshot.setdefault("temperature", temperature)
            if max_tokens is not None:
                options_snapshot.setdefault("max_tokens", max_tokens)

            self._persist_generation_artifacts(
                result=result,
                result_id=result_id,
                component_type=component_type,
                generation_options=options_snapshot,
                template=template,
            )

            logger.info(f"Completed {component_type} generation: {result_id} (success: {result.success})")
            return result_id, result
            
        finally:
            self._in_flight_generations.discard(generation_key)

    async def generate_async(self, template_id: str, model: str, temperature: Optional[float] = None, 
                            max_tokens: Optional[int] = None, create_backup: bool = False, 
                            generate_frontend: bool = True, generate_backend: bool = True) -> Tuple[str, GenerationResult]:
        logger.info(f"[GEN_ASYNC] START: tid={template_id}, model={model}, has_api_key={bool(self.generator.api_key)}")
        
        # Check concurrency limits
        if len(self._in_flight_generations) >= self._max_concurrent_generations:
            raise ValueError(f"Too many concurrent generations (limit: {self._max_concurrent_generations})")
        
        generation_key = f"{template_id}_{model}_{int(time.time() * 1000)}"
        self._in_flight_generations.add(generation_key)
        
        try:
            self._refresh_api_key_if_needed()
            
            # Debug logging
            logger.info(f"Generation requested: template_id={template_id}, model={model}")
            logger.info(f"Component flags: generate_frontend={generate_frontend}, generate_backend={generate_backend}, create_backup={create_backup}")
            
            # Find template(s) for generation - look for frontend and backend versions
            frontend_template = None
            backend_template = None
            
            # Try to find specific frontend and backend templates based on the template_id
            app_num = int(template_id) if template_id.isdigit() else None
            
            logger.info(f"Looking for templates: app_num={app_num}, total templates={len(self.template_registry.templates)}")
            
            if app_num:
                # Look for app-specific frontend and backend templates
                for template in self.template_registry.templates:
                    logger.info(f"Checking template: app_num={template.app_num}, name={template.name}, type={template.template_type}")
                    if template.app_num == app_num:
                        if template.template_type and 'frontend' in template.template_type.lower():
                            frontend_template = template
                            logger.info(f"Found frontend template: {template.name}")
                        elif template.template_type and 'backend' in template.template_type.lower():
                            backend_template = template
                            logger.info(f"Found backend template: {template.name}")
                        elif template.template_type == 'generic' or not template.template_type:
                            # Use generic template as fallback for both if specific ones not found
                            if not frontend_template:
                                frontend_template = template
                                logger.info(f"Using generic template as frontend fallback: {template.name}")
                            if not backend_template:
                                backend_template = template
                                logger.info(f"Using generic template as backend fallback: {template.name}")
            else:
                # Look for template by name
                template = self.template_registry.get(template_id)
                if template:
                    frontend_template = template
                    backend_template = template
            
            # Create templates if not found (legacy compatibility)
            if not frontend_template and not backend_template:
                try:
                    new_app_num = max([t.app_num for t in self.template_registry.templates] or [0]) + 1
                except Exception:  # noqa: BLE001
                    new_app_num = 1
                
                # Create frontend template
                frontend_template = Template(
                    app_num=new_app_num,
                    name=f"{template_id}_frontend",
                    content=f"Auto frontend template for {template_id}.",
                    requirements=["react", "vite"],
                    template_type="frontend"
                )
                
                # Create backend template
                backend_template = Template(
                    app_num=new_app_num,
                    name=f"{template_id}_backend", 
                    content=f"Auto backend template for {template_id}.",
                    requirements=["flask"],
                    template_type="backend"
                )
                
                # Add to registry
                self.template_registry.templates.extend([frontend_template, backend_template])
                self.template_registry._by_name[frontend_template.name] = frontend_template
                self.template_registry._by_name[backend_template.name] = backend_template
                self.template_registry._resort()
            
            # Generate frontend and/or backend based on flags (gen.py approach with separate extractions)
            all_extracted_blocks = []
            frontend_content = ""
            backend_content = ""
            frontend_success = False
            backend_success = False
            frontend_result: Optional[GenerationResult] = None
            backend_result: Optional[GenerationResult] = None
            
            # Set extractor app number
            if app_num:
                self.extractor.set_batch_app_number(app_num)
            
            if generate_frontend and frontend_template:
                logger.info(f"Generating frontend content using template: {frontend_template.name}")
                frontend_result = await self.generator.generate(frontend_template, model, temperature, max_tokens, is_frontend=True)
                logger.info(f"Frontend generation result: success={frontend_result.success if frontend_result else 'None'}")

                if frontend_result:
                    frontend_options = {
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                    frontend_result_id = f"{model.replace('/', '_')}_{frontend_template.app_num}_frontend_{int(time.time() * 1000)}"
                    self._persist_generation_artifacts(
                        result=frontend_result,
                        result_id=frontend_result_id,
                        component_type="frontend",
                        generation_options=frontend_options,
                        template=frontend_template,
                    )
                
                if frontend_result and frontend_result.success:
                    frontend_success = True
                    frontend_content = frontend_result.content
                    
                    # Extract code blocks from frontend result (gen.py style)
                    model_info = ModelInfo(
                        raw_slug=model,
                        standardized_name=model,
                        provider=model.split('_')[0] if '_' in model else model.split('/')[0] if '/' in model else 'unknown',
                        model_family=model.split('_')[0] if '_' in model else model,
                    )
                    
                    frontend_blocks = self.extractor.extract(frontend_result.content, model_info, app_num or 1)
                    all_extracted_blocks.extend(frontend_blocks)
                    logger.info(f"Extracted {len(frontend_blocks)} frontend code blocks")
            elif generate_frontend and not frontend_template:
                logger.warning(f"Frontend generation requested but no frontend template found for app {template_id}")
            
            if generate_backend and backend_template:
                logger.info(f"Generating backend content using template: {backend_template.name}")
                backend_result = await self.generator.generate(backend_template, model, temperature, max_tokens, is_frontend=False)
                logger.info(f"Backend generation result: success={backend_result.success if backend_result else 'None'}")

                if backend_result:
                    backend_options = {
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                    backend_result_id = f"{model.replace('/', '_')}_{backend_template.app_num}_backend_{int(time.time() * 1000)}"
                    self._persist_generation_artifacts(
                        result=backend_result,
                        result_id=backend_result_id,
                        component_type="backend",
                        generation_options=backend_options,
                        template=backend_template,
                    )
                
                if backend_result and backend_result.success:
                    backend_success = True
                    backend_content = backend_result.content
                    
                    # Extract code blocks from backend result (gen.py style)
                    model_info = ModelInfo(
                        raw_slug=model,
                        standardized_name=model,
                        provider=model.split('_')[0] if '_' in model else model.split('/')[0] if '/' in model else 'unknown',
                        model_family=model.split('_')[0] if '_' in model else model,
                    )
                    
                    backend_blocks = self.extractor.extract(backend_result.content, model_info, app_num or 1)
                    all_extracted_blocks.extend(backend_blocks)
                    logger.info(f"Extracted {len(backend_blocks)} backend code blocks")
            elif generate_backend and not backend_template:
                logger.warning(f"Backend generation requested but no backend template found for app {template_id}")
            
            # Create result with separate frontend/backend content and combined blocks (gen.py style)
            base_template = backend_template or frontend_template
            success = frontend_success or backend_success
            
            if base_template:
                # Combine content for display purposes but keep blocks separate
                combined_content = ""
                if frontend_content:
                    combined_content += f"# Frontend Implementation\n\n{frontend_content}\n\n"
                if backend_content:
                    combined_content += f"# Backend Implementation\n\n{backend_content}"
                
                result = GenerationResult(
                    app_num=base_template.app_num,
                    app_name=base_template.name,
                    model=model,
                    content=combined_content or "No content generated",
                    requirements=base_template.requirements,
                    success=success,
                    extracted_blocks=all_extracted_blocks,  # Contains both frontend and backend blocks
                    error_message="Partial failure" if (frontend_success != backend_success) and (generate_frontend and generate_backend) else None
                )
                if frontend_result:
                    frontend_meta = frontend_result.component_metadata.get("frontend")
                    if frontend_meta:
                        result.component_metadata["frontend"] = frontend_meta
                    result.raw_payload_paths.extend(frontend_result.raw_payload_paths)
                    result.raw_response_paths.extend(frontend_result.raw_response_paths)
                if backend_result:
                    backend_meta = backend_result.component_metadata.get("backend")
                    if backend_meta:
                        result.component_metadata["backend"] = backend_meta
                    result.raw_payload_paths.extend(backend_result.raw_payload_paths)
                    result.raw_response_paths.extend(backend_result.raw_response_paths)
            else:
                # No templates found at all
                result = GenerationResult(
                    app_num=int(template_id) if template_id.isdigit() else 1,
                    app_name=template_id,
                    model=model,
                    content="", 
                    requirements=[],
                        success=False,
                        error_message="No templates found for generation"
                    )
            
            model_info = self.model_registry.get_model_info(model)
            
            # Check for duplicate content before processing
            if result.success and result.content:
                content_hash = self._compute_content_hash(result.content)
                existing_id = self._find_duplicate_by_content(content_hash)
                if existing_id:
                    logger.info("Duplicate content detected, returning existing result: %s", existing_id)
                    existing_result = self.get_result(existing_id, include_content=True)
                    if existing_result:
                        # Return existing result with same structure
                        return existing_id, self._results.get(existing_id) or result
                
                # Use already extracted blocks instead of re-extracting
                if not all_extracted_blocks:
                    # Fallback: extract from combined content if no blocks were extracted earlier
                    logger.warning("No blocks extracted during component generation, extracting from combined content")
                    blocks = self.extractor.extract(result.content, model_info, result.app_num)
                    result.extracted_blocks = blocks
                else:
                    # Use the blocks already extracted from frontend/backend separately
                    logger.info(f"Using {len(all_extracted_blocks)} blocks extracted during component generation")
                    result.extracted_blocks = all_extracted_blocks
                
                # Save blocks using enhanced gen.py-style organization
                logger.info(f"[FILE_SAVE] Saving {len(result.extracted_blocks)} blocks for {model}/app{result.app_num}")
                logger.info(f"[FILE_SAVE] First 5 filenames: {[getattr(b, 'filename', 'NONAME') for b in result.extracted_blocks[:5]]}")
                saved_count = self.organizer.save_code_blocks_gen_style(
                    result.extracted_blocks, model, create_backup=create_backup
                )
                logger.info(f"[FILE_SAVE] SUCCESS: Saved {saved_count} files using gen.py-style organization")
                # Optionally persist raw markdown (disabled by default)
                if self._save_markdown:
                    self.organizer.save_markdown(result)
                # --- Automatic model/application DB sync (filesystem -> DB) ---
                # After replacing application files, ensure a corresponding ModelCapability & GeneratedApplication
                # row exist so the /models UI immediately reflects the file replacement without manual sync.
                try:  # Guard to avoid breaking generation flow if sync fails
                    from app.services.model_sync_service import upsert_model_and_application  # local import to avoid circular refs
                    # Derive filesystem paths used by ProjectOrganizer for presence flags
                    import re
                    safe_model = re.sub(r'[^\w\-_.]', '_', model)
                    app_dir = Path('generated') / safe_model / f"app{result.app_num}"
                    has_backend = (app_dir / 'backend').exists()
                    has_frontend = (app_dir / 'frontend').exists()
                    # docker-compose.yml may live either under app directory or model root
                    has_compose = any([
                        (app_dir / 'docker-compose.yml').exists(),
                        (app_dir / 'docker-compose.yaml').exists(),
                        (app_dir.parent / 'docker-compose.yml').exists(),
                        (app_dir.parent / 'docker-compose.yaml').exists(),
                    ])
                    upsert_model_and_application(
                        model,
                        result.app_num,
                        has_backend=has_backend,
                        has_frontend=has_frontend,
                        has_compose=has_compose,
                    )
                    if db:
                        # Defer commit until later when we also persist GeneratedCodeResult to keep atomicity
                        db.session.flush()
                except Exception as sync_err:  # noqa: BLE001
                    logger.warning("Auto model/app upsert failed (non-fatal): %s", sync_err)
            result_id = f"{model.replace('/', '_')}_{result.app_num}_{int(time.time())}"
            self._results[result_id] = result
            if result.raw_payload_paths:
                result.raw_payload_paths = list(dict.fromkeys(result.raw_payload_paths))
            if result.raw_response_paths:
                result.raw_response_paths = list(dict.fromkeys(result.raw_response_paths))

            combined_options = {
                "temperature": temperature,
                "max_tokens": max_tokens,
                "generate_frontend": generate_frontend,
                "generate_backend": generate_backend,
            }
            self._persist_generation_artifacts(
                result=result,
                result_id=result_id,
                component_type="combined",
                generation_options=combined_options,
                template=base_template,
            )
            # Append manifest entry (best-effort, atomic via read-modify-write)
            try:
                entry = {
                    'result_id': result_id,
                    'model': result.model,
                    'app_num': result.app_num,
                    'app_name': result.app_name,
                    'timestamp': result.timestamp.isoformat(),
                    'success': result.success,
                    'blocks': [
                        {
                            'language': b.language,
                            'file_type': b.file_type,
                            'checksum': b.checksum,
                            'backend_port': b.backend_port,
                        } for b in result.extracted_blocks
                    ],
                }
                import json as _json
                try:
                    data = _json.loads(self._manifest_path.read_text(encoding='utf-8'))
                    if isinstance(data, list):
                        data.insert(0, entry)
                        # cap size to avoid unbounded growth
                        if len(data) > 5000:
                            data = data[:5000]
                    else:
                        data = [entry]
                except Exception:
                    data = [entry]
                self._manifest_path.write_text(_json.dumps(data, indent=2), encoding='utf-8')
            except Exception:  # noqa: BLE001
                pass
            # Persist to DB if available
            if GeneratedCodeResult and db:
                try:
                    blocks_meta = [
                        {
                            "language": b.language,
                            "file_type": b.file_type,
                            "line_count": b.line_count,
                            "checksum": b.checksum,
                            "backend_port": b.backend_port,
                            "port_replacements": b.port_replacements,
                        } for b in result.extracted_blocks
                    ]
                    rec = GeneratedCodeResult()
                    rec.result_id = result_id
                    rec.model = result.model
                    rec.app_num = result.app_num
                    rec.app_name = result.app_name
                    rec.success = result.success
                    rec.error_message = result.error_message
                    rec.duration = result.duration
                    rec.requirements_json = json.dumps(result.requirements)
                    
                    # Handle large content storage and content hashing
                    content_hash = None
                    if result.success and result.content:
                        content_hash = self._compute_content_hash(result.content)
                        if self._should_store_to_filesystem(result.content):
                            # Store full content to filesystem, truncated version to DB
                            file_ref = self._store_large_content(result_id, result.content)
                            rec.content = self._truncate_content_for_db(result.content)
                            # Store both file reference and content hash
                            rec.error_message = f"LARGE_CONTENT_REF:{file_ref};CONTENT_HASH:{content_hash}"
                        else:
                            rec.content = result.content
                            # Store content hash for duplicate detection
                            if not rec.error_message:
                                rec.error_message = f"CONTENT_HASH:{content_hash}"
                            else:
                                rec.error_message = f"{rec.error_message};CONTENT_HASH:{content_hash}"
                    else:
                        rec.content = result.content if result.success else None
                    
                    rec.blocks_json = json.dumps(blocks_meta)
                    db.session.add(rec)
                    db.session.commit()
                except Exception as e:  # noqa: BLE001
                    if db:
                        try:
                            db.session.rollback()
                        except Exception:
                            pass
                    logger.warning("Failed to persist generation result %s: %s", result_id, e)
            return result_id, result
        finally:
            self._in_flight_generations.discard(generation_key)

    async def generate_batch_async(self, template_ids: List[str], models: List[str], parallel_workers: int = 3) -> Dict[str, Any]:
        # Generate batch ID
        batch_id = f"batch_{int(time.time() * 1000)}"
        logger.info(f"[BATCH] Starting batch {batch_id}: {len(template_ids)} templates x {len(models)} models = {len(template_ids)*len(models)} total")
        logger.info(f"[BATCH] Templates: {template_ids}")
        logger.info(f"[BATCH] Models: {models}")
        
        # Prepare task list
        tasks = []
        for tid in template_ids:
            for model in models:
                tasks.append((tid, model))
        
        # Initialize progress tracking
        progress = BatchProgress(batch_id=batch_id, total_tasks=len(tasks))
        self._batch_operations[batch_id] = progress
        
        semaphore = asyncio.Semaphore(parallel_workers)

        async def run_one(tid: str, model: str):
            async with semaphore:
                try:
                    logger.info(f"[BATCH] Running generation for template={tid}, model={model}")
                    rid, res = await self.generate_async(tid, model)
                    logger.info(f"[BATCH] Generation completed: result_id={rid}, success={res.success}")
                    result = {"result_id": rid, **res.to_dict(include_content=False)}
                    progress.task_results.append(result)
                    # Only count as completed if actually successful
                    if res.success:
                        progress.completed_tasks += 1
                    else:
                        progress.failed_tasks += 1
                except Exception as e:  # noqa: BLE001
                    logger.error(f"[BATCH] Generation FAILED for template={tid}, model={model}: {e}")
                    result = {"template_id": tid, "model": model, "success": False, "error": str(e)}
                    progress.task_results.append(result)
                    progress.failed_tasks += 1
                
                # Update status if complete
                if progress.is_complete:
                    progress.status = "completed" if progress.failed_tasks == 0 else "completed_with_errors"

        await asyncio.gather(*(run_one(tid, m) for tid, m in tasks))
        
        logger.info(f"[BATCH] Batch {batch_id} COMPLETE: {progress.completed_tasks} succeeded, {progress.failed_tasks} failed")
        return {
            "batch_id": batch_id,
            "results": progress.task_results,
            "progress": progress.to_dict()
        }

    def get_batch_progress(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Get progress information for a specific batch operation."""
        progress = self._batch_operations.get(batch_id)
        return progress.to_dict() if progress else None

    def list_batch_operations(self) -> List[Dict[str, Any]]:
        """List all tracked batch operations."""
        return [progress.to_dict() for progress in self._batch_operations.values()]

    def cleanup_completed_batches(self, max_age_hours: int = 24) -> int:
        """Remove completed batch operations older than specified hours."""
        cutoff_time = time.time() - (max_age_hours * 3600)
        to_remove = []
        
        for batch_id, progress in self._batch_operations.items():
            if progress.status in ["completed", "completed_with_errors"] and progress.start_time < cutoff_time:
                to_remove.append(batch_id)
        
        for batch_id in to_remove:
            del self._batch_operations[batch_id]
        
        logger.info("Cleaned up %d completed batch operations", len(to_remove))
        return len(to_remove)

    # ---------------- Results ----------------
    def get_result(self, result_id: str, include_content: bool = False) -> Optional[Dict[str, Any]]:
        res = self._results.get(result_id)
        if res:
            return res.to_dict(include_content=include_content)
        # Fallback to DB
        if GeneratedCodeResult and db:
            try:
                rec = GeneratedCodeResult.query.filter_by(result_id=result_id).first()
                if rec:
                    result_dict = rec.to_dict(include_content=include_content)
                    # Handle large content retrieval and clean up metadata
                    if rec.error_message:
                        error_parts = rec.error_message.split(';')
                        actual_errors = []
                        
                        for part in error_parts:
                            if part.startswith("LARGE_CONTENT_REF:"):
                                if include_content:
                                    file_ref = part[18:]  # Remove "LARGE_CONTENT_REF:" prefix
                                    full_content = self._retrieve_large_content(file_ref)
                                    result_dict["content"] = full_content
                            elif part.startswith("CONTENT_HASH:"):
                                # This is metadata, not a user-visible error
                                continue
                            else:
                                # This is an actual error message
                                actual_errors.append(part)
                        
                        # Clean up error_message for display
                        result_dict["error_message"] = ';'.join(actual_errors) if actual_errors else None
                    
                    return result_dict
            except Exception:
                pass
        return None

    def list_results(self, model: Optional[str] = None, success: Optional[bool] = None,
                     limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        # Gather in-memory first
        in_memory_items = [
            (rid, r) for rid, r in sorted(self._results.items(), key=lambda x: x[1].timestamp, reverse=True)
        ]
        filtered: List[Dict[str, Any]] = []
        for rid, r in in_memory_items:
            if model and r.model != model:
                continue
            if success is not None and r.success != success:
                continue
            filtered.append({"result_id": rid, **r.to_dict(include_content=False)})
        # Add DB rows not already present
        if GeneratedCodeResult and db:
            try:
                query = GeneratedCodeResult.query
                if model:
                    query = query.filter_by(model=model)
                if success is not None:
                    query = query.filter_by(success=success)
                query = query.order_by(GeneratedCodeResult.timestamp.desc())
                existing_ids = {item["result_id"] for item in filtered}
                for rec in query.limit(500):  # broader scan then slice after merge
                    if rec.result_id not in existing_ids:
                        filtered.append(rec.to_dict(include_content=False))
            except Exception:
                pass
        # Apply pagination after merging
        return filtered[offset: offset + limit]

    def delete_result(self, result_id: str) -> bool:
        """Delete a specific result from both memory and database."""
        deleted = False
        # Remove from memory
        if result_id in self._results:
            del self._results[result_id]
            deleted = True
        # Remove from DB and filesystem if needed
        if GeneratedCodeResult and db:
            try:
                rec = GeneratedCodeResult.query.filter_by(result_id=result_id).first()
                if rec:
                    # Clean up large content file if exists
                    if rec.error_message:
                        for part in rec.error_message.split(';'):
                            if part.startswith("LARGE_CONTENT_REF:"):
                                file_ref = part[18:]
                                try:
                                    Path(file_ref).unlink(missing_ok=True)
                                    logger.info("Deleted large content file: %s", file_ref)
                                except Exception as e:  # noqa: BLE001
                                    logger.warning("Failed to delete large content file %s: %s", file_ref, e)
                    
                    db.session.delete(rec)
                    db.session.commit()
                    deleted = True
            except Exception as e:  # noqa: BLE001
                if db:
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                logger.warning("Failed to delete result %s from DB: %s", result_id, e)
        return deleted

    def cleanup_old_results(self, max_age_days: int = 30, dry_run: bool = False) -> Dict[str, Any]:
        """Clean up old results and optionally orphaned scaffolds."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        deleted_count = 0
        deleted_ids = []
        
        # Clean memory first
        to_remove = [rid for rid, result in self._results.items() if result.timestamp < cutoff]
        if not dry_run:
            for rid in to_remove:
                del self._results[rid]
        deleted_count += len(to_remove)
        deleted_ids.extend(to_remove)
        
        # Clean DB
        if GeneratedCodeResult and db:
            try:
                query = GeneratedCodeResult.query.filter(GeneratedCodeResult.timestamp < cutoff)
                db_records = query.all()
                db_ids = [rec.result_id for rec in db_records]
                deleted_ids.extend(db_ids)
                deleted_count += len(db_ids)
                
                if not dry_run:
                    # Clean up large content files first
                    for rec in db_records:
                        if rec.error_message:
                            for part in rec.error_message.split(';'):
                                if part.startswith("LARGE_CONTENT_REF:"):
                                    file_ref = part[18:]
                                    try:
                                        Path(file_ref).unlink(missing_ok=True)
                                        logger.info("Cleaned up large content file: %s", file_ref)
                                    except Exception as e:  # noqa: BLE001
                                        logger.warning("Failed to cleanup large content file %s: %s", file_ref, e)
                        db.session.delete(rec)
                    db.session.commit()
            except Exception as e:  # noqa: BLE001
                if db:
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                logger.warning("Failed to cleanup old results from DB: %s", e)
        
        return {
            "deleted_count": deleted_count,
            "deleted_ids": deleted_ids if dry_run else [],
            "cutoff_date": cutoff.isoformat(),
            "dry_run": dry_run
        }

    def regenerate(self, result_id: str, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> Tuple[str, GenerationResult]:
        """Regenerate using same template and model from an existing result."""
        # Find original result
        original = self._results.get(result_id)
        if not original and GeneratedCodeResult and db:
            try:
                rec = GeneratedCodeResult.query.filter_by(result_id=result_id).first()
                if rec:
                    # Find template by app_num/name
                    template = None
                    for t in self.template_registry.templates:
                        if t.app_num == rec.app_num or t.name == rec.app_name:
                            template = t
                            break
                    if template:
                        import asyncio
                        return asyncio.run(self.generate_async(
                            str(template.app_num), 
                            rec.model, 
                            temperature, 
                            max_tokens
                        ))
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to regenerate from DB result %s: %s", result_id, e)
        
        if not original:
            raise ValueError(f"Original result {result_id} not found")
        
        # Find matching template
        template = None
        for t in self.template_registry.templates:
            if t.app_num == original.app_num or t.name == original.app_name:
                template = t
                break
        
        if not template:
            raise ValueError(f"Template for result {result_id} no longer exists")
        
        # Generate new result
        import asyncio
        return asyncio.run(self.generate_async(
            str(template.app_num),
            original.model,
            temperature,
            max_tokens
        ))

    def project_structure(self) -> Dict[str, Any]:
        return self.organizer.structure()


# Singleton-like accessor (created lazily on first use)
_sample_generation_service: Optional[SampleGenerationService] = None


def get_sample_generation_service() -> SampleGenerationService:
    global _sample_generation_service  # noqa: PLW0603
    if _sample_generation_service is None:
        _sample_generation_service = SampleGenerationService()
    return _sample_generation_service
