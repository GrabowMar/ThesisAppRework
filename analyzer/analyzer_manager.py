#!/usr/bin/env python3
"""
Unified Analyzer Manager
========================

A comprehensive Python script for managing containerized analysis services
and running various types of code analysis on AI-generated applications.

Features:
- Docker container management (start, stop, restart, status)
- Real-time WebSocket communication with analyzer services
- Batch analysis capabilities
- Security scanning (Bandit, Safety, Static Analysis)
- Performance testing (Locust-based load testing)
- AI-powered code analysis (OpenRouter integration)
- Static code analysis (PyLint, ESLint, etc.)
- Interactive CLI and programmatic API

Usage:
    python analyzer_manager.py start                    # Start all services
    python analyzer_manager.py stop                     # Stop all services
    python analyzer_manager.py status                   # Show service status
    python analyzer_manager.py analyze <model> <app>    # Run analysis
    python analyzer_manager.py batch <models>           # Batch analysis
    python analyzer_manager.py test                     # Test all services

Author: AI Assistant
Date: August 2025
"""

import asyncio
import os
import json
import logging
import socket
import subprocess
import sys
import time
import uuid
try:
    from .universal_results import build_universal_payload, write_universal_file
except Exception:  # pragma: no cover - optional path
    build_universal_payload = None  # type: ignore
    write_universal_file = None  # type: ignore
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

import websockets
from websockets.exceptions import ConnectionClosed

# Import slug normalization utilities from Flask app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
try:
    from app.utils.slug_utils import normalize_model_slug, generate_slug_variants
except ImportError:
    # Fallback if running standalone
    def normalize_model_slug(raw_slug: str) -> str:
        """Fallback slug normalization."""
        return raw_slug.strip().lower().replace('/', '_').replace(' ', '-')
    def generate_slug_variants(model_slug: str) -> List[str]:
        """Fallback variant generation."""
        variants = [
            model_slug,
            model_slug.replace('_', '-'),
            model_slug.replace('-', '_'),
            model_slug.replace('_', '/'),
        ]
        return list(dict.fromkeys(variants))  # dedupe

# Import shared analysis utilities
try:
    from app.utils.sarif_utils import (
        extract_sarif_to_files as shared_extract_sarif,
        strip_sarif_rules as shared_strip_sarif,
    )
    from app.utils.tool_normalization import (
        normalize_severity as shared_normalize_severity,
        collect_normalized_tools as shared_collect_tools,
        aggregate_findings_from_services as shared_aggregate_findings,
        categorize_services as shared_categorize_services,
        determine_overall_status as shared_determine_status,
    )
    SHARED_UTILS_AVAILABLE = True
except ImportError:
    SHARED_UTILS_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# JSON mode: when set, restrict stdout to machine-readable JSON only
JSON_MODE = bool(int(os.environ.get('ANALYZER_JSON', '0'))) if 'ANALYZER_JSON' in os.environ else False
if JSON_MODE:
    # Redirect existing log handlers to stderr to keep stdout clean
    try:
        root_logger = logging.getLogger()
        for h in list(root_logger.handlers):
            try:
                h.stream = sys.stderr  # type: ignore[attr-defined]
            except Exception:
                try:
                    root_logger.removeHandler(h)
                except Exception:
                    pass
        # Ensure at least one stderr handler
        if not any(getattr(h, 'stream', None) is sys.stderr for h in root_logger.handlers):
            sh = logging.StreamHandler(stream=sys.stderr)
            sh.setLevel(logging.INFO)
            sh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            root_logger.addHandler(sh)
    except Exception:
        pass


@dataclass
class AnalysisRequest:
    """Request for code analysis."""
    model_slug: str
    app_number: int
    analysis_type: str
    source_path: str = ""
    options: Optional[Dict[str, Any]] = None
    timeout: int = 900

    def __post_init__(self):
        if self.options is None:
            self.options = {}
        if not self.source_path:
            self.source_path = f"/app/sources/{self.model_slug}/app{self.app_number}"


import random

@dataclass
class ServiceInfo:
    """Information about an analyzer service."""
    name: str
    port: int
    container_name: str
    websocket_url: str  # Kept for backward compat (primary URL)
    urls: List[str]     # List of all available replica URLs
    health_status: str = "unknown"
    last_check: Optional[datetime] = None


class AnalyzerManager:
    """Main manager for analyzer infrastructure."""
    
    @staticmethod
    def _is_running_in_docker() -> bool:
        """Detect if running inside a Docker container."""
        # Check for Docker-specific files/environment
        if os.path.exists('/.dockerenv'):
            return True
        if os.environ.get('RUNNING_IN_DOCKER', '').lower() in ('true', '1', 'yes'):
            return True
        if os.environ.get('IN_DOCKER', '').lower() in ('true', '1', 'yes'):
            return True
        # Check if redis host is reachable (indicates we're in analyzer network)
        if os.environ.get('REDIS_URL', '').startswith('redis://redis:'):
            return True
        try:
            with open('/proc/1/cgroup', 'r') as f:
                return 'docker' in f.read()
        except Exception:
            pass
        return False
    
    def __init__(self, isolation_id: Optional[str] = None):
        """Initialize AnalyzerManager with optional isolation ID for parallel execution.

        Args:
            isolation_id: Optional isolation identifier for parallel test execution.
                         If not provided, uses ANALYSIS_ISOLATION_ID from environment.
                         Empty string or None means production mode (no isolation).
        """
        # Get isolation ID from parameter or environment
        self.isolation_id = isolation_id or os.environ.get('ANALYSIS_ISOLATION_ID', '')

        # Detect if running inside Docker to use service names instead of localhost
        in_docker = self._is_running_in_docker()

        # Calculate port offsets for isolation to avoid conflicts
        port_offset = self._calculate_port_offset()

        # Build service configurations with dynamic naming and ports
        base_ports = {
            'static': 2001,
            'dynamic': 2002,
            'perf': 2003,
            'ai': 2004
        }
        
        # Mapping from short type to env var prefix
        env_param_map = {
            'static': 'STATIC_ANALYZER_URLS',
            'dynamic': 'DYNAMIC_ANALYZER_URLS',
            'perf': 'PERF_TESTER_URLS',
            'ai': 'AI_ANALYZER_URLS'
        }

        self.services = {}
        for service_type, base_port in base_ports.items():
            port = base_port + port_offset

            # Map service types to service names
            service_name_map = {
                'static': 'static-analyzer',
                'dynamic': 'dynamic-analyzer',
                'perf': 'performance-tester',
                'ai': 'ai-analyzer'
            }
            service_name = service_name_map[service_type]

            # Add isolation suffix to container names if in isolated mode
            container_suffix = f"-{self.isolation_id}" if self.isolation_id else ""
            
            # Primary URL (constructed legacy way)
            primary_url = self._build_websocket_url(service_name, port, in_docker, container_suffix)
            
            # Resolve all URLs (replicas)
            urls = []
            
            # 1. Try environment variable (comma-separated configs)
            env_var = env_param_map.get(service_type, '')
            if env_var and os.environ.get(env_var):
                raw_urls = os.environ[env_var].split(',')
                urls = [u.strip() for u in raw_urls if u.strip()]
                logger.info(f"Loaded {len(urls)} URLs for {service_name} from {env_var}")
            
            # 2. Fallback to constructed primary URL if env var missing/empty
            if not urls:
                urls = [primary_url]
                logger.debug(f"Using default single URL for {service_name}: {primary_url}")

            self.services[service_name] = ServiceInfo(
                name=service_name,
                port=port,
                container_name=f'analyzer-{service_name}-1{container_suffix}',
                websocket_url=primary_url,
                urls=urls
            )

        if self.isolation_id:
            logger.info(f"AnalyzerManager initialized in ISOLATED mode: isolation_id={self.isolation_id}, port_offset={port_offset}")
        else:
            logger.info("AnalyzerManager initialized in PRODUCTION mode (no isolation)")

        # Compose file located in the root directory
        self.compose_file = (Path(__file__).parent.parent / "docker-compose.yml").resolve()
        # Save results under project root results folder
        self.results_dir = (Path(__file__).parent.parent / "results").resolve()
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Determine docker compose command (prefer modern 'docker compose')
        self._compose_cmd = self._resolve_compose_cmd()
        # Discover available model slugs under ../generated for convenience
        try:
            # Prefer project-root generated directory for model sources
            self._models_root = (Path(__file__).parent.parent / "generated").resolve()
        except Exception:
            self._models_root = None
        # Lazy-loaded port configuration cache
        self._port_config_cache: Optional[List[Dict[str, Any]]] = None
        # Legacy directory names we want to keep pruned under each app folder
        self._legacy_result_dirs = ["static-analyzer","dynamic-analyzer","performance-tester","ai-analyzer","security-analyzer"]

    def _calculate_port_offset(self) -> int:
        """Calculate port offset based on isolation ID to avoid port conflicts.

        Returns:
            int: Port offset (0 for production, 100/200/300/... for isolated sessions)

        The offset allows up to 10 parallel test sessions (100 ports apart each).
        """
        if not self.isolation_id:
            return 0
        # Hash isolation ID to consistent port offset (0, 100, 200, ...)
        hash_val = sum(ord(c) for c in self.isolation_id)
        return (hash_val % 10) * 100

    def _build_websocket_url(self, service_name: str, port: int, in_docker: bool, container_suffix: str) -> str:
        """Build WebSocket URL with isolation awareness.

        Args:
            service_name: Base service name (e.g., 'static-analyzer')
            port: Port number (with offset applied)
            in_docker: Whether running inside Docker container
            container_suffix: Suffix to add to container name (empty for production)

        Returns:
            str: WebSocket URL (e.g., 'ws://static-analyzer:2001' or 'ws://127.0.0.1:2101')
        """
        if in_docker:
            # Use service name with isolation suffix for container-to-container communication
            return f'ws://{service_name}{container_suffix}:{port}'
        else:
            # Use localhost with offset port for host-to-container communication
            return f'ws://127.0.0.1:{port}'

    @staticmethod
    def _sanitize_task_id(task_id: str) -> str:
        cleaned = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in str(task_id))
        return cleaned or 'task'

    @staticmethod
    def _is_task_dir_name(name: str) -> bool:
        return name.startswith('task-') or name.startswith('task_')

    def _build_task_output_dir(self, model_slug: str, app_number: int, task_id: str) -> Path:
        """Return the folder where consolidated results for a task should live."""
        safe_slug = str(model_slug).replace('/', '_').replace('\\', '_')
        sanitized_task = self._sanitize_task_id(task_id)
        app_dir = self.results_dir / safe_slug / f"app{app_number}"
        app_dir.mkdir(parents=True, exist_ok=True)
        # Don't add task_ prefix if sanitized_task already starts with it
        dir_name = sanitized_task if sanitized_task.startswith('task_') else f"task_{sanitized_task}"
        target_dir = app_dir / dir_name
        legacy_candidates = [
            app_dir / 'analysis' / dir_name,
            app_dir / 'analysis' / sanitized_task.replace('_', '-'),
        ]

        target_dir.mkdir(parents=True, exist_ok=True)

        for legacy_dir in legacy_candidates:
            if not legacy_dir.exists() or not legacy_dir.is_dir():
                continue
            for item in legacy_dir.iterdir():
                destination = target_dir / item.name
                if destination.exists():
                    continue
                try:
                    item.replace(destination)
                except Exception:
                    try:
                        item.rename(destination)
                    except Exception:
                        logger.debug("Failed to migrate legacy artefact %s", item)
            try:
                legacy_dir.rmdir()
            except OSError:
                pass

        return target_dir

    # ---------------------------------------------------------------
    # Legacy Results Pruning
    # ---------------------------------------------------------------
    def prune_legacy_results(self, model_slug: str, app_number: int) -> None:
        """Remove legacy per-service result directories & stray files.

        Earlier versions emitted per-service folders and nested everything under an
        `analysis/` directory. The current design consolidates into
        results/<model>/appN/task_<task>. This helper deletes obsolete folders,
        migrates any remaining task directories, and cleans well-known stray artefacts.
        """
        try:
            base = (self.results_dir / model_slug.replace('/', '_').replace('\\', '_') / f"app{app_number}")
            if not base.exists():
                return
            removed = []
            analysis_dir = base / 'analysis'
            if analysis_dir.exists():
                for legacy_file in analysis_dir.glob('*.json'):
                    try:
                        legacy_file.unlink(missing_ok=True)  # type: ignore[arg-type]
                    except Exception:
                        pass
                for legacy_task_dir in analysis_dir.iterdir():
                    if not legacy_task_dir.is_dir() or not self._is_task_dir_name(legacy_task_dir.name):
                        continue
                    remainder = legacy_task_dir.name[5:]
                    if remainder.startswith(('-', '_')):
                        remainder = remainder[1:]
                    sanitized = self._sanitize_task_id(remainder)
                    destination = base / f"task_{sanitized}"
                    if destination.exists():
                        continue
                    try:
                        legacy_task_dir.rename(destination)
                        continue
                    except OSError:
                        destination.mkdir(parents=True, exist_ok=True)
                        for item in legacy_task_dir.iterdir():
                            dest_item = destination / item.name
                            if dest_item.exists():
                                continue
                            try:
                                item.replace(dest_item)
                            except Exception:
                                try:
                                    item.rename(dest_item)
                                except Exception:
                                    logger.debug("Failed to relocate legacy artefact %s", item)
                        try:
                            legacy_task_dir.rmdir()
                        except OSError:
                            pass
                try:
                    next(analysis_dir.iterdir())
                except StopIteration:
                    try:
                        analysis_dir.rmdir()
                    except OSError:
                        pass
                except Exception:
                    pass
            for legacy in self._legacy_result_dirs:
                d = base / legacy
                if d.exists() and d.is_dir():
                    for f in d.glob("*.json"):
                        try:
                            f.unlink(missing_ok=True)  # type: ignore[arg-type]
                        except Exception:
                            pass
                    try:
                        d.rmdir()
                        removed.append(legacy)
                    except OSError:
                        # Non-empty (unexpected) – attempt recursive removal
                        import shutil
                        try:
                            shutil.rmtree(d, ignore_errors=True)
                            removed.append(legacy)
                        except Exception:
                            pass
            # Remove stray ai-analyzer cache file if present
            stray = base / 'ai-analyzer' / '.analysis_results.json'
            if stray.exists():
                try:
                    stray.unlink()
                except Exception:
                    pass
            if removed:
                logger.debug(f"Pruned legacy result dirs for {model_slug} app{app_number}: {removed}")
        except Exception as e:
            logger.debug(f"Legacy prune failed for {model_slug} app{app_number}: {e}")

    # -----------------------------------------------------------------
    # Port Configuration Helpers
    # -----------------------------------------------------------------
    def _load_port_config(self) -> List[Dict[str, Any]]:
        """Load port configurations from database.

        Returns empty list if database query fails. The results are cached
        to avoid repeatedly querying the database for every analysis request.
        """
        if self._port_config_cache is not None:
            return self._port_config_cache
        
        root = Path(__file__).parent.parent  # project root - defined outside try for fallback access
        
        try:
            # Try to load from database first
            sys.path.insert(0, str(root / 'src'))
            
            from app import create_app
            from app.models import PortConfiguration
            
            app = create_app()
            with app.app_context():
                port_configs = PortConfiguration.query.all()
                data = []
                for pc in port_configs:
                    data.append({
                        'model': pc.model,  # using 'model' to match field name
                        'app_number': pc.app_num,  # using app_number for consistency
                        'backend_port': pc.backend_port,
                        'frontend_port': pc.frontend_port
                    })
                self._port_config_cache = data
                logger.info(f"Loaded {len(data)} port configurations from database")
                return self._port_config_cache
                
        except Exception as e:
            logger.warning(f"Could not load port configurations from database: {e}")
            
            # Fallback to JSON file if database fails
            try:
                cfg_path = (root / 'misc' / 'port_config.json').resolve()
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self._port_config_cache = data  # type: ignore[assignment]
                    logger.info(f"Loaded {len(data)} port configurations from JSON file (fallback)")
                else:
                    self._port_config_cache = []
            except Exception as json_err:
                logger.warning(f"Could not load port_config.json either: {json_err}")
                self._port_config_cache = []
        
        return self._port_config_cache

    def _normalize_and_validate_app(self, model_slug: str, app_number: int, include_failed: bool = False) -> Union[Tuple[str, Path], Dict[str, Any]]:
        """Normalize model slug and validate app exists.
        
        Searches for apps in both flat and template-based directory structures:
        - generated/apps/{model}/app{N}/  (flat, backward compatible)
        - generated/apps/{model}/{template}/app{N}/  (template-based)
        
        Also checks the database to verify the app generation didn't fail.
        
        Args:
            model_slug: Model slug to normalize and validate
            app_number: App number to validate
            include_failed: If True, allow analyzing apps with failed generation status
        
        Returns:
            Tuple of (normalized_slug, app_path) if app exists and is valid
            Dict with error details if validation fails
        """
        # Normalize slug to canonical format (provider_model-name)
        normalized_slug = normalize_model_slug(model_slug)
        
        # Check database for generation failure status
        if not include_failed:
            failure_check = self._check_generation_failed(normalized_slug, app_number)
            if failure_check:
                return failure_check  # Return error dict
        
        # Check if app exists in filesystem
        root = Path(__file__).parent.parent  # project root
        base_path = root / 'generated' / 'apps' / normalized_slug
        
        # Try flat structure first (backward compatible)
        app_path = base_path / f'app{app_number}'
        
        if app_path.exists() and app_path.is_dir():
            return normalized_slug, app_path
        
        # Try searching in template subdirectories
        if base_path.exists():
            for template_dir in base_path.iterdir():
                if template_dir.is_dir() and not template_dir.name.startswith('.'):
                    template_app_path = template_dir / f'app{app_number}'
                    if template_app_path.exists() and template_app_path.is_dir():
                        logger.info(f"Found app in template directory: {template_dir.name}/app{app_number}")
                        return normalized_slug, template_app_path
        
        # Try slug variants for backward compatibility
        for variant in generate_slug_variants(model_slug):
            variant_base = root / 'generated' / 'apps' / variant
            
            # Try flat structure
            variant_path = variant_base / f'app{app_number}'
            if variant_path.exists() and variant_path.is_dir():
                logger.info(f"Found app using variant slug: {variant} (requested: {model_slug})")
                return variant, variant_path
            
            # Try template subdirectories
            if variant_base.exists():
                for template_dir in variant_base.iterdir():
                    if template_dir.is_dir() and not template_dir.name.startswith('.'):
                        variant_template_path = template_dir / f'app{app_number}'
                        if variant_template_path.exists() and variant_template_path.is_dir():
                            logger.info(f"Found app using variant slug: {variant}/{template_dir.name}/app{app_number}")
                            return variant, variant_template_path
        
        logger.error(f"App does not exist: {base_path}/app{app_number} (tried flat and template structures)")
        logger.error(f"Cannot analyze non-existent app. Generate it first or check model slug.")
        return {
            'status': 'error',
            'error': f'App does not exist: {model_slug} app{app_number}',
            'message': 'Generate the app first before running analysis'
        }

    def _check_generation_failed(self, model_slug: str, app_number: int) -> Optional[dict]:
        """Check if an app's generation failed in the database.
        
        This is called before attempting analysis to prevent analyzing
        incomplete or broken apps.
        
        NOTE: This check is skipped when running from async/CLI context to avoid
        Flask app context conflicts with the event loop.
        
        Args:
            model_slug: Normalized model slug
            app_number: App number
            
        Returns:
            Error dict if generation failed, None if app is valid for analysis
        """
        try:
            # Check if we're in an async context (event loop running)
            # If so, skip DB check to avoid Flask context conflicts
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                if loop and loop.is_running():
                    logger.debug("Running in async context - skipping Flask DB check")
                    return None
            except RuntimeError:
                # No running event loop - safe to use Flask
                pass
            
            # Try to import Flask app context for DB access
            # This may fail if running standalone (CLI mode without Flask)
            try:
                import sys
                src_path = Path(__file__).parent.parent / 'src'
                if str(src_path) not in sys.path:
                    sys.path.insert(0, str(src_path))
                
                from app.factory import create_app
                from app.models import GeneratedApplication
                from app.constants import AnalysisStatus
            except ImportError:
                # Running in standalone mode without Flask - skip DB check
                logger.debug("Flask not available - skipping generation failure check")
                return None
            
            # Create minimal app context if needed
            try:
                from flask import current_app
                app = current_app._get_current_object()  # type: ignore[attr-defined]
            except RuntimeError:
                # No app context - create one
                app = create_app()
            
            with app.app_context():
                # Query for the app record
                app_record = GeneratedApplication.query.filter_by(
                    model_slug=model_slug,
                    app_number=app_number
                ).first()
                
                if not app_record:
                    # No database record - allow filesystem-only apps (backward compatibility)
                    logger.debug(f"No database record for {model_slug}/app{app_number} - allowing analysis")
                    return None
                
                # Check if generation is still in progress
                if app_record.generation_status == AnalysisStatus.RUNNING:
                    logger.warning(
                        f"Cannot analyze {model_slug}/app{app_number}: "
                        f"generation is still in progress"
                    )
                    return {
                        'status': 'error',
                        'error': f"Generation in progress for {model_slug}/app{app_number}",
                        'message': "Wait for generation to complete before running analysis"
                    }
                
                # Check if generation failed
                if app_record.is_generation_failed or app_record.generation_status == AnalysisStatus.FAILED:
                    failure_stage = app_record.failure_stage or 'unknown'
                    error_msg = app_record.error_message or 'Unknown error'
                    
                    logger.error(
                        f"Cannot analyze {model_slug}/app{app_number}: "
                        f"generation failed at stage '{failure_stage}': {error_msg}"
                    )
                    return {
                        'status': 'error',
                        'error': f"Generation failed for {model_slug}/app{app_number}",
                        'message': f"Generation failed at stage '{failure_stage}': {error_msg}. "
                                   f"Fix the generation issues or regenerate the app before analysis.",
                        'failure_stage': failure_stage,
                        'error_details': error_msg
                    }
                
                # App is valid for analysis
                return None
                
        except Exception as e:
            # Log but don't block analysis on DB check failure
            logger.warning(f"Could not check generation status for {model_slug}/app{app_number}: {e}")
            return None

    def _resolve_app_ports(self, model_slug: str, app_number: int) -> Optional[Tuple[int, int]]:
        """Resolve backend & frontend ports for a model/app.

        PRIORITY ORDER (highest to lowest):
        1. .env file in generated app directory (source of truth for running apps)
           - Searches both flat and template-based directory structures
        2. Database/JSON configuration (fallback for apps without .env)
        3. Docker inspect: attempt to auto-detect internal container ports for app containers

        Returns None if no configuration found (caller MUST handle this error).
        """
        try:
            # PRIORITY 1: Try reading from generated app's .env file FIRST (source of truth)
            try:
                root = Path(__file__).parent.parent  # project root
                base_path = root / 'generated' / 'apps' / model_slug
                
                # Try flat structure first
                app_env_path = base_path / f'app{app_number}' / '.env'
                logger.debug(f"Checking flat structure: {app_env_path}")
                
                # If not found in flat structure, search template directories
                if not app_env_path.exists():
                    logger.debug(f"Flat structure not found, searching template directories in {base_path}")
                    if base_path.exists():
                        for template_dir in base_path.iterdir():
                            if template_dir.is_dir() and not template_dir.name.startswith('.'):
                                template_env_path = template_dir / f'app{app_number}' / '.env'
                                logger.debug(f"Checking template path: {template_env_path}")
                                if template_env_path.exists():
                                    app_env_path = template_env_path
                                    logger.info(f"Found .env in template directory: {app_env_path}")
                                    break
                
                if app_env_path.exists():
                    logger.info(f"Reading port configuration from: {app_env_path}")
                    backend_port = None
                    frontend_port = None
                    with open(app_env_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith('BACKEND_PORT='):
                                backend_port = int(line.split('=', 1)[1].strip())
                            elif line.startswith('FRONTEND_PORT='):
                                frontend_port = int(line.split('=', 1)[1].strip())
                    
                    if backend_port and frontend_port:
                        logger.info(f"✓ Resolved ports from .env file for {model_slug} app {app_number}: backend={backend_port}, frontend={frontend_port}")
                        return backend_port, frontend_port
                    else:
                        logger.warning(f"Found .env file at {app_env_path} but missing BACKEND_PORT or FRONTEND_PORT")
                else:
                    logger.debug(f"No .env file found for {model_slug} app {app_number} in filesystem")
            except Exception as env_err:
                logger.debug(f"Could not read .env file for {model_slug} app {app_number}: {env_err}")
            
            # PRIORITY 2: Fall back to database/JSON configuration using slug variants
            for variant in generate_slug_variants(model_slug):
                for entry in self._load_port_config():
                    if (entry.get('model') == variant and
                            int(entry.get('app_number', -1)) == int(app_number)):
                        b = entry.get('backend_port')
                        f = entry.get('frontend_port')
                        if isinstance(b, int) and isinstance(f, int):
                            logger.debug(f"Resolved ports for {model_slug} app {app_number}: backend={b}, frontend={f} (matched as {variant} from database)")
                            return b, f

            # PRIORITY 3: Attempt to inspect running Docker containers to discover internal ports
            try:
                safe_slug = model_slug.replace('_', '-').replace('.', '-')
                backend_container = f"{safe_slug}-app{app_number}_backend"
                frontend_container = f"{safe_slug}-app{app_number}_frontend"

                def _inspect_container_internal_port(container_name: str) -> Optional[int]:
                    """Return the first exposed/internal port for a container or None."""
                    try:
                        rc, out, err = self.run_command([
                            "docker", "inspect", "-f", "{{json .NetworkSettings.Ports}}", container_name
                        ], capture_output=True, timeout=6)
                        if rc == 0 and out:
                            ports_map = json.loads(out)
                            # keys look like '5000/tcp' or '80/tcp'
                            for key in ports_map.keys():
                                if isinstance(key, str) and '/' in key:
                                    try:
                                        return int(key.split('/', 1)[0])
                                    except Exception:
                                        continue
                        # Fallback to Config.ExposedPorts
                        rc, out, err = self.run_command([
                            "docker", "inspect", "-f", "{{json .Config.ExposedPorts}}", container_name
                        ], capture_output=True, timeout=6)
                        if rc == 0 and out:
                            exposed = json.loads(out)
                            for key in exposed.keys():
                                if isinstance(key, str) and '/' in key:
                                    try:
                                        return int(key.split('/', 1)[0])
                                    except Exception:
                                        continue
                    except Exception as e:
                        logger.debug(f"docker inspect failed for {container_name}: {e}")
                    return None

                backend_internal = _inspect_container_internal_port(backend_container)
                frontend_internal = _inspect_container_internal_port(frontend_container)

                if backend_internal and frontend_internal:
                    logger.info(f"✓ Resolved ports via Docker inspect for {model_slug} app {app_number}: backend={backend_internal}, frontend={frontend_internal}")
                    return backend_internal, frontend_internal
                else:
                    logger.debug(f"Docker inspect did not yield internal ports for {model_slug} app {app_number} (backend={backend_internal}, frontend={frontend_internal})")
            except Exception as docker_err:
                logger.debug(f"Docker inspect attempt failed: {docker_err}")

            logger.error(f"No port configuration found for {model_slug} app {app_number}")
            logger.error(f"Cannot run dynamic/performance analysis without port configuration.")
        except Exception as e:
            logger.error(f"Error resolving ports for {model_slug} app {app_number}: {e}")
        return None

    def _resolve_compose_cmd(self) -> List[str]:
        """Detect the appropriate docker compose command.

        Returns ['docker', 'compose'] when available, otherwise ['docker-compose'].
        """
        try:
            # Check for 'docker compose' (Compose V2)
            rc, _, _ = self.run_command(["docker", "compose", "version"], capture_output=True, timeout=10)
            if rc == 0:
                return ["docker", "compose"]
        except Exception:
            pass
        # Fallback to legacy docker-compose
        return ["docker-compose"]
    
    # =================================================================
    # DOCKER CONTAINER MANAGEMENT
    # =================================================================
    
    def _get_compose_env(self) -> Dict[str, str]:
        """Get environment variables for docker-compose with isolation support.

        Returns:
            Dict[str, str]: Environment variables including isolation context
        """
        env = os.environ.copy()
        if self.isolation_id:
            # Set project name for isolation
            env['COMPOSE_PROJECT_NAME'] = f'thesisapp-{self.isolation_id}'
            env['ISOLATION_ID'] = self.isolation_id
            env['ISOLATION_SUFFIX'] = f'-{self.isolation_id}'

            # Pass port offsets to docker-compose
            offset = self._calculate_port_offset()
            env['STATIC_PORT'] = str(2001 + offset)
            env['DYNAMIC_PORT'] = str(2002 + offset)
            env['PERF_PORT'] = str(2003 + offset)
            env['AI_PORT'] = str(2004 + offset)
            env['REDIS_PORT'] = str(6379 + offset)

            logger.debug(f"Compose env with isolation: project={env['COMPOSE_PROJECT_NAME']}, ports={offset}")
        return env

    def run_command(self, command: List[str], capture_output: bool = False,
                   timeout: int = 60, env: Optional[Dict[str, str]] = None) -> Tuple[int, str, str]:
        """Run a shell command and return result.

        Args:
            command: Command to run as list of strings
            capture_output: Whether to capture stdout/stderr
            timeout: Command timeout in seconds
            env: Optional environment variables (uses _get_compose_env() if None for compose commands)

        Returns:
            Tuple of (returncode, stdout, stderr)
        """
        try:
            # Use isolation-aware environment for docker-compose commands
            if env is None and 'compose' in ' '.join(command).lower():
                env = self._get_compose_env()

            logger.info(f"Running: {' '.join(command)}")
            result = subprocess.run(
                command,
                capture_output=capture_output,
                text=True,
                cwd=Path(__file__).parent,
                timeout=timeout,
                env=env
            )
            return result.returncode, result.stdout or "", result.stderr or ""
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out after {timeout}s")
            return 1, "", "Command timed out"
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return 1, "", str(e)
    
    def start_services(self) -> bool:
        """Start all analyzer services using Docker Compose."""
        logger.info("[START] Starting analyzer infrastructure...")
        
        if not self.compose_file.exists():
            logger.error(f"[ERROR] Docker Compose file not found: {self.compose_file}")
            return False
        
        # Build and start services
        returncode, stdout, stderr = self.run_command(
            self._compose_cmd + ['up', '--build', '-d'], timeout=300
        )  # 5 minutes for building
        
        if returncode == 0:
            logger.info("[OK] All services started successfully!")
            
            # Wait for services to initialize
            logger.info("[WAIT] Waiting for services to initialize...")
            time.sleep(15)
            
            # Check service health (but don't wait for it)
            asyncio.create_task(self.check_all_services_health())
            return True
        else:
            logger.error(f"[ERROR] Failed to start services: {stderr}")
            return False
    
    def stop_services(self) -> bool:
        """Stop all analyzer services."""
        logger.info("[STOP] Stopping analyzer infrastructure...")
        
        returncode, stdout, stderr = self.run_command(self._compose_cmd + ['down'])
        
        if returncode == 0:
            logger.info("[OK] All services stopped successfully!")
            return True
        else:
            logger.error(f"[ERROR] Failed to stop services: {stderr}")
            return False
    
    def restart_services(self) -> bool:
        """Restart all analyzer services."""
        logger.info("[SYNC] Restarting analyzer infrastructure...")
        self.stop_services()
        time.sleep(3)
        return self.start_services()
    
    def get_container_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all containers."""
        returncode, stdout, stderr = self.run_command(
            self._compose_cmd + ['ps', '--format', 'json'], capture_output=True
        )
        
        containers = {}
        if returncode == 0 and stdout:
            try:
                for line in stdout.strip().split('\n'):
                    if line:
                        container_data = json.loads(line)
                        service_name = container_data.get('Service', '')
                        containers[service_name] = {
                            'name': container_data.get('Name', ''),
                            'state': container_data.get('State', ''),
                            'status': container_data.get('Status', ''),
                            'ports': container_data.get('Publishers', [])
                        }
            except json.JSONDecodeError:
                logger.warning("Could not parse container status JSON")
        
        return containers
    
    def check_port_accessibility(self, host: str, port: int, timeout: int = 3) -> bool:
        """Check if a port is accessible."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def show_status(self) -> None:
        """Show comprehensive status of all services."""
        logger.info("[STATS] Checking service status...")
        
        print("\n" + "=" * 80)
        print("[DOCKER] ANALYZER INFRASTRUCTURE STATUS")
        print("=" * 80)
        
        # Docker container status
        containers = self.get_container_status()
        
        print("\n🔧 CONTAINER STATUS:")
        print("-" * 50)
        
        for service_name, service_info in self.services.items():
            container_data = containers.get(service_name, {})
            state = container_data.get('state', 'Not found')
            status = container_data.get('status', 'Unknown')
            
            state_icon = "[OK]" if state == "running" else "[ERROR]"
            print(f"{state_icon} {service_name:20} | {state:10} | {status}")
        
        # Port accessibility
        print("\n[SIGNAL] PORT ACCESSIBILITY:")
        print("-" * 50)
        
        for service_name, service_info in self.services.items():
            accessible = self.check_port_accessibility('localhost', service_info.port)
            access_icon = "[OK]" if accessible else "[ERROR]"
            print(f"{access_icon} {service_name:20} | localhost:{service_info.port:5} | {'ACCESSIBLE' if accessible else 'NOT ACCESSIBLE'}")
        
        # WebSocket health check
        print("\n[HEALTH] SERVICE HEALTH:")
        print("-" * 50)
        
        # Check if we can run health checks (avoid event loop conflicts)
        try:
            # Try to get the current event loop
            try:
                asyncio.get_running_loop()
                # If we're already in an event loop, skip detailed health check
                logger.info("Already in event loop, skipping detailed health check")
                for service_name in self.services.keys():
                    print(f"[INFO]  {service_name:20} | RUNNING    | Use 'health' command for details")
            except RuntimeError:
                # No running loop, safe to create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    health_results = loop.run_until_complete(self.check_all_services_health())
                    
                    for service_name, health_data in health_results.items():
                        if health_data.get('status') == 'healthy':
                            health_icon = "[OK]"
                            health_status = "HEALTHY"
                            extra_info = f"v{health_data.get('version', 'unknown')}"
                        else:
                            health_icon = "[ERROR]" 
                            health_status = "UNHEALTHY"
                            extra_info = health_data.get('error', 'Unknown error')[:30]
                        
                        print(f"{health_icon} {service_name:20} | {health_status:10} | {extra_info}")
                finally:
                    loop.close()
                    
        except Exception as e:
            logger.warning(f"Could not check service health: {e}")
            for service_name in self.services.keys():
                print(f"❓ {service_name:20} | UNKNOWN    | Health check failed")
    
    def show_logs(self, service: Optional[str] = None, lines: int = 50) -> None:
        """Show logs from services."""
        if service:
            if service not in self.services:
                logger.error(f"[ERROR] Unknown service: {service}")
                return
            
            logger.info(f"📋 Showing logs for {service} (last {lines} lines)...")
            command = self._compose_cmd + ['logs', '--tail', str(lines), service]
        else:
            logger.info(f"📋 Showing logs from all services (last {lines} lines each)...")
            command = self._compose_cmd + ['logs', '--tail', str(lines)]
        
        returncode, stdout, stderr = self.run_command(command, capture_output=True)
        
        if returncode == 0:
            print("\n" + "=" * 80)
            print("📋 SERVICE LOGS")
            print("=" * 80)
            print(stdout)
        else:
            logger.error(f"[ERROR] Failed to get logs: {stderr}")
    
    # =================================================================
    # WEBSOCKET COMMUNICATION
    # =================================================================
    
    async def send_websocket_message(self, service_name: str, message: Dict[str, Any], 
                                   timeout: int = 30) -> Dict[str, Any]:
        """Send a message to a service via WebSocket with load balancing and failover.

        Features:
        - Load Balancing: Randomly selects from available replicas (if configured)
        - Failover: Retries on other replicas if connection fails
        - Protocol: Handles progress frames until terminal result
        """
        if service_name not in self.services:
            return {'status': 'error', 'error': f'Unknown service: {service_name}'}
        
        service_info = self.services[service_name]
        
        # Create a shuffled list of URLs for this request to distribute load
        # and provide failover order
        target_urls = list(service_info.urls)
        random.shuffle(target_urls)
        
        last_error = None
        
        for url in target_urls:
            try:
                logger.info(f"Attempting connection to {service_name} at {url}")
                
                async with websockets.connect(
                    url,
                    open_timeout=10,
                    close_timeout=10,
                    ping_interval=None,
                    ping_timeout=None,
                    max_size=100 * 1024 * 1024  # 100 MB for large SARIF responses
                ) as websocket:
                    # Send request
                    await websocket.send(json.dumps(message))

                    deadline = time.time() + timeout
                    first_frame: Optional[Dict[str, Any]] = None
                    terminal_frame: Optional[Dict[str, Any]] = None

                    while time.time() < deadline:
                        remaining = max(0.1, deadline - time.time())
                        try:
                            raw = await asyncio.wait_for(websocket.recv(), timeout=remaining)
                        except asyncio.TimeoutError:
                            break
                        except ConnectionClosed:
                            break
                        try:
                            frame = json.loads(raw)
                        except Exception:
                            frame = {'status': 'error', 'error': 'invalid_json_frame', 'raw': raw}

                        if first_frame is None:
                            first_frame = frame

                        ftype = str(frame.get('type','')).lower()
                        has_analysis = isinstance(frame.get('analysis'), dict)
                        logger.debug(
                            f"WebSocket frame from {service_name} ({url}): type={ftype} "
                            f"has_analysis={has_analysis} status={frame.get('status')} "
                            f"keys={list(frame.keys())[:5]}"
                        )
                        
                        # Heuristic: treat *_analysis_result or *_analysis (with status) as terminal
                        if ('analysis_result' in ftype) or (ftype.endswith('_analysis') and 'analysis' in frame):
                            terminal_frame = frame
                            # Break only if it already contains nested 'analysis' key to avoid prematurely
                            # returning a progress-like message that happens to match pattern.
                            if has_analysis:
                                logger.debug(f"Found terminal frame with analysis data from {service_name}")
                                break
                    
                    # Log what we're returning
                    result_type = 'terminal' if terminal_frame else ('first' if first_frame else 'no_response')
                    logger.debug(f"Returning {result_type} frame from {service_name} ({url})")
                    
                    # Store result and RETURN immediately on success (no retry needed)
                    result = terminal_frame or first_frame or {'status': 'error', 'error': 'no_response'}
                    
                    # If we got a valid response (even an error response from the service logic), consider it a success
                    # connectivity-wise. Only network errors trigger failover.
                    return result
                    
            except (asyncio.TimeoutError, ConnectionClosed, OSError, IOError) as e:
                last_error = e
                logger.warning(f"Connection failed to {service_name} at {url}: {e}. Retrying with next replica...")
                continue
            except Exception as e:
                # Unexpected errors shouldn't necessarily trigger retry unless we're sure it's transient
                logger.error(f"Unexpected error communicating with {service_name} at {url}: {e}")
                last_error = e
                continue

        # If we exhausted all URLs
        logger.error(f"All replicas failed for {service_name}. URLs tried: {target_urls}")
        return {'status': 'error', 'error': f'All replicas failed for {service_name}: {str(last_error)}'}
    
    async def check_service_health(self, service_name: str) -> Dict[str, Any]:
        """Check health of a specific service."""
        health_message = {
            "type": "health_check",
            "timestamp": datetime.now().isoformat(),
            "id": str(uuid.uuid4())
        }
        
        result = await self.send_websocket_message(service_name, health_message, timeout=10)
        
        # Update service info
        service_info = self.services[service_name]
        service_info.last_check = datetime.now()
        
        if result.get('status') != 'error':
            service_info.health_status = result.get('status', 'unknown')
        else:
            service_info.health_status = 'unhealthy'
        
        return result
    
    async def check_all_services_health(self) -> Dict[str, Dict[str, Any]]:
        """Check health of all services."""
        logger.info("Checking health of all services...")
        
        health_tasks = [
            self.check_service_health(service_name)
            for service_name in self.services.keys()
        ]
        
        results = await asyncio.gather(*health_tasks, return_exceptions=True)
        
        health_results = {}
        for i, (service_name, result) in enumerate(zip(self.services.keys(), results)):
            if isinstance(result, Exception):
                health_results[service_name] = {
                    'status': 'error',
                    'error': str(result)
                }
            else:
                health_results[service_name] = result
        
        return health_results
    
    async def test_all_services(self) -> Dict[str, Any]:
        """Run comprehensive tests on all services.
        
        Returns detailed test results including:
        - Health check status for each service
        - Ping response times
        - Functional test results
        """
        logger.info("Running comprehensive service tests...")
        
        results = {
            'services': {},
            'summary': {
                'total_services': len(self.services),
                'healthy_services': 0,
                'successful_pings': 0,
                'functional_tests_passed': 0,
                'overall_health': 'unknown'
            }
        }
        
        # Test each service
        for service_name in self.services.keys():
            service_result = {
                'health': 'unknown',
                'ping_ms': None,
                'functional': False,
                'errors': []
            }
            
            # 1. Health check
            try:
                health = await self.check_service_health(service_name)
                service_result['health'] = health.get('status', 'unknown')
                if service_result['health'] == 'healthy':
                    results['summary']['healthy_services'] += 1
            except Exception as e:
                service_result['errors'].append(f"Health check failed: {e}")
            
            # 2. Ping test with timing
            try:
                import time
                start = time.time()
                ping_msg = {
                    "type": "ping",
                    "timestamp": datetime.now().isoformat(),
                    "id": str(uuid.uuid4())
                }
                ping_result = await self.send_websocket_message(service_name, ping_msg, timeout=5)
                elapsed = (time.time() - start) * 1000
                service_result['ping_ms'] = round(elapsed, 2)
                if ping_result.get('status') != 'error':
                    results['summary']['successful_pings'] += 1
            except Exception as e:
                service_result['errors'].append(f"Ping failed: {e}")
            
            # 3. Functional test (service-specific)
            try:
                func_result = await self._test_service_function(service_name)
                service_result['functional'] = func_result.get('success', False)
                if service_result['functional']:
                    results['summary']['functional_tests_passed'] += 1
                if func_result.get('error'):
                    service_result['errors'].append(func_result['error'])
            except Exception as e:
                service_result['errors'].append(f"Functional test failed: {e}")
            
            results['services'][service_name] = service_result
        
        # Determine overall health
        total = results['summary']['total_services']
        healthy = results['summary']['healthy_services']
        if healthy == total:
            results['summary']['overall_health'] = 'healthy'
        elif healthy >= total / 2:
            results['summary']['overall_health'] = 'degraded'
        else:
            results['summary']['overall_health'] = 'unhealthy'
        
        return results
    
    async def _test_service_function(self, service_name: str) -> Dict[str, Any]:
        """Run a minimal functional test for a specific service."""
        # Send a capabilities/info request to verify service is responding properly
        test_msg = {
            "type": "get_capabilities",
            "timestamp": datetime.now().isoformat(),
            "id": str(uuid.uuid4())
        }
        
        try:
            result = await self.send_websocket_message(service_name, test_msg, timeout=10)
            if result.get('status') == 'error':
                return {'success': False, 'error': result.get('error')}
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _test_service_ping(self, service_name: str) -> Dict[str, Any]:
        """Test service ping with response time measurement."""
        import time
        start = time.time()
        
        ping_msg = {
            "type": "ping",
            "timestamp": datetime.now().isoformat(),
            "id": str(uuid.uuid4())
        }
        
        try:
            result = await self.send_websocket_message(service_name, ping_msg, timeout=10)
            elapsed = time.time() - start
            
            if result.get('status') == 'error':
                return {'status': 'error', 'error': result.get('error')}
            return {'status': 'success', 'response_time': elapsed}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    # =================================================================
    # ANALYSIS OPERATIONS
    # =================================================================
    
    async def run_security_analysis(self, model_slug: str, app_number: int, 
                                  tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run security analysis on an application."""
        # Only apply defaults when tools is explicitly None. Respect provided selections.
        if tools is None:
            tools = ['bandit', 'safety', 'semgrep']
        
        logger.info(f"🔒 Running security analysis on {model_slug} app {app_number}")
        
        request = AnalysisRequest(
            model_slug=model_slug,
            app_number=app_number,
            analysis_type='security_analysis',
            options={'tools': tools}
        )
        
        message = {
            "type": "static_analyze",
            "model_slug": model_slug,
            "app_number": app_number,
            "source_path": request.source_path,
            "tools": tools,
            "timestamp": datetime.now().isoformat(),
            "id": str(uuid.uuid4())
        }
        # Allow longer runtime for comprehensive static/security scans.
        # Default to 480s and allow override via env.
        security_timeout = int(os.environ.get('SECURITY_ANALYSIS_TIMEOUT', os.environ.get('STATIC_ANALYSIS_TIMEOUT', '480')))
        return await self.send_websocket_message('static-analyzer', message, timeout=security_timeout)

    async def run_dynamic_analysis(self, model_slug: str, app_number: int,
                                  target_urls: Optional[List[str]] = None,
                                  tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run dynamic analysis against running app endpoints."""
        logger.info(f"🕷️  Running dynamic analysis on {model_slug} app {app_number}")
        
        # Validate app exists and normalize slug
        validation = self._normalize_and_validate_app(model_slug, app_number)
        if isinstance(validation, dict):
            # Validation returned an error dict
            return validation
        normalized_slug, app_path = validation
        
        resolved_urls: List[str] = []
        if target_urls:
            resolved_urls = list(target_urls)
        else:
            ports = self._resolve_app_ports(normalized_slug, app_number)
            if not ports:
                return {
                    'status': 'error',
                    'error': f'No port configuration found for {normalized_slug} app{app_number}',
                    'message': 'Start the app with docker-compose or configure ports in database'
                }
            
            backend_port, frontend_port = ports
            # Use Docker container names for container-to-container communication
            # Container names follow pattern: {model_slug}-app{N}_backend/frontend
            # The containers are on thesis-apps-network, same as analyzers
            # Note: Docker Compose converts underscores to hyphens in container names
            safe_slug = normalized_slug.replace('_', '-').replace('.', '-')
            container_prefix = f"{safe_slug}-app{app_number}"
            resolved_urls = [
                f"http://{container_prefix}_backend:{backend_port}",
                f"http://{container_prefix}_frontend:80"  # nginx serves on port 80 inside container
            ]
            logger.info(f"Target URLs for dynamic analysis: {resolved_urls}")
        
        message = {
            "type": "dynamic_analyze",
            "model_slug": normalized_slug,
            "app_number": app_number,
            "target_urls": resolved_urls,
            # Optional tools selection propagated to service for gating
            "tools": tools,
            "timestamp": datetime.now().isoformat(),
            "id": str(uuid.uuid4())
        }

        return await self.send_websocket_message('dynamic-analyzer', message, timeout=300)
    
    async def run_performance_test(self, model_slug: str, app_number: int,
                                 target_url: Optional[str] = None, users: int = 10, 
                                 duration: int = 60, tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run performance test on an application."""
        logger.info(f"⚡ Running performance test on {model_slug} app {app_number}")
        
        # Validate app exists and normalize slug
        validation = self._normalize_and_validate_app(model_slug, app_number)
        if isinstance(validation, dict):
            # Validation returned an error dict
            return validation
        normalized_slug, app_path = validation
        
        # New behavior: send explicit target_urls list derived from port config when available.
        urls: List[str] = []
        if target_url:
            urls.append(target_url)
        else:
            ports = self._resolve_app_ports(normalized_slug, app_number)
            if not ports:
                return {
                    'status': 'error',
                    'error': f'No port configuration found for {normalized_slug} app{app_number}',
                    'message': 'Start the app with docker-compose or configure ports in database'
                }
            
            backend_port, frontend_port = ports
            # Use Docker container names for container-to-container communication
            # Container names follow pattern: {model_slug}-app{N}_backend/frontend
            # The containers are on thesis-apps-network, same as analyzers
            # Note: Docker Compose converts underscores AND dots to hyphens in container names
            safe_slug = normalized_slug.replace('_', '-').replace('.', '-')
            container_prefix = f"{safe_slug}-app{app_number}"
            urls = [
                f"http://{container_prefix}_backend:{backend_port}",
                f"http://{container_prefix}_frontend:80"  # nginx serves on port 80 inside container
            ]
            logger.info(f"Target URLs for performance test: {urls}")
        
        # Backwards compatible: we still include legacy 'target_url' key (first url or None)
        legacy_single = urls[0] if urls else target_url
        if not legacy_single:
            return {
                'status': 'error',
                'error': 'No target URL available',
                'message': 'Could not determine target URL for performance test'
            }
        
        message = {
            "type": "performance_test",
            "model_slug": normalized_slug,
            "app_number": app_number,
            "target_url": legacy_single,  # legacy field (service ignores if target_urls present)
            "target_urls": urls,
            "users": users,
            "duration": duration,
            # Optional tools selection propagated to service for gating
            "tools": tools,
            "timestamp": datetime.now().isoformat(),
            "id": str(uuid.uuid4())
        }
        
        # Use longer timeout for performance tests since they can take a while
        # Use environment variable if set, otherwise calculate based on duration
        perf_timeout = int(os.environ.get('PERFORMANCE_TIMEOUT', str(max(duration * 2 + 300, 600))))
        raw_result = await self.send_websocket_message('performance-tester', message, timeout=perf_timeout)
        # Normalization layer: we expect wrapped frame with 'analysis' dict. If missing, coerce.
        try:
            if isinstance(raw_result, dict):
                # Case 1: Already wrapped (preferred)
                if 'analysis' in raw_result and isinstance(raw_result['analysis'], dict):
                    return raw_result
                # Case 2: Service may have returned the inner analysis directly.
                # Heuristic: presence of keys typical of analysis payload.
                indicative_keys = {'tools_used','results','model_slug','app_number'}
                if indicative_keys.intersection(raw_result.keys()):
                    wrapped = {
                        'type': 'performance_analysis_result',
                        'status': raw_result.get('status','success' if raw_result.get('tools_used') else 'unknown'),
                        'service': 'performance-tester',
                        'analysis': raw_result,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    return wrapped
                # Case 3: Progress frame only; fabricate minimal analysis so downstream save doesn't break.
                if raw_result.get('type','').startswith('aiohttp_') or raw_result.get('type','').endswith('_start'):
                    fabricated = {
                        'type': 'performance_analysis_result',
                        'status': 'error',
                        'service': 'performance-tester',
                        'analysis': {
                            'model_slug': model_slug,
                            'app_number': app_number,
                            'status': 'error',
                            'error': 'final performance result not received',
                            'tools_used': [],
                            'results': {'tool_runs': {}},
                        },
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    return fabricated
        except Exception as e:
            logger.debug(f"Performance result normalization failed: {e}")
        return raw_result
    
    def _detect_template_from_app(self, model_slug: str, app_number: int) -> Optional[str]:
        """Detect template_slug from app payload files or code analysis.
        
        Same logic as AI analyzer's _detect_template_from_app for consistency.
        """
        import json
        from pathlib import Path
        
        # Template patterns: keywords that indicate specific templates
        template_patterns = {
            'api_url_shortener': [
                'url shortener', 'shorten url', 'short_code', 'original_url',
                '/api/shorten', '/shorten', 'shortcode', 'click_count'
            ],
            'api_weather_display': [
                'weather', 'temperature', 'forecast', 'humidity', 
                'weather api', 'weather data', 'openweathermap'
            ],
            'auth_user_login': [
                'user login', 'authentication', 'login system', 'auth system',
                'user management', 'register user', '/api/auth/login'
            ],
            'crud_todo_list': [
                'todo list', 'todo app', 'task list', 'task manager',
                '/api/todos', 'completed', 'due_date', 'todo item'
            ],
            'crud_book_library': [
                'book library', 'library system', 'book management',
                '/api/books', 'author', 'isbn', 'borrower'
            ],
            'realtime_chat_room': [
                'chat room', 'real-time chat', 'chat application',
                'websocket', 'socket.io', 'chat message', '/chat'
            ],
            'ecommerce_shopping_cart': [
                'shopping cart', 'e-commerce', 'ecommerce', 'cart items',
                '/api/cart', 'add to cart', 'checkout', 'product'
            ],
            'booking_reservations': [
                'reservation', 'booking system', 'book appointment',
                '/api/booking', 'schedule', 'availability', 'time slot'
            ],
        }
        
        # Method 1: Read from payload files
        try:
            base_path = Path(__file__).parent.parent / "generated" / "raw" / "payloads" / model_slug / f"app{app_number}"
            if base_path.exists():
                payload_files = sorted(base_path.glob("*_backend_*_payload.json"), reverse=True)
                if not payload_files:
                    payload_files = sorted(base_path.glob("*_payload.json"), reverse=True)
                
                for payload_file in payload_files[:1]:
                    try:
                        with open(payload_file, 'r', encoding='utf-8') as f:
                            payload_data = json.load(f)
                        
                        messages = payload_data.get('payload', {}).get('messages', [])
                        prompt_text = ""
                        for msg in messages:
                            content = msg.get('content', '')
                            if isinstance(content, str):
                                prompt_text += content.lower() + " "
                        
                        for template_slug, patterns in template_patterns.items():
                            match_count = sum(1 for p in patterns if p in prompt_text)
                            if match_count >= 2:
                                logger.info(f"Detected template '{template_slug}' from payload ({match_count} matches)")
                                return template_slug
                    except Exception as e:
                        logger.debug(f"Could not read payload file: {e}")
        except Exception as e:
            logger.debug(f"Payload-based template detection failed: {e}")
        
        # Method 2: Analyze app code
        try:
            base_path = Path(__file__).parent.parent / "generated" / "apps" / model_slug / f"app{app_number}"
            if base_path.exists():
                code_content = ""
                for py_file in (base_path / "backend").rglob("*.py"):
                    if any(x in str(py_file) for x in ['__pycache__', 'venv']):
                        continue
                    try:
                        code_content += py_file.read_text(encoding='utf-8', errors='ignore').lower() + " "
                    except:
                        pass
                
                best_match = None
                best_score = 0
                for template_slug, patterns in template_patterns.items():
                    match_count = sum(1 for p in patterns if p in code_content)
                    if match_count > best_score and match_count >= 2:
                        best_score = match_count
                        best_match = template_slug
                
                if best_match:
                    logger.info(f"Detected template '{best_match}' from code ({best_score} matches)")
                    return best_match
        except Exception as e:
            logger.debug(f"Code-based template detection failed: {e}")
        
        return None
    
    def _resolve_ai_config(self, model_slug: str, app_number: int, 
                          tools: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Resolve AI analyzer configuration including template_slug and ports.
        
        This is a synchronous helper for task_execution_service to get AI config
        without running the full async analysis.
        
        Returns:
            Dict with template_slug, backend_port, frontend_port, or None on failure
        """
        try:
            template_slug = None
            
            # Try to get template_slug from database
            try:
                import sys
                from pathlib import Path
                
                # Add src to path if not already there
                src_path = Path(__file__).parent.parent / 'src'
                if str(src_path) not in sys.path:
                    sys.path.insert(0, str(src_path))
                
                from app.models import GeneratedApplication
                from flask import current_app
                
                # Use existing app context if available
                app_record = GeneratedApplication.query.filter_by(
                    model_slug=model_slug,
                    app_number=app_number
                ).order_by(GeneratedApplication.version.desc()).first()
                
                if app_record and app_record.template_slug:
                    template_slug = app_record.template_slug
                    logger.info(f"Found template_slug from database: {template_slug}")
            except Exception as e:
                logger.debug(f"Could not query database for template_slug: {e}")
            
            # Smart detection from payload files or code analysis
            if not template_slug:
                detected = self._detect_template_from_app(model_slug, app_number)
                if detected:
                    template_slug = detected
                    logger.info(f"Using auto-detected template: {template_slug}")
            
            # Final fallback
            if not template_slug:
                template_slug = 'crud_todo_list'
                logger.warning(f"Using default template_slug: {template_slug}")
            
            # Resolve ports
            # Resolve ports
            ports_tuple = self._resolve_app_ports(model_slug, app_number)
            if ports_tuple:
                backend_port, frontend_port = ports_tuple
            else:
                logger.warning(f"Could not resolve ports for {model_slug}/app{app_number} - checking DB config")
                # Fallback: Check if ports are in DB even if valid environment wasn't found
                # This covers cases where app isn't running but DB has allocation
                try:
                    from app.models import PortConfiguration
                    pc = PortConfiguration.query.filter_by(model=model_slug, app_num=app_number).first()
                    if pc:
                        backend_port = pc.backend_port
                        frontend_port = pc.frontend_port
                        logger.info(f"Resolved ports from DB: backend={backend_port}, frontend={frontend_port}")
                    else:
                        logger.error(f"Failed to resolve ports for {model_slug}/app{app_number} (no env, no DB entry)")
                        return None
                except Exception as db_err:
                    logger.error(f"Database lookup failed: {db_err}")
                    return None
            
            return {
                "template_slug": template_slug,
                "backend_port": backend_port,
                "frontend_port": frontend_port,
                "gemini_model": "anthropic/claude-3-5-haiku"
            }
        except Exception as e:
            logger.error(f"Failed to resolve AI config: {e}")
            return None
    
    async def run_ai_analysis(self, model_slug: str, app_number: int,
                            ai_model: Optional[str] = None, tools: Optional[List[str]] = None,
                            template_slug: Optional[str] = None) -> Dict[str, Any]:
        """Run AI-powered code analysis with template-based requirements.
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            ai_model: AI model to use (default: anthropic/claude-3-5-haiku)
            tools: List of tools to run (default: ['requirements-scanner', 'code-quality-analyzer'])
            template_slug: Template slug (optional, will query DB if not provided)
        
        Returns:
            Analysis results from ai-analyzer service
        """
        logger.info(f"🤖 Running AI analysis on {model_slug} app {app_number}")
        
        # Determine template_slug: from parameter, DB, smart detection, or fallback
        if not template_slug:
            # Try to get template_slug from database
            try:
                # Import here to avoid circular dependencies
                import sys
                from pathlib import Path
                
                # Add src to path if not already there
                src_path = Path(__file__).parent.parent / 'src'
                if str(src_path) not in sys.path:
                    sys.path.insert(0, str(src_path))
                
                from app.models import GeneratedApplication
                from app import create_app
                
                # Get Flask app and database session
                flask_app = create_app()
                with flask_app.app_context():
                    app_record = GeneratedApplication.query.filter_by(
                        model_slug=model_slug,
                        app_number=app_number
                    ).order_by(GeneratedApplication.version.desc()).first()
                    
                    if app_record and app_record.template_slug:
                        template_slug = app_record.template_slug
                        logger.info(f"Found template_slug from database: {template_slug}")
            except Exception as e:
                logger.debug(f"Could not query database for template_slug: {e}")
            
            # Smart detection from payload files or code analysis if DB doesn't have it
            if not template_slug:
                detected = self._detect_template_from_app(model_slug, app_number)
                if detected:
                    template_slug = detected
                    logger.info(f"Using auto-detected template: {template_slug}")
            
            # Final fallback
            if not template_slug:
                logger.warning(f"No template_slug detected for {model_slug}/app{app_number}, using default")
                template_slug = 'crud_todo_list'
        
        # Resolve port configuration
        ports_tuple = self._resolve_app_ports(model_slug, app_number)
        if ports_tuple:
            backend_port, frontend_port = ports_tuple
        else:
            logger.error(f"Could not resolve ports for {model_slug}/app{app_number}")
            return {
                'status': 'error',
                'error': f'Port resolution failed for {model_slug}/app{app_number}',
                'message': 'Application ports could not be determined. App may not be generated correctly.'
            }
        
        request = AnalysisRequest(
            model_slug=model_slug,
            app_number=app_number,
            analysis_type='ai_analysis'
        )
        
        # Default tools for template-based analysis - include both requirements scanner and quality analyzer
        if tools is None:
            tools = ['requirements-scanner', 'code-quality-analyzer']  # Both AI analysis tools by default
        
        message = {
            "type": "ai_analyze",
            "model_slug": model_slug,
            "app_number": app_number,
            "source_path": request.source_path,
            "tools": tools,
            "config": {
                "template_slug": template_slug,
                "backend_port": backend_port,
                "frontend_port": frontend_port,
                "gemini_model": ai_model or "anthropic/claude-3-5-haiku"
            },
            "timestamp": datetime.now().isoformat(),
            "id": str(uuid.uuid4())
        }
        
        logger.info(f"AI analysis config: template={template_slug}, tools={tools}, ports={backend_port}/{frontend_port}")
        
        return await self.send_websocket_message('ai-analyzer', message, timeout=900)
    
    async def run_static_analysis(self, model_slug: str, app_number: int, 
                                 tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run static code analysis."""
        # Only apply defaults when tools is explicitly None. Respect provided selections.
        if tools is None:
            # Include ALL available static analysis tools (including security tools)
            tools = ['bandit', 'safety', 'pip-audit', 'semgrep', 'detect-secrets',  # Security/CVE tools
                    'pylint', 'flake8', 'mypy', 'vulture', 'ruff', 'radon',  # Python static analysis
                    'eslint', 'jshint', 'npm-audit', 'snyk', 'stylelint']  # JavaScript/CSS tools
        logger.info(f"[SEARCH] Running static analysis on {model_slug} app {app_number}")
        
        request = AnalysisRequest(
            model_slug=model_slug,
            app_number=app_number,
            analysis_type='static_analysis',
            options={'tools': tools}
        )
        
        message = {
            "type": "static_analyze",
            "model_slug": model_slug,
            "app_number": app_number,
            "source_path": request.source_path,
            "tools": tools,
            "timestamp": datetime.now().isoformat(),
            "id": str(uuid.uuid4())
        }
        # Static analysis can take several minutes depending on project size; extend timeout.
        static_timeout = int(os.environ.get('STATIC_ANALYSIS_TIMEOUT', '480'))
        return await self.send_websocket_message('static-analyzer', message, timeout=static_timeout)

    async def run_dynamic_analysis(self, model_slug: str, app_number: int,
                                  target_urls: Optional[List[str]] = None,
                                  tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run dynamic analysis against running app endpoints."""
        logger.info(f"🕷️  Running dynamic analysis on {model_slug} app {app_number}")
        
        # Validate app exists and normalize slug
        validation = self._normalize_and_validate_app(model_slug, app_number)
        if isinstance(validation, dict):
            # Validation returned an error dict
            return validation
        normalized_slug, app_path = validation
        
        resolved_urls: List[str] = []
        if target_urls:
            resolved_urls = list(target_urls)
        else:
            ports = self._resolve_app_ports(normalized_slug, app_number)
            if not ports:
                return {
                    'status': 'error',
                    'error': f'No port configuration found for {normalized_slug} app{app_number}',
                    'message': 'Start the app with docker-compose or configure ports in database'
                }
            
            backend_port, frontend_port = ports
            # Use Docker container names for container-to-container communication
            # Container names follow pattern: {model_slug}-app{N}_backend/frontend
            # The containers are on thesis-apps-network, same as analyzers
            # Note: Docker Compose converts underscores to hyphens in container names
            safe_slug = normalized_slug.replace('_', '-').replace('.', '-')
            container_prefix = f"{safe_slug}-app{app_number}"
            resolved_urls = [
                f"http://{container_prefix}_backend:{backend_port}",
                f"http://{container_prefix}_frontend:80"  # nginx serves on port 80 inside container
            ]
            logger.info(f"Target URLs for dynamic analysis: {resolved_urls}")
        
        message = {
            "type": "dynamic_analyze",
            "model_slug": normalized_slug,
            "app_number": app_number,
            "target_urls": resolved_urls,
            # Optional tools selection propagated to service for gating
            "tools": tools,
            "timestamp": datetime.now().isoformat(),
            "id": str(uuid.uuid4())
        }
        
        # Dynamic analysis can be long
        dynamic_timeout = int(os.environ.get('DYNAMIC_ANALYSIS_TIMEOUT', '300'))
        return await self.send_websocket_message('dynamic-analyzer', message, timeout=dynamic_timeout)
    
    async def run_performance_test(self, model_slug: str, app_number: int,
                                 test_config: Optional[Dict[str, Any]] = None,
                                 tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run performance test on an application."""
        logger.info(f"⚡ Running performance test on {model_slug} app {app_number}")
        
        # Validate app exists and normalize slug
        validation = self._normalize_and_validate_app(model_slug, app_number)
        if isinstance(validation, dict):
            # Validation returned an error dict
            return validation
        normalized_slug, app_path = validation
        
        # Check config for overrides
        config = test_config or {}
        target_url = config.get('target_url')
        
        # Resolve target URLs
        urls: List[str] = []
        if target_url:
            urls.append(target_url)
        else:
            ports = self._resolve_app_ports(normalized_slug, app_number)
            if not ports:
                return {
                    'status': 'error',
                    'error': f'No port configuration found for {normalized_slug} app{app_number}',
                    'message': 'Start the app with docker-compose or configure ports in database'
                }
            
            backend_port, frontend_port = ports
            # Use Docker container names for container-to-container communication
            safe_slug = normalized_slug.replace('_', '-').replace('.', '-')
            container_prefix = f"{safe_slug}-app{app_number}"
            urls = [
                f"http://{container_prefix}_backend:{backend_port}",
                f"http://{container_prefix}_frontend:80"
            ]
            logger.info(f"Target URLs for performance test: {urls}")

        message = {
            "type": "performance_test",
            "model_slug": normalized_slug,
            "app_number": app_number,
            "target_urls": urls,
            "tools": tools,
            "config": config,
            "timestamp": datetime.now().isoformat(),
            "id": str(uuid.uuid4())
        }
        
        perf_timeout = int(os.environ.get('PERFORMANCE_TEST_TIMEOUT', '600'))
        return await self.send_websocket_message('performance-tester', message, timeout=perf_timeout)
    
    async def run_comprehensive_analysis(self, model_slug: str, app_number: int, task_name: Optional[str] = None, tools: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """Run comprehensive analysis (static, performance, dynamic, AI).
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            task_name: Optional task name for results folder
            tools: Optional list of specific tools to run. If None, runs all available tools.
        """
        logger.info(f"[ANALYZE] Running comprehensive analysis on {model_slug} app {app_number}")
        if tools:
            logger.info(f"[ANALYZE] Tool filter applied: {tools}")

        # Run all analysis types including AI
        # Pass tools parameter to all analysis services so they can filter execution
        analysis_tasks = [
            ('static', self.run_static_analysis(model_slug, app_number, tools=tools)),
            ('performance', self.run_performance_test(model_slug, app_number, tools=tools)),
            ('dynamic', self.run_dynamic_analysis(model_slug, app_number, tools=tools)),
            ('ai', self.run_ai_analysis(model_slug, app_number, tools=tools)),
        ]
        
        results = {}

        for analysis_type, task in analysis_tasks:
            try:
                logger.info(f"Starting {analysis_type} analysis...")
                result = await task
                results[analysis_type] = result

                status = result.get('status', 'unknown')
                if status == 'success':
                    logger.info(f"[OK] {analysis_type.title()} analysis completed")
                else:
                    logger.warning(f"⚠️ {analysis_type.title()} analysis failed: {result.get('error', 'Unknown error')}")

            except Exception as e:
                logger.error(f"[ERROR] {analysis_type.title()} analysis error: {e}")
                results[analysis_type] = {'status': 'error', 'error': str(e)}

        # Use provided task name or generate timestamp-based name
        if not task_name:
            task_name = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Save consolidated results using the new method
        await self.save_task_results(model_slug, app_number, task_name, results)

        return results
    
    async def run_batch_analysis(self, models_and_apps: List[Tuple[str, int]],
                               analysis_type: str = 'comprehensive') -> Dict[str, Any]:
        """Run batch analysis on multiple applications."""
        logger.info(f"📦 Starting batch {analysis_type} analysis on {len(models_and_apps)} applications")
        
        batch_id = str(uuid.uuid4())
        batch_start = datetime.now()
        batch_results = {
            'batch_id': batch_id,
            'analysis_type': analysis_type,
            'started_at': batch_start.isoformat(),
            'total_apps': len(models_and_apps),
            'results': {},
            'summary': {}
        }
        
        for i, (model_slug, app_number) in enumerate(models_and_apps, 1):
            app_key = f"{model_slug}_app{app_number}"
            logger.info(f"[{i}/{len(models_and_apps)}] Analyzing {app_key}")
            
            try:
                if analysis_type == 'comprehensive':
                    result = await self.run_comprehensive_analysis(model_slug, app_number)
                elif analysis_type == 'security':
                    result = await self.run_security_analysis(model_slug, app_number)
                elif analysis_type == 'ai':
                    result = await self.run_ai_analysis(model_slug, app_number)
                elif analysis_type == 'static':
                    result = await self.run_static_analysis(model_slug, app_number)
                else:
                    result = {'status': 'error', 'error': f'Unknown analysis type: {analysis_type}'}
                
                batch_results['results'][app_key] = result
                
            except Exception as e:
                logger.error(f"[ERROR] Failed to analyze {app_key}: {e}")
                batch_results['results'][app_key] = {'status': 'error', 'error': str(e)}
        
        # Calculate summary
        batch_end = datetime.now()
        batch_results['completed_at'] = batch_end.isoformat()
        batch_results['duration'] = (batch_end - batch_start).total_seconds()
        
        successful = sum(1 for result in batch_results['results'].values() 
                        if isinstance(result, dict) and 
                        (result.get('status') == 'success' or 
                         any(sub_result.get('status') == 'success' 
                            for sub_result in result.values() if isinstance(sub_result, dict))))
        
        batch_results['summary'] = {
            'successful_analyses': successful,
            'failed_analyses': len(models_and_apps) - successful,
            'success_rate': successful / len(models_and_apps) * 100,
            'total_duration': batch_results['duration']
        }
        
        # Save batch results
        await self.save_batch_results(batch_results)
        
        logger.info(f"[OK] Batch analysis completed: {successful}/{len(models_and_apps)} successful")
        return batch_results
    
    # =================================================================
    # RESULTS MANAGEMENT
    # =================================================================
    
    async def save_analysis_results(self, model_slug: str, app_number: int,
                                  analysis_type: str, results: Dict[str, Any]) -> Path:
        """Save analysis results to project-root results/<model>/appN/<container-dir>/<timestamped>.json"""
        # RESULT PERSISTENCE ENABLED: Write per-service results for debugging and traceability

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        container_dir = self._map_analysis_type_to_container_dir(analysis_type)
        out_dir = self.results_dir / model_slug / f"app{app_number}" / container_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        safe_slug = str(model_slug).replace("/", "_").replace("\\", "_")
        filename = f"{safe_slug}_app{app_number}_{analysis_type}_{timestamp}.json"
        filepath = out_dir / filename

        results_with_metadata = {
            'metadata': {
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_type': analysis_type,
                'timestamp': datetime.now().isoformat(),
                'analyzer_version': '1.0.0'
            },
            'results': results
        }

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(results_with_metadata, f, indent=2, default=str)
            logger.info(f"[SAVE] Results saved to: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"[ERROR] Failed to save results: {e}")
            raise
    
    async def save_batch_results(self, batch_results: Dict[str, Any]) -> Path:
        """Save batch analysis results to project-root results/batch/"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = (self.results_dir / "batch").resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"batch_analysis_{batch_results['batch_id'][:8]}_{timestamp}.json"
        filepath = out_dir / filename

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(batch_results, f, indent=2, default=str)
            logger.info(f"[SAVE] Batch results saved to: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"[ERROR] Failed to save batch results: {e}")
            raise
    
    def _extract_findings_from_analyzer_result(self, analyzer_name: str, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract findings from a specific analyzer result in a standardized format."""
        findings = []
        
        try:
            # Navigate to the analysis results
            analysis_data = result.get('analysis', {})
            if not isinstance(analysis_data, dict):
                return findings
                
            results_data = analysis_data.get('results', {})
            if not isinstance(results_data, dict):
                return findings
            
            # Handle different analyzer types
            if analyzer_name == 'static':
                findings.extend(self._extract_static_findings(results_data))
            elif analyzer_name == 'dynamic':
                findings.extend(self._extract_dynamic_findings(results_data))
            elif analyzer_name == 'performance':
                findings.extend(self._extract_performance_findings(results_data))
            elif analyzer_name == 'ai':
                findings.extend(self._extract_ai_findings(results_data))
            elif analyzer_name == 'security':
                findings.extend(self._extract_security_findings(results_data))
                
        except Exception as e:
            logger.warning(f"Failed to extract findings from {analyzer_name}: {e}")
            
        return findings
    
    def _extract_static_findings(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract findings from static analysis results."""
        findings = []
        
        # Python tools
        python_results = results.get('python', {})
        if isinstance(python_results, dict):
            logger.debug(f"[STATIC] Found python tools: {list(python_results.keys())}")
            
            # Bandit - try issues first, then SARIF
            bandit = python_results.get('bandit', {})
            if isinstance(bandit, dict):
                issues = bandit.get('issues', [])
                
                # If issues array is empty but SARIF exists, extract from SARIF
                if not issues and bandit.get('sarif'):
                    logger.debug("[STATIC] Bandit: extracting from SARIF")
                    sarif = bandit['sarif']
                    if isinstance(sarif, dict) and 'runs' in sarif:
                        for run in sarif['runs']:
                            for result in run.get('results', []):
                                # Extract Bandit's original severity from properties (HIGH/MEDIUM/LOW)
                                # instead of generic SARIF level (error/warning/note)
                                bandit_props = result.get('properties', {})
                                original_severity = bandit_props.get('issue_severity', result.get('level', 'warning'))
                                findings.append({
                                    'id': f"bandit_{result.get('ruleId', 'unknown')}_{result.get('locations', [{}])[0].get('physicalLocation', {}).get('region', {}).get('startLine', 0)}",
                                    'tool': 'bandit',
                                    'rule_id': result.get('ruleId'),
                                    'severity': self._normalize_severity(original_severity),
                                    'confidence': 'unknown',
                                    'category': 'security',
                                    'type': 'vulnerability',
                                    'file': {
                                        'path': result.get('locations', [{}])[0].get('physicalLocation', {}).get('artifactLocation', {}).get('uri', '').replace('/app/sources/', ''),
                                        'line_start': result.get('locations', [{}])[0].get('physicalLocation', {}).get('region', {}).get('startLine'),
                                        'line_end': result.get('locations', [{}])[0].get('physicalLocation', {}).get('region', {}).get('endLine'),
                                        'column_start': result.get('locations', [{}])[0].get('physicalLocation', {}).get('region', {}).get('startColumn'),
                                        'column_end': result.get('locations', [{}])[0].get('physicalLocation', {}).get('region', {}).get('endColumn')
                                    },
                                    'message': {
                                        'title': result.get('message', {}).get('text', ''),
                                        'description': result.get('message', {}).get('text', ''),
                                        'solution': '',
                                        'references': []
                                    },
                                    'evidence': {
                                        'code_snippet': result.get('locations', [{}])[0].get('physicalLocation', {}).get('region', {}).get('snippet', {}).get('text', ''),
                                        'context_lines': 3
                                    },
                                    'metadata': {
                                        'cwe_id': None,
                                        'confidence': 'unknown',
                                        'tags': [result.get('ruleId', '')],
                                        'fix_available': False
                                    }
                                })
                    logger.debug(f"[STATIC] Bandit: extracted {len([f for f in findings if f['tool'] == 'bandit'])} findings from SARIF")
                elif issues:
                    logger.debug(f"[STATIC] Bandit: found {len(issues)} issues")
                    for issue in issues:
                        findings.append({
                            'id': f"bandit_{issue.get('test_id', 'unknown')}_{issue.get('line_number', 0)}",
                            'tool': 'bandit',
                            'rule_id': issue.get('test_id'),
                            'severity': self._normalize_severity(issue.get('issue_severity', 'UNKNOWN')),
                            'confidence': issue.get('issue_confidence', 'UNKNOWN'),
                            'category': 'security',
                            'type': 'vulnerability',
                            'file': {
                                'path': issue.get('filename', '').replace('/app/sources/', ''),
                                'line_start': issue.get('line_number'),
                                'line_end': issue.get('line_number'),
                                'column_start': issue.get('col_offset'),
                                'column_end': issue.get('end_col_offset')
                            },
                            'message': {
                                'title': issue.get('test_name', ''),
                                'description': issue.get('issue_text', ''),
                                'solution': f"See: {issue.get('more_info', '')}",
                                'references': [issue.get('more_info')] if issue.get('more_info') else []
                            },
                            'evidence': {
                                'code_snippet': issue.get('code', ''),
                                'context_lines': 3
                            },
                            'metadata': {
                                'cwe_id': f"CWE-{issue.get('issue_cwe', {}).get('id', '')}" if issue.get('issue_cwe') else None,
                                'confidence': issue.get('issue_confidence', '').lower(),
                                'tags': [issue.get('test_name', '')],
                                'fix_available': False
                            }
                        })
            
            # Pylint
            pylint = python_results.get('pylint', {})
            if isinstance(pylint, dict) and pylint.get('issues'):
                for issue in pylint['issues']:
                    findings.append({
                        'id': f"pylint_{issue.get('message-id', 'unknown')}_{issue.get('line', 0)}",
                        'tool': 'pylint',
                        'rule_id': issue.get('message-id'),
                        'severity': self._normalize_severity(issue.get('type', 'UNKNOWN')),
                        'confidence': 'high',
                        'category': 'quality',
                        'type': 'code_quality',
                        'file': {
                            'path': issue.get('path', ''),
                            'line_start': issue.get('line'),
                            'line_end': issue.get('endLine', issue.get('line')),
                            'column_start': issue.get('column'),
                            'column_end': issue.get('endColumn', issue.get('column'))
                        },
                        'message': {
                            'title': issue.get('symbol', ''),
                            'description': issue.get('message', ''),
                            'solution': 'Fix according to pylint guidelines',
                            'references': []
                        },
                        'evidence': {
                            'code_snippet': '',
                            'context_lines': 3
                        },
                        'metadata': {
                            'cwe_id': None,
                            'confidence': 'high',
                            'tags': [issue.get('symbol', '')],
                            'fix_available': False
                        }
                    })
            
            # Semgrep - try issues first, then results, then SARIF
            semgrep = python_results.get('semgrep', {})
            if isinstance(semgrep, dict):
                results_list = semgrep.get('results', [])
                issues_list = semgrep.get('issues', [])
                
                if issues_list:
                    logger.debug(f"[STATIC] Semgrep: found {len(issues_list)} issues in normalized format")
                    for issue in issues_list:
                        findings.append({
                            'id': f"semgrep_{issue.get('rule_id', 'unknown')}_{issue.get('line', 0)}",
                            'tool': 'semgrep',
                            'rule_id': issue.get('rule_id'),
                            'severity': self._normalize_severity(issue.get('severity', 'UNKNOWN')),
                            'confidence': 'medium',
                            'category': issue.get('category', 'security'),
                            'type': 'vulnerability',
                            'file': {
                                'path': issue.get('file', '').replace('/app/sources/', ''),
                                'line_start': issue.get('line'),
                                'line_end': issue.get('line'),
                                'column_start': issue.get('column'),
                                'column_end': None
                            },
                            'message': {
                                'title': issue.get('rule_id', ''),
                                'description': issue.get('message', ''),
                                'solution': issue.get('help_url', ''),
                                'references': [issue.get('help_url')] if issue.get('help_url') else []
                            },
                            'evidence': {
                                'code_snippet': '',
                                'context_lines': 3
                            },
                            'metadata': {
                                'cwe_id': None,
                                'confidence': 'medium',
                                'tags': [issue.get('rule_id', '')],
                                'fix_available': False
                            }
                        })
                # If results array is empty but SARIF exists, extract from SARIF
                elif not results_list and semgrep.get('sarif'):
                    logger.debug("[STATIC] Semgrep: extracting from SARIF")
                    sarif = semgrep['sarif']
                    if isinstance(sarif, dict) and 'runs' in sarif:
                        for run in sarif['runs']:
                            for result in run.get('results', []):
                                findings.append({
                                    'id': f"semgrep_{result.get('ruleId', 'unknown')}_{result.get('locations', [{}])[0].get('physicalLocation', {}).get('region', {}).get('startLine', 0)}",
                                    'tool': 'semgrep',
                                    'rule_id': result.get('ruleId'),
                                    'severity': self._normalize_severity(result.get('level', 'warning')),
                                    'confidence': 'medium',
                                    'category': 'security',
                                    'type': 'vulnerability',
                                    'file': {
                                        'path': result.get('locations', [{}])[0].get('physicalLocation', {}).get('artifactLocation', {}).get('uri', '').replace('/app/sources/', ''),
                                        'line_start': result.get('locations', [{}])[0].get('physicalLocation', {}).get('region', {}).get('startLine'),
                                        'line_end': result.get('locations', [{}])[0].get('physicalLocation', {}).get('region', {}).get('endLine'),
                                        'column_start': result.get('locations', [{}])[0].get('physicalLocation', {}).get('region', {}).get('startColumn'),
                                        'column_end': result.get('locations', [{}])[0].get('physicalLocation', {}).get('region', {}).get('endColumn')
                                    },
                                    'message': {
                                        'title': result.get('ruleId', ''),
                                        'description': result.get('message', {}).get('text', ''),
                                        'solution': '',
                                        'references': []
                                    },
                                    'evidence': {
                                        'code_snippet': result.get('locations', [{}])[0].get('physicalLocation', {}).get('region', {}).get('snippet', {}).get('text', ''),
                                        'context_lines': 3
                                    },
                                    'metadata': {
                                        'cwe_id': None,
                                        'confidence': 'medium',
                                        'tags': [result.get('ruleId', '')],
                                        'fix_available': False
                                    }
                                })
                    logger.debug(f"[STATIC] Semgrep: extracted {len([f for f in findings if f['tool'] == 'semgrep'])} findings from SARIF")
                elif results_list:
                    logger.debug(f"[STATIC] Semgrep: found {len(results_list)} results")
                    for result in results_list:
                        extra = result.get('extra', {})
                        metadata = extra.get('metadata', {})
                        findings.append({
                            'id': f"semgrep_{result.get('check_id', 'unknown')}_{result.get('start', {}).get('line', 0)}",
                            'tool': 'semgrep',
                            'rule_id': result.get('check_id'),
                            'severity': self._normalize_severity(extra.get('severity', 'UNKNOWN')),
                            'confidence': metadata.get('confidence', 'medium'),
                            'category': metadata.get('category', 'security'),
                            'type': 'vulnerability',
                            'file': {
                                'path': result.get('path', '').replace('/app/sources/', ''),
                                'line_start': result.get('start', {}).get('line'),
                                'line_end': result.get('end', {}).get('line'),
                                'column_start': result.get('start', {}).get('col'),
                                'column_end': result.get('end', {}).get('col')
                            },
                            'message': {
                                'title': result.get('check_id', ''),
                                'description': extra.get('message', ''),
                                'solution': extra.get('fix', 'Apply security fix'),
                                'references': metadata.get('references', [])
                            },
                            'evidence': {
                                'code_snippet': '',
                                'context_lines': 3
                            },
                            'metadata': {
                                'cwe_id': metadata.get('cwe', [None])[0] if metadata.get('cwe') else None,
                                'owasp_category': metadata.get('owasp', [None])[0] if metadata.get('owasp') else None,
                                'confidence': metadata.get('confidence', 'medium'),
                                'tags': metadata.get('subcategory', []),
                                'fix_available': bool(extra.get('fix'))
                            }
                        })
            
            # MyPy
            mypy = python_results.get('mypy', {})
            if isinstance(mypy, dict):
                if mypy.get('issues'):
                    for issue in mypy['issues']:
                        findings.append({
                            'id': f"mypy_{issue.get('line', 0)}_{issue.get('column', 0)}",
                            'tool': 'mypy',
                            'rule_id': issue.get('rule', 'type-check'),
                            'severity': self._normalize_severity(issue.get('severity', 'UNKNOWN')),
                            'confidence': 'high',
                            'category': 'quality',
                            'type': 'type_error',
                            'file': {
                                'path': issue.get('file', '').replace('/app/sources/', ''),
                                'line_start': issue.get('line'),
                                'line_end': issue.get('line'),
                                'column_start': issue.get('column'),
                                'column_end': issue.get('column')
                            },
                            'message': {
                                'title': 'Type Error',
                                'description': issue.get('message', ''),
                                'solution': 'Fix type annotations or imports',
                                'references': []
                            },
                            'evidence': {
                                'code_snippet': '',
                                'context_lines': 3
                            },
                            'metadata': {
                                'cwe_id': None,
                                'confidence': 'high',
                                'tags': ['type-error'],
                                'fix_available': False
                            }
                        })
                elif mypy.get('results'):
                    for result in mypy['results']:
                        findings.append({
                            'id': f"mypy_{result.get('line', 0)}_{result.get('column', 0)}",
                            'tool': 'mypy',
                            'rule_id': 'type-check',
                            'severity': self._normalize_severity(result.get('severity', 'UNKNOWN')),
                            'confidence': 'high',
                            'category': 'quality',
                            'type': 'type_error',
                            'file': {
                                'path': result.get('file', ''),
                                'line_start': result.get('line'),
                                'line_end': result.get('line'),
                                'column_start': result.get('column'),
                                'column_end': result.get('column')
                            },
                            'message': {
                                'title': 'Type Error',
                                'description': result.get('message', ''),
                                'solution': 'Fix type annotations or imports',
                                'references': []
                            },
                            'evidence': {
                                'code_snippet': '',
                                'context_lines': 3
                            },
                            'metadata': {
                                'cwe_id': None,
                                'confidence': 'high',
                                'tags': ['type-error'],
                                'fix_available': False
                            }
                        })
            
            # Vulture
            vulture = python_results.get('vulture', {})
            if isinstance(vulture, dict) and vulture.get('results'):
                for result in vulture['results']:
                    # Extract confidence from message if possible
                    confidence = 'medium'
                    msg = result.get('message', '')
                    if 'confidence' in msg:
                        try:
                            conf_val = int(msg.split('confidence')[0].split('(')[-1].strip().replace('%', ''))
                            if conf_val >= 90:
                                confidence = 'high'
                            elif conf_val >= 70:
                                confidence = 'medium'
                            else:
                                confidence = 'low'
                        except:
                            pass

                    findings.append({
                        'id': f"vulture_{result.get('filename', 'unknown')}_{result.get('line', 0)}",
                        'tool': 'vulture',
                        'rule_id': 'unused-code',
                        'severity': 'low',
                        'confidence': confidence,
                        'category': 'quality',
                        'type': 'code_smell',
                        'file': {
                            'path': result.get('filename', '').replace('/app/sources/', ''),
                            'line_start': result.get('line'),
                            'line_end': result.get('line'),
                            'column_start': 0,
                            'column_end': 0
                        },
                        'message': {
                            'title': 'Unused Code',
                            'description': result.get('message', ''),
                            'solution': 'Remove unused code or add # noqa comment if intentional',
                            'references': []
                        },
                        'evidence': {
                            'code_snippet': '',
                            'context_lines': 3
                        },
                        'metadata': {
                            'cwe_id': None,
                            'confidence': confidence,
                            'tags': ['unused-code'],
                            'fix_available': True
                        }
                    })

            # Radon
            radon = python_results.get('radon', {})
            if isinstance(radon, dict) and radon.get('issues'):
                for issue in radon['issues']:
                    findings.append({
                        'id': f"radon_{issue.get('line', 0)}_{issue.get('column', 0)}",
                        'tool': 'radon',
                        'rule_id': 'cyclomatic-complexity',
                        'severity': self._normalize_severity(issue.get('severity', 'low')),
                        'confidence': 'high',
                        'category': 'quality',
                        'type': 'complexity',
                        'file': {
                            'path': issue.get('file', '').replace('/app/sources/', ''),
                            'line_start': issue.get('line'),
                            'line_end': issue.get('end_line', issue.get('line')),
                            'column_start': issue.get('column'),
                            'column_end': None
                        },
                        'message': {
                            'title': 'High Complexity',
                            'description': issue.get('message', ''),
                            'solution': 'Refactor code to reduce complexity',
                            'references': []
                        },
                        'evidence': {
                            'code_snippet': '',
                            'context_lines': 3
                        },
                        'metadata': {
                            'cwe_id': None,
                            'confidence': 'high',
                            'tags': ['complexity'],
                            'fix_available': False,
                            'complexity': issue.get('complexity'),
                            'rank': issue.get('rank')
                        }
                    })

            # Detect Secrets
            secrets = python_results.get('detect-secrets', {})
            if isinstance(secrets, dict) and secrets.get('issues'):
                for issue in secrets['issues']:
                    findings.append({
                        'id': f"detect_secrets_{issue.get('line', 0)}",
                        'tool': 'detect-secrets',
                        'rule_id': 'secret-detection',
                        'severity': 'high',
                        'confidence': 'medium',
                        'category': 'security',
                        'type': 'secret',
                        'file': {
                            'path': issue.get('file', '').replace('/app/sources/', ''),
                            'line_start': issue.get('line'),
                            'line_end': issue.get('line'),
                            'column_start': None,
                            'column_end': None
                        },
                        'message': {
                            'title': 'Potential Secret Detected',
                            'description': issue.get('message', ''),
                            'solution': 'Revoke the secret and use environment variables',
                            'references': []
                        },
                        'evidence': {
                            'code_snippet': '',
                            'context_lines': 3
                        },
                        'metadata': {
                            'cwe_id': 'CWE-798',
                            'confidence': 'medium',
                            'tags': ['secret'],
                            'fix_available': False,
                            'secret_type': issue.get('secret_type')
                        }
                    })

            # Safety
            safety = python_results.get('safety', {})
            if isinstance(safety, dict) and safety.get('vulnerabilities'):
                for vuln in safety['vulnerabilities']:
                    findings.append({
                        'id': f"safety_{vuln.get('vulnerability_id', 'unknown')}_{vuln.get('package_name', 'unknown')}",
                        'tool': 'safety',
                        'rule_id': vuln.get('vulnerability_id'),
                        'severity': self._normalize_severity(vuln.get('severity', 'medium')),
                        'confidence': 'high',
                        'category': 'security',
                        'type': 'dependency_vulnerability',
                        'file': {
                            'path': 'requirements.txt',
                            'line_start': 0,
                            'line_end': 0,
                            'column_start': 0,
                            'column_end': 0
                        },
                        'message': {
                            'title': f"Vulnerability in {vuln.get('package_name', 'unknown')}",
                            'description': vuln.get('advisory', ''),
                            'solution': f"Upgrade {vuln.get('package_name')} to version {vuln.get('fixed_versions', [])}",
                            'references': [vuln.get('more_info_url')] if vuln.get('more_info_url') else []
                        },
                        'evidence': {
                            'code_snippet': f"{vuln.get('package_name')}=={vuln.get('analyzed_version')}",
                            'context_lines': 1
                        },
                        'metadata': {
                            'cwe_id': vuln.get('cwe_id'),
                            'confidence': 'high',
                            'tags': ['dependency'],
                            'fix_available': bool(vuln.get('fixed_versions'))
                        }
                    })

            # pip-audit
            pip_audit = python_results.get('pip-audit', {})
            if isinstance(pip_audit, dict) and pip_audit.get('vulnerabilities'):
                for vuln in pip_audit['vulnerabilities']:
                    # Collect references from aliases and URLs if available
                    references = []
                    if vuln.get('aliases'):
                        references.extend([f"https://osv.dev/vulnerability/{alias}" for alias in vuln.get('aliases')])
                    
                    findings.append({
                        'id': f"pip_audit_{vuln.get('id', 'unknown')}_{vuln.get('package', 'unknown')}",
                        'tool': 'pip-audit',
                        'rule_id': vuln.get('id'),
                        'severity': 'high',
                        'confidence': 'high',
                        'category': 'security',
                        'type': 'dependency_vulnerability',
                        'file': {
                            'path': 'requirements.txt',
                            'line_start': 0,
                            'line_end': 0,
                            'column_start': 0,
                            'column_end': 0
                        },
                        'message': {
                            'title': f"Vulnerability in {vuln.get('package', 'unknown')}",
                            'description': vuln.get('description', ''),
                            'solution': f"Upgrade {vuln.get('package')} to fixed version: {vuln.get('fix_versions', [])}",
                            'references': references
                        },
                        'evidence': {
                            'code_snippet': f"{vuln.get('package')}=={vuln.get('version')}",
                            'context_lines': 1
                        },
                        'metadata': {
                            'cwe_id': None,
                            'confidence': 'high',
                            'tags': ['dependency'] + vuln.get('aliases', []),
                            'fix_available': bool(vuln.get('fix_versions'))
                        }
                    })

            # Ruff
            ruff = python_results.get('ruff', {})
            if isinstance(ruff, dict):
                if ruff.get('issues'):
                    for issue in ruff['issues']:
                        findings.append({
                            'id': f"ruff_{issue.get('rule_id', 'unknown')}_{issue.get('line', 0)}",
                            'tool': 'ruff',
                            'rule_id': issue.get('rule_id'),
                            'severity': self._normalize_severity(issue.get('severity', 'warning')),
                            'confidence': 'high',
                            'category': issue.get('category', 'quality'),
                            'type': 'code_quality',
                            'file': {
                                'path': issue.get('file', '').replace('/app/sources/', ''),
                                'line_start': issue.get('line'),
                                'line_end': issue.get('line'),
                                'column_start': issue.get('column'),
                                'column_end': None
                            },
                            'message': {
                                'title': issue.get('message', ''),
                                'description': issue.get('message', ''),
                                'solution': 'Fix according to Ruff rules',
                                'references': [issue.get('help_url')] if issue.get('help_url') else []
                            },
                            'evidence': {
                                'code_snippet': '',
                                'context_lines': 3
                            },
                            'metadata': {
                                'cwe_id': None,
                                'confidence': 'high',
                                'tags': [issue.get('rule_id', '')],
                                'fix_available': True
                            }
                        })
                # Try SARIF first
                elif ruff.get('sarif'):
                    sarif = ruff['sarif']
                    if isinstance(sarif, dict) and 'runs' in sarif:
                        for run in sarif['runs']:
                            for result in run.get('results', []):
                                findings.append({
                                    'id': f"ruff_{result.get('ruleId', 'unknown')}_{result.get('locations', [{}])[0].get('physicalLocation', {}).get('region', {}).get('startLine', 0)}",
                                    'tool': 'ruff',
                                    'rule_id': result.get('ruleId'),
                                    'severity': self._normalize_severity(result.get('level', 'warning')),
                                    'confidence': 'high',
                                    'category': 'quality',
                                    'type': 'code_quality',
                                    'file': {
                                        'path': result.get('locations', [{}])[0].get('physicalLocation', {}).get('artifactLocation', {}).get('uri', '').replace('/app/sources/', ''),
                                        'line_start': result.get('locations', [{}])[0].get('physicalLocation', {}).get('region', {}).get('startLine'),
                                        'line_end': result.get('locations', [{}])[0].get('physicalLocation', {}).get('region', {}).get('endLine'),
                                        'column_start': result.get('locations', [{}])[0].get('physicalLocation', {}).get('region', {}).get('startColumn'),
                                        'column_end': result.get('locations', [{}])[0].get('physicalLocation', {}).get('region', {}).get('endColumn')
                                    },
                                    'message': {
                                        'title': result.get('message', {}).get('text', ''),
                                        'description': result.get('message', {}).get('text', ''),
                                        'solution': 'Fix according to Ruff rules',
                                        'references': []
                                    },
                                    'evidence': {
                                        'code_snippet': '',
                                        'context_lines': 3
                                    },
                                    'metadata': {
                                        'cwe_id': None,
                                        'confidence': 'high',
                                        'tags': [result.get('ruleId', '')],
                                        'fix_available': True
                                    }
                                })

        # JavaScript/TypeScript tools
        js_results = results.get('javascript', {})
        if isinstance(js_results, dict):
            # ESLint
            eslint = js_results.get('eslint', {})
            if isinstance(eslint, dict):
                if eslint.get('issues'):
                    for issue in eslint['issues']:
                        findings.append({
                            'id': f"eslint_{issue.get('rule_id', 'unknown')}_{issue.get('line', 0)}",
                            'tool': 'eslint',
                            'rule_id': issue.get('rule_id'),
                            'severity': self._normalize_severity(issue.get('severity', 'warning')),
                            'confidence': 'high',
                            'category': issue.get('category', 'quality'),
                            'type': 'code_quality',
                            'file': {
                                'path': issue.get('file', '').replace('/app/sources/', ''),
                                'line_start': issue.get('line'),
                                'line_end': issue.get('line'),
                                'column_start': issue.get('column'),
                                'column_end': None
                            },
                            'message': {
                                'title': issue.get('rule_id', 'ESLint Rule Violation'),
                                'description': issue.get('message', ''),
                                'solution': 'Fix according to ESLint rule documentation.',
                                'references': [issue.get('help_url')] if issue.get('help_url') else []
                            },
                            'evidence': {},
                            'metadata': {
                                'fix_available': True
                            }
                        })
                elif eslint.get('results'):
                    for file_result in eslint['results']:
                        for issue in file_result.get('messages', []):
                            findings.append({
                                'id': f"eslint_{issue.get('ruleId', 'unknown')}_{issue.get('line', 0)}",
                                'tool': 'eslint',
                                'rule_id': issue.get('ruleId'),
                                'severity': self._normalize_severity('error' if issue.get('severity') == 2 else 'warning'),
                                'confidence': 'high',
                                'category': 'quality',
                                'type': 'code_quality',
                                'file': {
                                    'path': file_result.get('filePath', '').replace('/app/sources/', ''),
                                    'line_start': issue.get('line'),
                                    'line_end': issue.get('endLine', issue.get('line')),
                                    'column_start': issue.get('column'),
                                    'column_end': issue.get('endColumn', issue.get('column'))
                                },
                                'message': {
                                    'title': issue.get('ruleId', 'ESLint Rule Violation'),
                                    'description': issue.get('message', ''),
                                    'solution': 'Fix according to ESLint rule documentation.',
                                    'references': []
                                },
                                'evidence': {},
                                'metadata': {
                                    'fix_available': 'fix' in issue
                                }
                            })

            # npm-audit
            npm_audit = js_results.get('npm-audit', {})
            if isinstance(npm_audit, dict) and npm_audit.get('vulnerabilities'):
                vulns = npm_audit['vulnerabilities']
                if isinstance(vulns, dict):
                    for pkg_name, vuln in vulns.items():
                        findings.append({
                            'id': f"npm_audit_{pkg_name}_{vuln.get('severity', 'unknown')}",
                            'tool': 'npm-audit',
                            'rule_id': 'npm-audit-vulnerability',
                            'severity': self._normalize_severity(vuln.get('severity', 'low')),
                            'confidence': 'high',
                            'category': 'security',
                            'type': 'dependency_vulnerability',
                            'file': {
                                'path': 'package.json',
                                'line_start': 0,
                                'line_end': 0,
                                'column_start': 0,
                                'column_end': 0
                            },
                            'message': {
                                'title': f"Vulnerability in {pkg_name}",
                                'description': f"Severity: {vuln.get('severity')}. Fix available: {vuln.get('fixAvailable', False)}",
                                'solution': 'Run npm audit fix',
                                'references': []
                            },
                            'evidence': {
                                'code_snippet': f"{pkg_name}",
                                'context_lines': 1
                            },
                            'metadata': {
                                'cwe_id': None,
                                'confidence': 'high',
                                'tags': ['dependency', 'security'],
                                'fix_available': isinstance(vuln.get('fixAvailable'), (bool, dict))
                            }
                        })
        
        # CSS tools
        css_results = results.get('css', {})
        if isinstance(css_results, dict):
            # Stylelint
            stylelint = css_results.get('stylelint', {})
            if isinstance(stylelint, dict) and stylelint.get('results'):
                for file_result in stylelint['results']:
                    for warning in file_result.get('warnings', []):
                        findings.append({
                            'id': f"stylelint_{warning.get('rule', 'unknown')}_{warning.get('line', 0)}",
                            'tool': 'stylelint',
                            'rule_id': warning.get('rule'),
                            'severity': self._normalize_severity(warning.get('severity', 'warning')),
                            'confidence': 'high',
                            'category': 'quality',
                            'type': 'code_style',
                            'file': {
                                'path': file_result.get('source', '').replace('/app/sources/', ''),
                                'line_start': warning.get('line'),
                                'line_end': warning.get('endLine', warning.get('line')),
                                'column_start': warning.get('column'),
                                'column_end': warning.get('endColumn', warning.get('column'))
                            },
                            'message': {
                                'title': f"Stylelint Rule: {warning.get('rule')}",
                                'description': warning.get('text', ''),
                                'solution': 'Fix according to Stylelint rule documentation.'
                            },
                            'evidence': {},
                            'metadata': {}
                        })

        return findings
    
    def _extract_dynamic_findings(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract findings from dynamic analysis results."""
        findings = []
        
        # Extract from ZAP-style scan
        zap_scan_results = results.get('zap_security_scan', [])
        if isinstance(zap_scan_results, list):
            for scan_result in zap_scan_results:
                if isinstance(scan_result, dict):
                    status = scan_result.get('status')
                    url = scan_result.get('url', 'unknown_url')
                    
                    if status == 'success':
                        # Handle ZAP alerts (alerts_by_risk) nested in scan_results
                        inner_scan_results = scan_result.get('scan_results', {})
                        
                        # If scan_results is empty, check if alerts_by_risk is at top level (legacy/fallback)
                        if not inner_scan_results:
                             alerts_by_risk = scan_result.get('alerts_by_risk', {})
                             if alerts_by_risk:
                                 inner_scan_results = {url: scan_result}

                        for target_url, inner_res in inner_scan_results.items():
                            if not isinstance(inner_res, dict):
                                continue
                                
                            alerts_by_risk = inner_res.get('alerts_by_risk', {})
                            if isinstance(alerts_by_risk, dict):
                                for risk, alerts in alerts_by_risk.items():
                                    for alert in alerts:
                                        findings.append({
                                            'id': f"zap_{alert.get('alert', 'unknown').replace(' ', '_')}_{target_url}",
                                            'tool': 'zap',
                                            'rule_id': alert.get('alert'),
                                            'severity': self._normalize_severity(risk),
                                            'category': 'security',
                                            'type': 'vulnerability',
                                            'file': {'path': target_url},
                                            'message': {
                                                'title': alert.get('alert'),
                                                'description': alert.get('description'),
                                                'solution': alert.get('solution')
                                            },
                                            'metadata': {
                                                'cweid': alert.get('cweid'),
                                                'wascid': alert.get('wascid'),
                                                'evidence': alert.get('evidence')
                                            }
                                        })

                        # Handle legacy vulnerabilities list (if any)
                        vulnerabilities = scan_result.get('vulnerabilities', [])
                        if isinstance(vulnerabilities, list):
                            for vuln in vulnerabilities:
                                if isinstance(vuln, dict):
                                    findings.append({
                                        'id': f"zap_{vuln.get('type', 'unknown').replace(' ', '_')}_{url}",
                                        'tool': 'zap',
                                        'rule_id': vuln.get('type'),
                                        'severity': self._normalize_severity(vuln.get('severity', 'medium')),
                                        'category': 'security',
                                        'type': 'vulnerability',
                                        'file': {'path': url},
                                        'message': {
                                            'title': vuln.get('type'),
                                            'description': vuln.get('description'),
                                            'solution': vuln.get('recommendation')
                                        },
                                        'metadata': {}
                                    })
                    elif status == 'error':
                        findings.append({
                            'id': f"zap_execution_failed_{url}",
                            'tool': 'zap',
                            'rule_id': 'execution-failed',
                            'severity': 'high',
                            'category': 'security',
                            'type': 'tool_failure',
                            'file': {'path': url},
                            'message': {
                                'title': 'ZAP Scan Failed',
                                'description': f"ZAP failed to scan {url}: {scan_result.get('error', 'Unknown error')}",
                                'solution': 'Ensure the application is running and accessible.'
                            },
                            'metadata': {'error': scan_result.get('error')}
                        })

        # Extract from common vulnerability scan
        vuln_scan_results = results.get('vulnerability_scan', [])
        if isinstance(vuln_scan_results, list):
            for scan_result in vuln_scan_results:
                if isinstance(scan_result, dict):
                    status = scan_result.get('status')
                    url = scan_result.get('url', 'unknown_url')
                    
                    if status == 'success':
                        vulnerabilities = scan_result.get('vulnerabilities', [])
                        if isinstance(vulnerabilities, list):
                            for vuln in vulnerabilities:
                                 if isinstance(vuln, dict) and vuln.get('type') == 'exposed_paths':
                                    for path_info in vuln.get('paths', []):
                                        findings.append({
                                            'id': f"curl_exposed_path_{path_info.get('path', '').replace('/', '')}_{url}",
                                            'tool': 'curl',
                                            'rule_id': 'exposed-path',
                                            'severity': self._normalize_severity(vuln.get('severity', 'low')),
                                            'category': 'security',
                                            'type': 'information_disclosure',
                                            'file': {'path': path_info.get('url')},
                                            'message': {
                                                'title': 'Exposed Sensitive Path',
                                                'description': f"The path {path_info.get('path')} was found to be accessible.",
                                                'solution': 'Restrict access to sensitive paths.'
                                            },
                                            'metadata': {'status': path_info.get('status')}
                                        })
                    elif status == 'error':
                        findings.append({
                            'id': f"curl_execution_failed_{url}",
                            'tool': 'curl',
                            'rule_id': 'execution-failed',
                            'severity': 'high',
                            'category': 'security',
                            'type': 'tool_failure',
                            'file': {'path': url},
                            'message': {
                                'title': 'Vulnerability Scan Failed',
                                'description': f"Vulnerability scan failed for {url}: {scan_result.get('error', 'Unknown error')}",
                                'solution': 'Ensure the application is running and accessible.'
                            },
                            'metadata': {'error': scan_result.get('error')}
                        })

        # Extract from port scan
        port_scan_result = results.get('port_scan', {})
        if isinstance(port_scan_result, dict):
            status = port_scan_result.get('status')
            host = port_scan_result.get('host', 'unknown_host')
            
            if status == 'success':
                open_ports = port_scan_result.get('open_ports', [])
                if isinstance(open_ports, list):
                    for port in open_ports:
                        # Example: create a finding for common unencrypted ports like FTP, Telnet
                        if port in [21, 23]:
                             findings.append({
                                'id': f"nmap_insecure_port_{port}_{host}",
                                'tool': 'nmap',
                                'rule_id': 'insecure-port-open',
                                'severity': 'medium',
                                'category': 'security',
                                'type': 'configuration_issue',
                                'file': {'path': f"{host}:{port}"},
                                'message': {
                                    'title': 'Insecure Port Open',
                                    'description': f"Port {port} is open, which may be used for unencrypted communication.",
                                    'solution': f"Ensure that port {port} is firewalled or that communication over it is encrypted."
                                },
                                'metadata': {'port': port}
                            })
            elif status == 'error':
                findings.append({
                    'id': f"nmap_execution_failed_{host}",
                    'tool': 'nmap',
                    'rule_id': 'execution-failed',
                    'severity': 'high',
                    'category': 'security',
                    'type': 'tool_failure',
                    'file': {'path': host},
                    'message': {
                        'title': 'Port Scan Failed',
                        'description': f"Port scan failed for {host}: {port_scan_result.get('error', 'Unknown error')}",
                        'solution': 'Ensure the host is reachable.'
                    },
                    'metadata': {'error': port_scan_result.get('error')}
                })

        return findings
    
    def _extract_performance_findings(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract findings from performance test results."""
        findings = []
        tool_runs = results.get('tool_runs', {})

        # Define thresholds for creating findings
        thresholds = {
            'avg_response_time': 500,  # ms
            'requests_per_second': 20, # req/s
            'failed_requests': 0
        }

        for tool_name, tool_result in tool_runs.items():
            if not isinstance(tool_result, dict) or tool_result.get('status') != 'success':
                continue

            url = tool_result.get('url', 'unknown_url')

            # Normalize metrics across different tools
            failed_requests = 0
            if 'failed_requests' in tool_result:
                failed_requests = tool_result['failed_requests']
            elif 'failures' in tool_result:  # Locust
                failed_requests = tool_result['failures']
            elif 'errors' in tool_result:    # Artillery
                failed_requests = tool_result['errors']

            if failed_requests > thresholds['failed_requests']:
                findings.append({
                    'id': f"perf_{tool_name}_failed_requests_{url}",
                    'tool': tool_name,
                    'rule_id': 'high-failure-rate',
                    'severity': 'high',
                    'category': 'performance',
                    'type': 'availability_issue',
                    'file': {'path': url},
                    'message': {
                        'title': 'High Request Failure Rate',
                        'description': f"{tool_name} reported {failed_requests} failed requests when testing {url}.",
                        'solution': 'Investigate server-side errors or application instability under load.'
                    },
                    'metadata': {'metric': 'failed_requests', 'value': failed_requests}
                })

            # Check for slow response time
            avg_response_time = tool_result.get('avg_response_time')
            if avg_response_time and avg_response_time > thresholds['avg_response_time']:
                findings.append({
                    'id': f"perf_{tool_name}_slow_response_{url}",
                    'tool': tool_name,
                    'rule_id': 'slow-response-time',
                    'severity': 'medium',
                    'category': 'performance',
                    'type': 'performance_issue',
                    'file': {'path': url},
                    'message': {
                        'title': 'Slow Average Response Time',
                        'description': f"Average response time of {avg_response_time:.2f}ms exceeds threshold of {thresholds['avg_response_time']}ms for {url}.",
                        'solution': 'Profile the application endpoint to identify performance bottlenecks.'
                    },
                    'metadata': {'metric': 'avg_response_time', 'value': avg_response_time}
                })

            # Check for low throughput
            rps = tool_result.get('requests_per_second')
            
            # Try to calculate RPS for aiohttp if missing
            if rps is None and tool_name == 'aiohttp':
                requests = tool_result.get('requests')
                raw = tool_result.get('raw', {})
                duration = raw.get('duration')
                if requests and duration and duration > 0:
                    rps = requests / duration

            if rps and rps < thresholds['requests_per_second']:
                findings.append({
                    'id': f"perf_{tool_name}_low_throughput_{url}",
                    'tool': tool_name,
                    'rule_id': 'low-throughput',
                    'severity': 'medium',
                    'category': 'performance',
                    'type': 'performance_issue',
                    'file': {'path': url},
                    'message': {
                        'title': 'Low Throughput (Requests Per Second)',
                        'description': f"Throughput of {rps:.2f} req/s is below the threshold of {thresholds['requests_per_second']} req/s for {url}.",
                        'solution': 'Optimize application code, database queries, or server configuration to handle more concurrent requests.'
                    },
                    'metadata': {'metric': 'requests_per_second', 'value': rps}
                })

        return findings
    
    def _extract_ai_findings(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract findings from AI analysis results.
        
        Supports both:
        - Legacy single-tool format: {analysis: {results: {functional_requirements: [...], ...}}}
        - New multi-tool format: {analysis: {tools: {requirements-scanner: {...}, code-quality-analyzer: {...}}, ...}}
        """
        findings = []
        
        # The AI analyzer service returns its primary data directly, not nested
        # under 'tool_results' like other services. The main content is in 'analysis'.
        analysis_data = results.get('analysis')
        if not analysis_data:
            # Fallback if 'analysis' is not present (maybe it's already the analysis dict?)
            analysis_data = results
        
        # Check for new multi-tool format first
        tools_map = analysis_data.get('tools', {})
        if tools_map and isinstance(tools_map, dict):
            logger.debug(f"[AI-FINDINGS] Processing multi-tool format with {len(tools_map)} tools")
            
            # Process requirements-scanner results (supports both new name and legacy requirements-checker)
            req_scanner = tools_map.get('requirements-scanner', tools_map.get('requirements-checker', {}))
            if req_scanner and req_scanner.get('status') == 'success':
                req_results = req_scanner.get('results', {})
                # Backend requirements (new format) or functional requirements (legacy)
                backend = req_results.get('backend_requirements', req_results.get('functional_requirements', []))
                for item in backend:
                    findings.extend(self._convert_ai_check_to_finding(item, 'backend', 'requirements-scanner'))
                
                # Frontend requirements (new format)
                frontend = req_results.get('frontend_requirements', [])
                for item in frontend:
                    findings.extend(self._convert_ai_check_to_finding(item, 'frontend', 'requirements-scanner'))
                
                # Admin requirements (new format)
                admin = req_results.get('admin_requirements', [])
                for item in admin:
                    findings.extend(self._convert_ai_check_to_finding(item, 'admin', 'requirements-scanner'))
                
                control = req_results.get('control_endpoint_tests', [])
                for item in control:
                    findings.extend(self._convert_ai_check_to_finding(item, 'control', 'requirements-scanner'))
            
            # Process code-quality-analyzer results (supports both new quality_metrics and legacy stylistic_requirements)
            quality_analyzer = tools_map.get('code-quality-analyzer', {})
            if quality_analyzer and quality_analyzer.get('status') == 'success':
                quality_results = quality_analyzer.get('results', {})
                # New format: quality_metrics with scores
                quality_metrics = quality_results.get('quality_metrics', [])
                if quality_metrics:
                    for metric in quality_metrics:
                        if not metric.get('passed', True):
                            findings.extend(self._convert_quality_metric_to_finding(metric, 'code-quality-analyzer'))
                else:
                    # Legacy format: stylistic_requirements
                    stylistic = quality_results.get('stylistic_requirements', [])
                    for item in stylistic:
                        findings.extend(self._convert_ai_check_to_finding(item, 'stylistic', 'code-quality-analyzer'))
            
            if findings:
                logger.info(f"[AI-FINDINGS] Extracted {len(findings)} findings from multi-tool AI analysis")
                return findings
        
        # Legacy single-tool format fallback
        results_data = analysis_data.get('results', {})
        
        # Collect all checks from different categories
        all_checks = []
        
        # 1. Functional Requirements
        functional = results_data.get('functional_requirements', [])
        if functional:
            for item in functional:
                item['_category'] = 'functional'
            all_checks.extend(functional)
            
        # 2. Stylistic Requirements
        stylistic = results_data.get('stylistic_requirements', [])
        if stylistic:
            for item in stylistic:
                item['_category'] = 'stylistic'
            all_checks.extend(stylistic)
            
        # 3. Control Endpoint Tests
        control = results_data.get('control_endpoint_tests', [])
        if control:
            for item in control:
                item['_category'] = 'control'
            all_checks.extend(control)
            
        # Legacy fallback
        legacy = results_data.get('requirement_checks', [])
        if legacy:
            for item in legacy:
                item['_category'] = 'legacy'
            all_checks.extend(legacy)

        if not all_checks:
            logger.warning("Could not find any requirement checks (functional, stylistic, or control) within the results.")
            return []

        tool_name = 'ai-requirements-checker'
        tools_used = analysis_data.get('tools_used', [])
        if tools_used:
            tool_name = tools_used[0]
            
        logger.debug(f"Found {len(all_checks)} total checks from tool '{tool_name}'.")

        for check in all_checks:
            result = check.get('result', {})
            # A finding is generated if the requirement is not met
            if not result.get('met', True):
                requirement_text = check.get('requirement', 'Unknown requirement')
                confidence = result.get('confidence', 'LOW').upper()
                severity = self._normalize_severity(confidence)
                category = check.get('_category', 'general')

                findings.append({
                    'id': f"ai_{category}_{uuid.uuid4().hex[:8]}",
                    'tool': tool_name,
                    'rule_id': f'ai_{category}_requirement_failure',
                    'severity': severity,
                    'category': 'requirements',
                    'type': 'requirement_failure',
                    'file': {'path': 'ai_analysis_report'},
                    'message': {
                        'title': f"Unmet {category.title()} Requirement",
                        'description': f"AI detected that a {category} requirement was not met: {requirement_text.split('::')[0]}",
                        'solution': result.get('explanation', 'No explanation provided.')
                    },
                    'metadata': {
                        'confidence': confidence,
                        'full_requirement': requirement_text
                    }
                })
        
        logger.info(f"Extracted {len(findings)} findings from AI analysis.")
        return findings
    
    def _convert_ai_check_to_finding(self, check: Dict[str, Any], category: str, tool_name: str) -> List[Dict[str, Any]]:
        """Convert a single AI requirement check to a finding if not met.
        
        Args:
            check: The requirement check dict (with 'requirement', 'met', 'confidence', 'explanation')
            category: Category type ('functional', 'stylistic', 'control')
            tool_name: Name of the tool that produced this check
            
        Returns:
            List of findings (empty if requirement met, one finding if not met)
        """
        findings = []
        
        # Get met status - for control tests it's 'passed', for requirements it's 'met'
        is_met = check.get('met', check.get('passed', True))
        
        if not is_met:
            requirement_text = check.get('requirement', check.get('endpoint', 'Unknown requirement'))
            confidence = check.get('confidence', 'LOW')
            if isinstance(confidence, str):
                confidence = confidence.upper()
            else:
                confidence = 'LOW'
            
            severity = self._normalize_severity(confidence)
            explanation = check.get('explanation', check.get('error', 'No explanation provided.'))
            
            findings.append({
                'id': f"ai_{category}_{uuid.uuid4().hex[:8]}",
                'tool': tool_name,
                'rule_id': f'ai_{category}_requirement_failure',
                'severity': severity,
                'category': 'requirements',
                'type': 'requirement_failure',
                'file': {'path': 'ai_analysis_report'},
                'message': {
                    'title': f"Unmet {category.title()} Requirement",
                    'description': f"AI detected that a {category} requirement was not met: {str(requirement_text).split('::')[0]}",
                    'solution': explanation
                },
                'metadata': {
                    'confidence': confidence,
                    'full_requirement': requirement_text
                }
            })
        
        return findings
    
    def _convert_quality_metric_to_finding(self, metric: Dict[str, Any], tool_name: str) -> List[Dict[str, Any]]:
        """Convert a code quality metric to findings if failed.
        
        Args:
            metric: Quality metric dict with 'metric_name', 'score', 'passed', 'confidence', 'findings', 'recommendations'
            tool_name: Name of the tool that produced this metric
            
        Returns:
            List of findings (empty if metric passed, findings list if failed)
        """
        result_findings = []
        
        if metric.get('passed', True):
            return result_findings
        
        metric_name = metric.get('metric_name', 'Unknown Metric')
        score = metric.get('score', 0)
        confidence = metric.get('confidence', 'LOW')
        if isinstance(confidence, str):
            confidence = confidence.upper()
        else:
            confidence = 'LOW'
        
        # Map confidence to severity
        if score < 40:
            severity = 'high'
        elif score < 60:
            severity = 'medium'
        else:
            severity = 'low'
        
        findings_list = metric.get('findings', [])
        recommendations = metric.get('recommendations', [])
        
        # Create one finding per issue in the metric's findings
        for i, finding_text in enumerate(findings_list[:10]):  # Limit to first 10
            result_findings.append({
                'id': f"ai_quality_{metric_name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}",
                'tool': tool_name,
                'rule_id': f'ai_quality_{metric_name.lower().replace(" ", "_")}',
                'severity': severity,
                'category': 'code_quality',
                'type': 'quality_metric_failure',
                'file': {'path': 'ai_analysis_report'},
                'message': {
                    'title': f"Quality Issue: {metric_name}",
                    'description': finding_text,
                    'solution': recommendations[i] if i < len(recommendations) else f"Improve {metric_name} - current score: {score}/100"
                },
                'metadata': {
                    'confidence': confidence,
                    'metric_name': metric_name,
                    'score': score,
                    'weight': metric.get('weight', 1.0)
                }
            })
        
        return result_findings
    
    def _extract_security_findings(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract findings from security analysis results."""
        findings = []
        # TODO: Implement security-specific findings extraction
        return findings
    
    def _normalize_severity(self, severity: str) -> str:
        """Normalize severity levels to standard format.
        
        Uses shared utility if available, otherwise falls back to local implementation.
        """
        if SHARED_UTILS_AVAILABLE:
            return shared_normalize_severity(severity)
        
        # Fallback implementation
        severity_lower = str(severity).lower()
        if severity_lower in ['critical', 'fatal', 'high']:
            return 'high'
        elif severity_lower in ['medium', 'warning', 'warn']:
            return 'medium'
        elif severity_lower in ['low', 'info', 'note']:
            return 'low'
        elif severity_lower in ['error']:
            return 'high'
        else:
            return 'medium'
    
    def _aggregate_findings(self, consolidated_results: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate findings from all analyzers into a comprehensive format.
        
        Uses shared utility when available for consistent results across entry points.
        """
        if SHARED_UTILS_AVAILABLE:
            return shared_aggregate_findings(consolidated_results)
        
        # Fallback implementation for standalone CLI use
        all_findings: List[Dict[str, Any]] = []
        seen_finding_ids: Set[str] = set()  # Track unique finding IDs
        findings_by_tool: Dict[str, int] = {}
        findings_by_severity: Dict[str, int] = {'high': 0, 'medium': 0, 'low': 0}
        tools_used: List[str] = []

        logger.debug(f"[AGGREGATE] Processing {len(consolidated_results)} services")

        for analyzer_name, analyzer_result in consolidated_results.items():
            if not isinstance(analyzer_result, dict):
                logger.debug(f"[AGGREGATE] {analyzer_name}: not a dict, skipping")
                continue

            # Service snapshots have structure: {metadata: {...}, results: {type, status, analysis: {...}}}
            # We need to extract from the 'results' wrapper if present
            service_results = analyzer_result.get('results', analyzer_result)
            if not isinstance(service_results, dict):
                logger.debug(f"[AGGREGATE] {analyzer_name}: no results dict")
                continue

            logger.debug(f"[AGGREGATE] {analyzer_name}: extracting findings from service_results")
            findings = self._extract_findings_from_analyzer_result(analyzer_name, service_results)
            logger.debug(f"[AGGREGATE] {analyzer_name}: extracted {len(findings)} findings")
            
            # Deduplicate findings before adding
            for finding in findings:
                finding_id = finding.get('id')
                if finding_id and finding_id in seen_finding_ids:
                    logger.debug(f"[AGGREGATE] Skipping duplicate finding: {finding_id}")
                    continue
                
                if finding_id:
                    seen_finding_ids.add(finding_id)
                
                all_findings.append(finding)

                # Update stats only for unique findings
                tool = finding.get('tool', 'unknown')
                severity = finding.get('severity', 'medium')
                findings_by_tool[tool] = findings_by_tool.get(tool, 0) + 1
                if severity in findings_by_severity:
                    findings_by_severity[severity] += 1

            analysis_data = service_results.get('analysis', {})
            if isinstance(analysis_data, dict):
                # Collect tools used from the analysis data if available
                used_in_analysis = analysis_data.get('tools_used', [])
                if isinstance(used_in_analysis, list):
                    logger.debug(f"[AGGREGATE] {analyzer_name}: tools_used = {used_in_analysis}")
                    tools_used.extend(t for t in used_in_analysis if t not in tools_used)

        logger.info(f"[AGGREGATE] Total: {len(all_findings)} findings from {len(tools_used)} tools")
        logger.info(f"[AGGREGATE] By tool: {findings_by_tool}")
        logger.info(f"[AGGREGATE] By severity: {findings_by_severity}")

        return {
            'findings_total': len(all_findings),
            'findings_by_tool': findings_by_tool,
            'findings_by_severity': findings_by_severity,
            'tools_executed': sorted(list(set(tools_used) | set(findings_by_tool.keys()))),
            'findings': all_findings
        }

    def _strip_sarif_rules(self, sarif_data: Dict[str, Any]) -> Dict[str, Any]:
        """Strip bulky rule definitions from SARIF to reduce file size.
        
        Uses shared utility if available, otherwise falls back to local implementation.
        
        SARIF 'tool.driver.rules' contains full rule catalog with lengthy descriptions.
        We preserve only: id, name, shortDescription (truncated to 200 chars).
        Always strips rules to minimize file size.
        """
        if SHARED_UTILS_AVAILABLE:
            return shared_strip_sarif(sarif_data)
        
        # Fallback implementation
        if not isinstance(sarif_data, dict):
            return sarif_data
            
        runs = sarif_data.get('runs', [])
        for run in runs:
            if not isinstance(run, dict):
                continue
            tool = run.get('tool', {})
            if not isinstance(tool, dict):
                continue
            driver = tool.get('driver', {})
            if not isinstance(driver, dict):
                continue
            
            rules = driver.get('rules', [])
            if rules:  # Always strip rules to reduce size
                slim_rules = []
                for rule in rules:
                    if not isinstance(rule, dict):
                        continue
                    slim_rule = {'id': rule.get('id', '')}
                    if rule.get('name'):
                        slim_rule['name'] = rule['name']
                    if rule.get('shortDescription'):
                        short_desc = rule['shortDescription']
                        if isinstance(short_desc, dict) and 'text' in short_desc:
                            text = short_desc['text'][:200] if len(short_desc.get('text', '')) > 200 else short_desc['text']
                            slim_rule['shortDescription'] = {'text': text}
                    slim_rules.append(slim_rule)
                driver['rules'] = slim_rules
        
        return sarif_data

    def _extract_sarif_to_files(self, consolidated_results: Dict[str, Any], sarif_dir: Path) -> Dict[str, Any]:
        """Extract SARIF data from service results to separate files.
        
        Uses shared utility if available, otherwise falls back to local implementation.
        
        Returns a copy of consolidated_results with SARIF data replaced by file references.
        Also strips bulky rule definitions before writing to reduce file size.
        """
        if SHARED_UTILS_AVAILABLE:
            return shared_extract_sarif(consolidated_results, sarif_dir)
        
        # Fallback implementation
        services_copy = {}
        
        for service_name, service_result in consolidated_results.items():
            if not isinstance(service_result, dict):
                services_copy[service_name] = service_result
                continue
                
            service_copy = dict(service_result)
            analysis = service_copy.get('analysis', {})
            
            if not isinstance(analysis, dict):
                services_copy[service_name] = service_copy
                continue
                
            analysis_copy = dict(analysis)
            
            # Handle tool_results with SARIF data
            tool_results = analysis_copy.get('tool_results', {})
            if isinstance(tool_results, dict):
                tool_results_copy = {}
                for tool_name, tool_data in tool_results.items():
                    if not isinstance(tool_data, dict):
                        tool_results_copy[tool_name] = tool_data
                        continue
                        
                    tool_copy = dict(tool_data)
                    
                    # Extract SARIF if present
                    if 'sarif' in tool_copy and isinstance(tool_copy['sarif'], dict):
                        sarif_data = self._strip_sarif_rules(tool_copy['sarif'])
                        sarif_filename = f"{tool_name}.sarif.json"
                        sarif_path = sarif_dir / sarif_filename
                        
                        try:
                            with open(sarif_path, 'w', encoding='utf-8') as f:
                                json.dump(sarif_data, f, indent=2, default=str)
                            logger.info(f"Extracted SARIF for {tool_name} to {sarif_filename}")
                            
                            # Replace SARIF data with file reference
                            tool_copy['sarif'] = {"sarif_file": f"sarif/{sarif_filename}"}
                        except Exception as e:
                            logger.error(f"Failed to extract SARIF for {tool_name}: {e}")
                    
                    tool_results_copy[tool_name] = tool_copy
                
                analysis_copy['tool_results'] = tool_results_copy
            
            # Handle nested results structure (static analyzer)
            results = analysis_copy.get('results', {})
            if isinstance(results, dict):
                results_copy = {}
                for category, category_data in results.items():
                    if not isinstance(category_data, dict):
                        results_copy[category] = category_data
                        continue
                        
                    category_copy = {}
                    for tool_name, tool_data in category_data.items():
                        if not isinstance(tool_data, dict):
                            category_copy[tool_name] = tool_data
                            continue
                            
                        tool_copy = dict(tool_data)
                        
                        # Extract SARIF if present
                        if 'sarif' in tool_copy and isinstance(tool_copy['sarif'], dict):
                            sarif_data = self._strip_sarif_rules(tool_copy['sarif'])
                            sarif_filename = f"{tool_name}.sarif.json"
                            sarif_path = sarif_dir / sarif_filename
                            
                            try:
                                with open(sarif_path, 'w', encoding='utf-8') as f:
                                    json.dump(sarif_data, f, indent=2, default=str)
                                logger.info(f"Extracted SARIF for {category}/{tool_name} to {sarif_filename}")
                                
                                # Replace SARIF data with file reference
                                tool_copy['sarif'] = {"sarif_file": f"sarif/{sarif_filename}"}
                            except Exception as e:
                                logger.error(f"Failed to extract SARIF for {category}/{tool_name}: {e}")
                        
                        category_copy[tool_name] = tool_copy
                    
                    results_copy[category] = category_copy
                
                analysis_copy['results'] = results_copy
            
            service_copy['analysis'] = analysis_copy
            services_copy[service_name] = service_copy
        
        return services_copy

    async def save_task_results(self, model_slug: str, app_number: int, task_id: str, consolidated_results: Dict[str, Any]) -> Path:
        """Save consolidated results for a task, aggregate findings, and write universal format."""
        safe_slug = str(model_slug).replace('/', '_').replace('\\', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Group consolidated artefacts under task_<task_id>/ (legacy analysis/* migrated)
        sanitized_task = self._sanitize_task_id(task_id)
        task_dir = self._build_task_output_dir(model_slug, app_number, sanitized_task)
        task_dir.mkdir(parents=True, exist_ok=True)
        
        # Create SARIF directory for separate SARIF files
        sarif_dir = task_dir / 'sarif'
        sarif_dir.mkdir(exist_ok=True)
        
        # Extract SARIF data to separate files before processing
        services_with_sarif_refs = self._extract_sarif_to_files(consolidated_results, sarif_dir)
        
        # Fix double-prefix bug: sanitized_task already starts with 'task_' so don't add it again
        task_part = sanitized_task if sanitized_task.startswith('task_') else f"task_{sanitized_task}"
        filename = f"{safe_slug}_app{app_number}_{task_part}_{timestamp}.json"
        filepath = task_dir / filename

        try:
            # 1. Aggregate findings from all tools (use original consolidated_results for complete data)
            aggregated_findings = self._aggregate_findings(consolidated_results)
            tools_executed = aggregated_findings.get('tools_executed', [])

            # 1b. Build a normalized tool map across services for organized reporting
            normalized_tools = self._collect_normalized_tools(consolidated_results)

            # Derive failed/skipped lists from normalized tool statuses
            tools_failed = []
            tools_skipped = []
            
            # Categorize services by their status - use shared utility when available
            if SHARED_UTILS_AVAILABLE:
                services_succeeded, services_partial, services_unreachable = shared_categorize_services(consolidated_results)
            else:
                # Fallback implementation
                services_unreachable = []
                services_partial = []
                services_succeeded = []
                
                for svc_name, svc_data in consolidated_results.items():
                    if not isinstance(svc_data, dict):
                        continue
                    svc_status = str(svc_data.get('status', 'unknown')).lower()
                    if svc_status in ('targets_unreachable', 'unreachable'):
                        services_unreachable.append(svc_name)
                    elif svc_status in ('partial', 'partial_connectivity', 'partial_success'):
                        services_partial.append(svc_name)
                    elif svc_status in ('success', 'completed', 'no_issues'):
                        services_succeeded.append(svc_name)
            
            for tname, tinfo in normalized_tools.items():
                status = str(tinfo.get('status', 'unknown')).lower()
                if status in ('skipped', 'not_available'):
                    tools_skipped.append(tname)
                elif status not in ('success', 'completed', 'no_issues'):
                    tools_failed.append(tname)
            
            # Determine overall status based on service outcomes - use shared utility when available
            if SHARED_UTILS_AVAILABLE:
                overall_status = shared_determine_status(services_succeeded, services_partial, services_unreachable)
            else:
                # Fallback implementation
                if services_unreachable and not services_succeeded and not services_partial:
                    overall_status = 'targets_unreachable'
                elif services_partial or (services_unreachable and services_succeeded):
                    overall_status = 'partial'
                elif services_succeeded:
                    overall_status = 'completed'
                else:
                    overall_status = 'unknown'

            # 2. Build the full consolidated task metadata dictionary (use services_with_sarif_refs)
            task_metadata = {
                'metadata': {
                    'model_slug': model_slug,
                    'app_number': app_number,
                    'analysis_type': task_id,
                    'timestamp': datetime.now().isoformat() + '+00:00',
                    'analyzer_version': '1.0.0',
                    'module': 'analysis',
                    'version': '1.0'
                },
                'results': {
                    'task': {
                        'task_id': task_id,
                        'analysis_type': task_id,
                        'model_slug': model_slug,
                        'app_number': app_number,
                        'started_at': datetime.now().isoformat(),
                        'completed_at': datetime.now().isoformat()
                    },
                    'summary': {
                        'total_findings': aggregated_findings.get('findings_total'),
                        'services_executed': len(services_succeeded),
                        'services_unreachable': len(services_unreachable),
                        'services_partial': len(services_partial),
                        'tools_executed': len(normalized_tools),
                        'severity_breakdown': aggregated_findings.get('findings_by_severity'),
                        'findings_by_tool': aggregated_findings.get('findings_by_tool'),
                        'tools_used': sorted(list(set(tools_executed) | set(normalized_tools.keys()))),
                        'tools_failed': sorted(tools_failed),
                        'tools_skipped': sorted(tools_skipped),
                        'status': overall_status,
                        'overall_status': overall_status  # For backward compat
                    },
                    # Keep raw per-service payloads, but order consistently for readability
                    # NOW with SARIF extracted to separate files
                    'services': self._ordered_services(services_with_sarif_refs),
                    # Flat, organized view of tools across all services
                    'tools': normalized_tools
                    # NOTE: 'findings' array REMOVED to reduce file size by ~15-20%
                    # Findings are already in services.*.analysis.results - use those directly
                    # Web app updated to read from services/tools instead of top-level findings
                }
            }

            # 3. Save the detailed consolidated JSON file alongside per-service snapshots
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(task_metadata, f, indent=2, default=str)
            logger.info(f"[SAVE] Consolidated task results saved to: {filepath}")
            logger.info(f"[SAVE] SARIF files extracted to: {sarif_dir}")

            self._write_service_snapshots(task_dir, safe_slug, model_slug, app_number, task_id, services_with_sarif_refs)
            self._write_task_manifest(task_dir, filename, model_slug, app_number, task_id, consolidated_results)
            self._remove_existing_task_payloads(
                task_dir,
                safe_slug,
                app_number,
                {task_id, sanitized_task},
                preserve=filepath,
            )

            # 4. If universal format helpers are available, write that too
            if build_universal_payload and write_universal_file:
                try:
                    payload = build_universal_payload(
                        task_id=task_id,
                        model_slug=model_slug,
                        app_number=app_number,
                        tools_requested=sorted(list(set(tools_executed) | set(normalized_tools.keys()))),
                        tool_results=normalized_tools,
                        start_time=time.time() - 1, # Placeholder
                        end_time=time.time(),
                        detected_languages=[] # Placeholder
                    )
                    universal_filepath = Path(write_universal_file(self.results_dir, model_slug, app_number, task_id, payload))
                    if universal_filepath.exists() and universal_filepath.parent != task_dir:
                        try:
                            # Move legacy universal output under the grouped folder for consistency
                            target = task_dir / universal_filepath.name
                            universal_filepath.replace(target)
                            universal_filepath = target
                        except Exception as move_exc:
                            logger.debug("Failed to relocate universal file %s: %s", universal_filepath, move_exc)
                    logger.info(f"[SAVE] Universal results saved to: {universal_filepath}")
                except Exception as e:
                    logger.warning(f"Could not write universal results file: {e}")

            # 5. Prune legacy directories
            self.prune_legacy_results(model_slug, app_number)
            
            # 6. Cleanup orphaned empty result files created by premature writes
            self._cleanup_empty_result_files(task_dir, safe_slug, app_number, sanitized_task, preserve=filepath)
            
            logger.info(f"[STATS] Aggregated {aggregated_findings.get('findings_total', 0)} findings from {len(tools_executed)} tools")
            
            return filepath
        except Exception as e:
            logger.error(f"[ERROR] Failed to save consolidated task results: {e}")
            raise

    def _remove_existing_task_payloads(
        self,
        task_dir: Path,
        safe_slug: str,
        app_number: int,
        task_ids: Iterable[str],
        preserve: Optional[Path] = None,
    ) -> None:
        """Remove previously written consolidated payloads for this task."""
        identifiers: set[str] = set()
        for tid in task_ids:
            if tid:
                identifiers.add(str(tid))
                identifiers.add(self._sanitize_task_id(tid))

        for ident in identifiers:
            patterns = [
                f"{safe_slug}_app{app_number}_task-{ident}_*.json",
                f"{safe_slug}_app{app_number}_task_{ident}_*.json",
            ]
            for pattern in patterns:
                for candidate in task_dir.glob(pattern):
                    if candidate.name.endswith('_universal.json'):
                        continue
                    if preserve and candidate.resolve() == preserve.resolve():
                        continue
                    try:
                        candidate.unlink()
                    except Exception:
                        logger.debug("Failed to remove legacy task payload %s", candidate)

    def _cleanup_empty_result_files(
        self,
        task_dir: Path,
        safe_slug: str,
        app_number: int,
        sanitized_task: str,
        preserve: Optional[Path] = None,
    ) -> None:
        """
        Remove empty or incomplete result files created by premature writes.
        
        These files were created by the Flask app's write_task_result_files() before
        analysis completed, resulting in empty or minimal JSON files. The canonical
        result file written by save_task_results() should be preserved.
        
        Args:
            task_dir: Directory containing task results
            safe_slug: Sanitized model slug
            app_number: Application number
            sanitized_task: Sanitized task ID
            preserve: Path to the canonical result file to keep
        """
        # Pattern matches files with the old naming scheme (without double-prefix)
        # Example: amazon_nova-pro-v1_app1_task_c186bd84fe47_*.json
        pattern = f"{safe_slug}_app{app_number}_{sanitized_task}_*.json"
        
        removed_count = 0
        for candidate in task_dir.glob(pattern):
            # Skip universal files and the canonical file we just wrote
            if candidate.name.endswith('_universal.json'):
                continue
            if preserve and candidate.resolve() == preserve.resolve():
                continue
                
            # Check if file is empty or has minimal content (likely premature write)
            try:
                if candidate.stat().st_size < 500:  # Very small file, likely empty structure
                    candidate.unlink()
                    removed_count += 1
                    logger.debug(f"Removed empty result file: {candidate.name}")
                    continue
                    
                # Check if file has actual analysis data
                with open(candidate, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    results = data.get('results', {})
                    
                    # File is considered empty if it has no services data and no findings
                    has_services = bool(results.get('services'))
                    has_findings = len(results.get('findings', [])) > 0
                    has_tools = len(results.get('tools', {})) > 0
                    
                    if not has_services and not has_findings and not has_tools:
                        candidate.unlink()
                        removed_count += 1
                        logger.info(f"Removed incomplete result file: {candidate.name}")
            except Exception as e:
                logger.debug(f"Failed to check/remove result file {candidate.name}: {e}")
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} empty/incomplete result file(s) from {task_dir.name}")

    def _write_service_snapshots(
        self,
        task_dir: Path,
        safe_slug: str,
        model_slug: str,
        app_number: int,
        task_id: str,
        consolidated_results: Dict[str, Any],
    ) -> None:
        """Persist individual service payloads beside the consolidated result."""
        if not consolidated_results:
            return

        services_dir = task_dir / 'services'
        services_dir.mkdir(parents=True, exist_ok=True)

        for service_name, payload in consolidated_results.items():
            if not isinstance(payload, dict):
                continue
            snapshot = {
                'metadata': {
                    'model_slug': model_slug,
                    'app_number': app_number,
                    'task_id': task_id,
                    'service_name': service_name,
                    'created_at': datetime.now().isoformat() + '+00:00',
                },
                'results': payload,
            }
            filename = f"{safe_slug}_app{app_number}_{service_name}.json"
            target = services_dir / filename
            try:
                with open(target, 'w', encoding='utf-8') as handle:
                    json.dump(snapshot, handle, indent=2, default=str)
            except Exception as snapshot_exc:
                logger.debug("Failed to persist %s snapshot for task %s: %s", service_name, task_id, snapshot_exc)

    def _write_task_manifest(
        self,
        task_dir: Path,
        primary_filename: str,
        model_slug: str,
        app_number: int,
        task_id: str,
        consolidated_results: Dict[str, Any],
    ) -> None:
        """Emit a lightweight manifest describing artefacts for the grouped task."""
        service_files = {}
        services_dir = task_dir / 'services'
        if services_dir.exists():
            for service_path in services_dir.glob('*.json'):
                key = service_path.stem.split('_')[-1]
                service_files[key] = service_path.name

        manifest = {
            'task_id': task_id,
            'model_slug': model_slug,
            'app_number': app_number,
            'primary_result': primary_filename,
            'services': sorted(service_files.keys() or consolidated_results.keys()),
            'service_files': service_files,
            'created_at': datetime.now().isoformat() + '+00:00',
        }

        try:
            with open(task_dir / 'manifest.json', 'w', encoding='utf-8') as handle:
                json.dump(manifest, handle, indent=2, default=str)
        except Exception as manifest_exc:
            logger.debug("Failed to write manifest for task %s: %s", task_id, manifest_exc)

    def find_latest_results(self, model_slug: str, app_number: int) -> Dict[str, Path]:
        """Find the latest result file for each analysis type for a given model/app."""
        latest_results: Dict[str, Path] = {}
        safe_slug = str(model_slug).replace('/', '_').replace('\\', '_')

        app_dir = self.results_dir / safe_slug / f"app{app_number}"
        if not app_dir.exists():
            return {}

        pattern = f"{safe_slug}_app{app_number}_*.json"
        search_roots = [app_dir]
        legacy_dir = app_dir / 'analysis'
        if legacy_dir.exists():
            search_roots.append(legacy_dir)

        seen: set[Path] = set()

        for root in search_roots:
            if not root.exists():
                continue
            for candidate in root.rglob(pattern):
                try:
                    if any(part.lower() == 'services' for part in candidate.parts):
                        continue
                    if candidate.name.endswith('_universal.json'):
                        continue
                    resolved = candidate.resolve()
                    if resolved in seen:
                        continue
                    seen.add(resolved)
                    analysis_key = self._resolve_analysis_key(candidate, app_number)
                    if not analysis_key:
                        continue
                    current = latest_results.get(analysis_key)
                    candidate_mtime = candidate.stat().st_mtime
                    if current is None or candidate_mtime > current.stat().st_mtime:
                        latest_results[analysis_key] = candidate
                except FileNotFoundError:
                    continue
                except Exception as exc:
                    logger.debug("Skipping candidate %s due to error: %s", candidate, exc)
                    continue

        return latest_results

    def _resolve_analysis_key(self, path: Path, app_number: int) -> Optional[str]:
        stem = path.stem
        marker = f"_app{app_number}_"
        idx = stem.find(marker)
        if idx == -1:
            return None
        remainder = stem[idx + len(marker):]
        for prefix in ('task-', 'task_'):
            if remainder.startswith(prefix):
                task_part = remainder.split('_', 1)[0]
                suffix = task_part[len(prefix):]
                return suffix or None
        # Legacy style: <analysis_type>_<timestamp>
        analysis_type = remainder.split('_', 1)[0]
        if analysis_type in {'suppressed', 'task'}:
            return None
        return analysis_type or None

    async def create_unified_result(self, model_slug: str, app_number: int, task_id: str = "unified") -> Optional[Path]:
        """
        Create a unified result file from the latest individual analysis results.
        """
        logger.info(f"Creating unified result for {model_slug} app {app_number}...")
        
        latest_results = self.find_latest_results(model_slug, app_number)
        
        if not latest_results:
            logger.warning(f"No individual results found for {model_slug} app {app_number}. Cannot create unified result.")
            return None

        consolidated_results: Dict[str, Any] = {}
        for analysis_type, filepath in latest_results.items():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # The actual results are usually under a 'results' key
                consolidated_results[analysis_type] = data.get('results', data)
            except Exception as e:
                logger.error(f"Failed to load result file {filepath}: {e}")
                consolidated_results[analysis_type] = {'status': 'error', 'error': f'Failed to load: {e}'}

        try:
            # Use the existing save_task_results to generate the unified file
            unified_filepath = await self.save_task_results(model_slug, app_number, task_id, consolidated_results)
            logger.info(f"Successfully created unified result file: {unified_filepath}")
            return unified_filepath
        except Exception as e:
            logger.error(f"Failed to create unified result file: {e}")
            return None

    def _ordered_services(self, consolidated_results: Dict[str, Any]) -> Dict[str, Any]:
        """Return services dict in a stable, logical order for readability.

        Preferred order: static, security, dynamic, performance, ai, then others alphabetically.
        """
        if not isinstance(consolidated_results, dict):
            return {}
        preferred = ['static', 'security', 'dynamic', 'performance', 'ai']
        ordered: Dict[str, Any] = {}
        # Add preferred in order if present
        for key in preferred:
            if key in consolidated_results:
                ordered[key] = consolidated_results[key]
        # Add any remaining keys in sorted order
        for key in sorted(k for k in consolidated_results.keys() if k not in ordered):
            ordered[key] = consolidated_results[key]
        return ordered

    def _collect_normalized_tools(self, consolidated_results: Dict[str, Any]) -> Dict[str, Any]:
        """Collect a flat map of tool -> minimal, consistent summary across services.

        Uses shared utility as base, then applies special handling for AI analyzer format.
        
        Each entry contains: status, total_issues, executed, duration_seconds (if present),
        severity_breakdown (if present), and error (if present).
        """
        if SHARED_UTILS_AVAILABLE:
            # Use shared utility for basic collection
            tools = shared_collect_tools(consolidated_results)
        else:
            tools: Dict[str, Any] = {}

        if not isinstance(consolidated_results, dict):
            return tools

        # Metadata keys to skip (case-insensitive) - these are service/structure metadata, not tools
        METADATA_KEYS = {
            'tool_status', '_metadata', 'status', 'file_counts', 'security_files', 
            'total_files', 'message', 'error', 'analysis_time', 'model_slug', 
            'app_number', 'tools_used', 'configuration_applied', 'results',
            '_project_metadata'
        }

        # Prefer per-service analysis.tool_results when available (if shared utils didn't populate)
        if not SHARED_UTILS_AVAILABLE:
            for service_name, service_result in consolidated_results.items():
                if not isinstance(service_result, dict):
                    continue
                analysis = service_result.get('analysis', {})
                if not isinstance(analysis, dict):
                    continue
                
                # Check for tool_results at top level
                tool_results = analysis.get('tool_results')
                if isinstance(tool_results, dict):
                    for tname, tdata in tool_results.items():
                        if tname in tools or not isinstance(tdata, dict):
                            continue
                        # Skip metadata keys (case-insensitive)
                        if tname.lower() in METADATA_KEYS:
                            continue
                        tools[tname] = {
                            'status': tdata.get('status', 'unknown'),
                            'duration_seconds': tdata.get('duration') or tdata.get('duration_seconds'),
                            'total_issues': tdata.get('total_issues'),
                            'executed': tdata.get('executed', False),
                            'severity_breakdown': tdata.get('severity_breakdown'),
                            'error': tdata.get('error')
                        }
        
        # Handle AI analyzer's multi-tool format: analysis.tools.{requirements-scanner, code-quality-analyzer}
        # This special handling is needed because AI analyzer has unique response structure
        for service_name, service_result in consolidated_results.items():
            if not isinstance(service_result, dict) or service_name != 'ai':
                continue
            analysis = service_result.get('analysis', {})
            if not isinstance(analysis, dict):
                continue
            
            ai_tools_map = analysis.get('tools', {})
            if isinstance(ai_tools_map, dict):
                for tname, tdata in ai_tools_map.items():
                    if tname in tools or not isinstance(tdata, dict):
                        continue
                    # Extract tool-specific info
                    tool_status = tdata.get('status', 'unknown')
                    tool_results_data = tdata.get('results', {})
                    tool_summary = tool_results_data.get('summary', {}) if isinstance(tool_results_data, dict) else {}
                    
                    # Count unmet requirements as issues
                    total_issues = 0
                    compliance_pct = tool_summary.get('compliance_percentage')
                    
                    if tname in ['requirements-scanner', 'requirements-checker']:
                        # New format: backend/frontend/admin totals
                        total_backend = tool_summary.get('backend_total', tool_summary.get('total_functional_requirements', 0))
                        met_backend = tool_summary.get('backend_met', tool_summary.get('functional_requirements_met', 0))
                        total_issues = (total_backend - met_backend) if total_backend > met_backend else 0
                        
                        # Add frontend unmet
                        total_frontend = tool_summary.get('frontend_total', 0)
                        met_frontend = tool_summary.get('frontend_met', 0)
                        total_issues += (total_frontend - met_frontend) if total_frontend > met_frontend else 0
                        
                        # Add admin unmet
                        total_admin = tool_summary.get('admin_total', 0)
                        met_admin = tool_summary.get('admin_met', 0)
                        total_issues += (total_admin - met_admin) if total_admin > met_admin else 0
                        
                        # Add failed endpoints
                        total_endpoints = tool_summary.get('total_api_endpoints', tool_summary.get('total_control_endpoints', 0))
                        passed_endpoints = tool_summary.get('api_endpoints_passed', tool_summary.get('control_endpoints_passed', 0))
                        total_issues += (total_endpoints - passed_endpoints) if total_endpoints > passed_endpoints else 0
                    elif tname == 'code-quality-analyzer':
                        # New format: quality_metrics with aggregate score
                        if 'aggregate_score' in tool_summary:
                            # New format with quality metrics
                            metrics_total = tool_summary.get('total_metrics', 0)
                            metrics_passed = tool_summary.get('metrics_passed', 0)
                            total_issues = (metrics_total - metrics_passed) if metrics_total > metrics_passed else 0
                            total_issues += tool_summary.get('critical_issues_count', 0)
                            compliance_pct = tool_summary.get('aggregate_score')
                        else:
                            # Legacy format: stylistic_requirements
                            total_stylistic = tool_summary.get('total_stylistic_requirements', 0)
                            met_stylistic = tool_summary.get('stylistic_requirements_met', 0)
                            total_issues = total_stylistic - met_stylistic if total_stylistic > met_stylistic else 0
                    
                    tools[tname] = {
                        'status': tool_status,
                        'duration_seconds': None,  # AI analyzer doesn't track per-tool duration
                        'total_issues': total_issues,
                        'executed': tool_status in ['success', 'warning', 'partial_success'],
                        'compliance_percentage': compliance_pct,
                        'error': tdata.get('error')
                    }
        
        # Also check for static analyzer's nested structure: analysis.results.python/javascript/css
        if not SHARED_UTILS_AVAILABLE:
            for service_name, service_result in consolidated_results.items():
                if not isinstance(service_result, dict):
                    continue
                analysis = service_result.get('analysis', {})
                if not isinstance(analysis, dict):
                    continue
                
                results = analysis.get('results', {})
                if isinstance(results, dict):
                    for lang_category in ['python', 'javascript', 'css']:
                        lang_tools = results.get(lang_category, {})
                        if isinstance(lang_tools, dict):
                            for tname, tdata in lang_tools.items():
                                if tname in tools or not isinstance(tdata, dict):
                                    continue
                                # Skip metadata keys (case-insensitive)
                                if tname.lower() in METADATA_KEYS:
                                    continue
                                # Verify this looks like a tool result (has expected tool fields)
                                if not ('tool' in tdata or 'executed' in tdata or 'status' in tdata):
                                    continue
                                tools[tname] = {
                                    'status': tdata.get('status', 'unknown'),
                                    'duration_seconds': None,  # Static analyzer doesn't track per-tool duration
                                    'total_issues': tdata.get('total_issues', 0),
                                    'executed': tdata.get('executed', False),
                                    'severity_breakdown': None,
                                    'error': tdata.get('error')
                                }

        # Fallback/augment from lightweight raw_outputs if needed
        if not tools:
            raw_outputs = self._build_lightweight_raw_outputs(consolidated_results)
            for _, analyzer_data in raw_outputs.items():
                if not isinstance(analyzer_data, dict):
                    continue
                tmap = analyzer_data.get('tools')
                if isinstance(tmap, dict):
                    for tname, tdata in tmap.items():
                        if tname in tools or not isinstance(tdata, dict):
                            continue
                        # Skip metadata keys in fallback path too
                        if tname.lower() in METADATA_KEYS:
                            continue
                        tools[tname] = {
                            'status': tdata.get('status', 'unknown'),
                            'duration_seconds': tdata.get('duration') or tdata.get('duration_seconds') if isinstance(tdata, dict) else None,
                            'total_issues': tdata.get('total_issues', 0),
                            'executed': tdata.get('executed', False),
                            'error': tdata.get('error')
                        }

        # Ensure deterministic ordering by tool name
        return {k: tools[k] for k in sorted(tools.keys())}

    
    def _build_lightweight_raw_outputs(self, consolidated_results: Dict[str, Any]) -> Dict[str, Any]:
        """Build a lightweight raw outputs section with only essential template data."""
        raw_outputs: Dict[str, Any] = {}

        for analyzer_name, analyzer_result in consolidated_results.items():
            if not isinstance(analyzer_result, dict):
                continue
            
            analysis_data = analyzer_result.get('analysis', {})
            if not isinstance(analysis_data, dict):
                continue

            # Extract only essential tool information for templates
            tools_summary = {}
            
            # Get tool results from various possible locations
            tool_results_sources = [
                analysis_data.get('tool_results', {}),
                analysis_data.get('results', {}).get('tool_results', {}) if isinstance(analysis_data.get('results'), dict) else {},
                analysis_data.get('results', {}) if isinstance(analysis_data.get('results'), dict) else {}
            ]
            
            for tool_results in tool_results_sources:
                if isinstance(tool_results, dict):
                    for tool_name, tool_data in tool_results.items():
                        if isinstance(tool_data, dict) and tool_name not in tools_summary:
                            tools_summary[tool_name] = {
                                'status': tool_data.get('status', 'unknown'),
                                'total_issues': tool_data.get('total_issues', 0),
                                'executed': tool_data.get('executed', False),
                                'files_analyzed': tool_data.get('files_analyzed'),
                                'error': tool_data.get('error')
                            }
            
            # Create lightweight analyzer entry
            raw_outputs[analyzer_name] = {
                'status': analyzer_result.get('status', 'unknown'),
                'tools': tools_summary,
                'raw_output': self._summarize_analysis_output(analysis_data)
            }

        return raw_outputs
    
    def _summarize_analysis_output(self, analysis_data: Dict[str, Any]) -> str:
        """Create a summary of analysis output for raw_output field."""
        summary_parts = []
        
        # Get summary data
        summary = analysis_data.get('summary', {})
        if isinstance(summary, dict):
            total_issues = summary.get('total_issues_found', 0)
            tools_run = summary.get('tools_run_successfully', 0)
            
            summary_parts.append("Analysis Results")
            summary_parts.append("=" * 40)
            summary_parts.append(f"Total Issues Found: {total_issues}")
            summary_parts.append(f"Tools Run Successfully: {tools_run}")
            
            # Add severity breakdown if available
            severity_breakdown = summary.get('severity_breakdown', {})
            if severity_breakdown:
                summary_parts.append("\nSeverity Breakdown:")
                for severity, count in severity_breakdown.items():
                    if count > 0:
                        summary_parts.append(f"  {severity.upper()}: {count}")
        
        return "\n".join(summary_parts) if summary_parts else "Analysis completed successfully"
    
    def list_results(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent analysis results from project-root results tree."""
        result_files: List[Dict[str, Any]] = []
        try:
            # Collect any json files under results tree (excluding massive trees)
            for filepath in self.results_dir.rglob("*.json"):
                try:
                    stat = filepath.stat()
                    # Determine if batch file
                    is_batch = any(part == 'batch' for part in filepath.parts)
                    result_files.append({
                        'filename': filepath.name,
                        'path': str(filepath),
                        'size': stat.st_size,
                        'modified': datetime.fromtimestamp(stat.st_mtime),
                        'is_batch': is_batch
                    })
                except Exception as e:
                    logger.warning(f"Could not read file info for {filepath}: {e}")
            # Sort by modification time (newest first)
            result_files.sort(key=lambda x: x['modified'], reverse=True)
            return result_files[:limit]
        except Exception as e:
            logger.warning(f"Could not list results: {e}")
            return result_files

    def _map_analysis_type_to_container_dir(self, analysis_type: str) -> str:
        """Map analysis type to container folder name for results organization."""
        at = (analysis_type or '').lower()
        if at in ('security', 'static'):
            return 'static-analyzer'
        if at in ('dynamic', 'zap'):
            return 'dynamic-analyzer'
        if at in ('performance',):
            return 'performance-tester'
        if at in ('ai', 'ai_review', 'ai-review'):
            return 'ai-analyzer'
        if at in ('comprehensive',):
            return 'comprehensive'
        # Default catch-all
        return 'analysis'

    def find_result_files(self, query: str) -> List[Path]:
        """Find result files by query within the results tree.

        Resolution order:
        - Absolute path provided and exists -> return it
        - Relative path under results_dir exists -> return it
        - If query contains glob chars (*?[]) -> rglob(query)
        - Exact filename match across all JSON files (case-insensitive on Windows)
        - Fallback: substring match against filenames
        Returns a list of matches sorted by modified time (newest first).
        """
        q = (query or "").strip()
        matches: List[Path] = []
        try:
            # Absolute path
            p = Path(q)
            if p.is_absolute() and p.exists():
                return [p.resolve()]

            # Relative path from results root
            rel = (self.results_dir / q).resolve()
            if rel.exists():
                return [rel]

            # Glob pattern support
            if any(ch in q for ch in "*?[]"):
                matches = list(self.results_dir.rglob(q))
            else:
                # Exact filename match across JSONs
                lower_q = q.lower()
                for f in self.results_dir.rglob("*.json"):
                    try:
                        if f.name.lower() == lower_q:
                            matches.append(f)
                    except Exception:
                        continue
                # Fallback: substring match
                if not matches:
                    for f in self.results_dir.rglob("*.json"):
                        try:
                            if lower_q in f.name.lower():
                                matches.append(f)
                        except Exception:
                            continue

            # Sort newest first
            try:
                matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            except Exception:
                pass
        except Exception:
            return []

        return matches
async def handle_unify(args):
    """Handler for the 'unify' command."""
    manager = AnalyzerManager()
    await manager.create_unified_result(args.model, args.app)


# =================================================================
# COMMAND LINE INTERFACE
# =================================================================

def print_help():
    """Print help information."""
    help_text = """
Unified Analyzer Manager - Container Management & Analysis Tool

CONTAINER MANAGEMENT:
  start                    Start all analyzer services
  stop                     Stop all analyzer services  
  restart                  Restart all analyzer services
  status                   Show status of all services
  logs [service] [lines]   Show logs (optional: specific service, line count)

ANALYSIS OPERATIONS:
    analyze <model> <app> [type]     Run analysis on specific app
                                                                     Types: comprehensive, security, static, performance, dynamic, ai
  
  batch <models_file>              Run batch analysis from JSON file
                                   Format: [["model1", 1], ["model2", 2], ...]
  
  batch-models <model1,model2,...> Quick batch on multiple models (app 1)

TESTING & VALIDATION:
  test                     Test all services comprehensively
  health                   Check health of all services
  ping <service>           Ping specific service

RESULTS MANAGEMENT:
  results                  List recent analysis results
  results <filename>       Show specific result file

EXAMPLES:
  python analyzer_manager.py start
  python analyzer_manager.py analyze anthropic_claude-3.7-sonnet 1 security
  python analyzer_manager.py batch-models openai_gpt-4,anthropic_claude-3.7-sonnet
  python analyzer_manager.py logs ai-analyzer 100
  python analyzer_manager.py test

ENVIRONMENT VARIABLES:
  OPENROUTER_API_KEY      API key for AI analysis (required for AI analyzer)
  LOG_LEVEL              Logging level (DEBUG, INFO, WARNING, ERROR)

For detailed documentation, see the docstring at the top of this file.
"""
    print(help_text)


async def main():
    """Main entry point for the analyzer manager."""
    if len(sys.argv) < 2:
        if JSON_MODE:
            # Emit a helpful JSON error without extra text
            print(json.dumps({"status": "error", "error": "missing_command"}))
        else:
            print_help()
        return
    
    command = sys.argv[1].lower()
    manager = AnalyzerManager()
    
    if not JSON_MODE:
        print("Unified Analyzer Manager v1.0")
        print("=" * 60)
    
    try:
        if command == 'start':
            success = manager.start_services()
            if success:
                if not JSON_MODE:
                    print("\n🎉 Analyzer infrastructure is ready!")
                    print("You can now run: python analyzer_manager.py test")
        
        elif command == 'stop':
            manager.stop_services()
        
        elif command == 'restart':
            manager.restart_services()
        
        elif command == 'status':
            manager.show_status()
        
        elif command == 'logs':
            service = sys.argv[2] if len(sys.argv) > 2 else None
            lines = int(sys.argv[3]) if len(sys.argv) > 3 else 50
            manager.show_logs(service, lines)
        
        elif command == 'analyze':
            if len(sys.argv) < 4:
                if JSON_MODE:
                    print(json.dumps({"status": "error", "error": "usage: analyze <model> <app_number> [type]"}))
                else:
                    print("[ERROR] Usage: python analyzer_manager.py analyze <model> <app_number> [type]")
                return
            
            model_slug = sys.argv[2]
            app_number = int(sys.argv[3])
            analysis_type = sys.argv[4] if len(sys.argv) > 4 else 'comprehensive'
            
            # Normalize model slug before analysis
            normalized_slug = normalize_model_slug(model_slug)
            if normalized_slug != model_slug:
                logger.info(f"Normalized model slug: {model_slug} → {normalized_slug}")
                model_slug = normalized_slug
            # Optional: parse tool selection e.g., --tools bandit pylint
            tools_arg: Optional[List[str]] = None
            if '--tools' in sys.argv:
                idx = sys.argv.index('--tools')
                # Collect args after --tools; support comma-separated single token as well
                candidate = sys.argv[idx + 1:] if idx + 1 < len(sys.argv) else []
                # Stop at next flag if any (future-proofing)
                collected: List[str] = []
                for tok in candidate:
                    if tok.startswith('-') and tok != '-':
                        break
                    # Split by comma to allow --tools bandit,eslint
                    parts = [p.strip() for p in tok.split(',') if p.strip()]
                    collected.extend(parts)
                tools_arg = collected if collected else None
            
            if not JSON_MODE:
                print(f"[ANALYZE] Analyzing {model_slug} app {app_number} ({analysis_type})")
            
            if analysis_type == 'comprehensive':
                results = await manager.run_comprehensive_analysis(model_slug, app_number)
            elif analysis_type == 'security':
                results = await manager.run_security_analysis(model_slug, app_number, tools=tools_arg)
            elif analysis_type == 'performance':
                results = await manager.run_performance_test(model_slug, app_number, tools=tools_arg)
            elif analysis_type in ['dynamic', 'zap']:
                results = await manager.run_dynamic_analysis(model_slug, app_number, tools=tools_arg)
            elif analysis_type == 'ai':
                results = await manager.run_ai_analysis(model_slug, app_number, tools=tools_arg)
            elif analysis_type == 'static':
                results = await manager.run_static_analysis(model_slug, app_number, tools=tools_arg)
            else:
                if JSON_MODE:
                    print(json.dumps({"status": "error", "error": f"unknown_type:{analysis_type}"}))
                else:
                    print(f"[ERROR] Unknown analysis type: {analysis_type}")
                return
            
            if JSON_MODE:
                # Emit raw JSON for machine consumption
                try:
                    print(json.dumps(results, ensure_ascii=False))
                except Exception as e:
                    print(json.dumps({"status": "error", "error": f"json_dump_failed:{str(e)}"}))
            else:
                print("[OK] Analysis completed. Results summary:")
                if isinstance(results, dict):
                    # Check if this is a comprehensive result (keys are service names like static/dynamic/performance/ai)
                    # vs a single-service result (has 'status' key at top level with 'analysis' nested dict)
                    service_keys = {'static', 'dynamic', 'performance', 'ai'}
                    is_comprehensive = any(k in service_keys for k in results.keys()) and 'status' not in results
                    
                    if is_comprehensive:
                        # Comprehensive results: dict of service results
                        for key, result in results.items():
                            if isinstance(result, dict):
                                status = result.get('status', 'unknown')
                                print(f"  {key}: {status}")
                    else:
                        # Single-service result: status at top level
                        status = results.get('status', 'unknown')
                        print(f"  type: {analysis_type}, status: {status}")
        
        elif command == 'batch':
            if len(sys.argv) < 3:
                print("[ERROR] Usage: python analyzer_manager.py batch <models_file.json>")
                return
            
            models_file = Path(sys.argv[2])
            if not models_file.exists():
                print(f"[ERROR] File not found: {models_file}")
                return
            
            try:
                with open(models_file, 'r') as f:
                    models_and_apps = json.load(f)
                
                results = await manager.run_batch_analysis(models_and_apps)
                print("[OK] Batch analysis completed:")
                print(f"  Success rate: {results['summary']['success_rate']:.1f}%")
                print(f"  Duration: {results['summary']['total_duration']:.1f}s")
                
            except Exception as e:
                print(f"[ERROR] Failed to run batch analysis: {e}")
        
        elif command == 'batch-models':
            if len(sys.argv) < 3:
                print("[ERROR] Usage: python analyzer_manager.py batch-models <model1,model2,...>")
                return
            
            model_names = sys.argv[2].split(',')
            models_and_apps = [(model.strip(), 1) for model in model_names]
            
            print(f"📦 Running batch analysis on {len(models_and_apps)} models (app 1)")
            
            results = await manager.run_batch_analysis(models_and_apps)
            print("[OK] Batch analysis completed:")
            print(f"  Success rate: {results['summary']['success_rate']:.1f}%")
            print(f"  Duration: {results['summary']['total_duration']:.1f}s")
        
        elif command == 'test':
            print("🧪 Running comprehensive service tests...")
            test_results = await manager.test_all_services()
            
            summary = test_results['summary']
            print("\n[STATS] TEST RESULTS:")
            print(f"  Healthy services: {summary['healthy_services']}/{summary['total_services']}")
            print(f"  Successful pings: {summary['successful_pings']}/{summary['total_services']}")
            print(f"  Functional tests: {summary['functional_tests_passed']}")
            print(f"  Overall health: {summary['overall_health'].upper()}")
        
        elif command == 'health':
            try:
                health_results = await manager.check_all_services_health()
                if JSON_MODE:
                    # Emit a condensed JSON map
                    print(json.dumps({"services": health_results}))
                else:
                    print("\nSERVICE HEALTH:")
                    all_healthy = True
                    for service_name, result in health_results.items():
                        status = result.get('status', 'unknown')
                        icon = "OK" if status == 'healthy' else "FAIL"
                        print(f"  {icon} {service_name}: {status}")
                        if status != 'healthy':
                            all_healthy = False
                    
                    # Exit with code 0 only if all services are healthy
                    if not all_healthy:
                        sys.exit(1)
                    
            except Exception as e:
                if JSON_MODE:
                    print(json.dumps({"status": "error", "error": str(e)}))
                else:
                    print(f"HEALTH CHECK FAILED: {e}")
                sys.exit(1)
        
        elif command == 'ping':
            if len(sys.argv) < 3:
                print("[ERROR] Usage: python analyzer_manager.py ping <service_name>")
                return
            
            service_name = sys.argv[2]
            if service_name not in manager.services:
                print(f"[ERROR] Unknown service: {service_name}")
                print(f"Available services: {', '.join(manager.services.keys())}")
                return
            
            result = await manager._test_service_ping(service_name)
            if result['status'] == 'success':
                print(f"[OK] {service_name} responded in {result['response_time']:.3f}s")
            else:
                print(f"[ERROR] {service_name} ping failed: {result.get('error')}")
        
        elif command == 'results':
            if len(sys.argv) > 2:
                # Show specific result file, with recursive lookup
                query = sys.argv[2]
                matches = manager.find_result_files(query)

                if not matches:
                    if JSON_MODE:
                        print(json.dumps({"status": "error", "error": "result_not_found", "query": query}))
                    else:
                        print(f"[ERROR] Result not found for query: {query}")
                        print("Tip: You can pass a filename, partial name, relative path under 'results/', an absolute path, or a glob like '**/static-analyzer/*.json'.")
                    return

                # If multiple matches, show top 5 and require more specific query
                if len(matches) > 1:
                    if JSON_MODE:
                        print(json.dumps({
                            "status": "ambiguous",
                            "count": len(matches),
                            "candidates": [str(p) for p in matches[:10]]
                        }))
                    else:
                        print(f"⚠️  Ambiguous query. {len(matches)} files match. Showing newest 5:")
                        for p in matches[:5]:
                            try:
                                mtime = datetime.fromtimestamp(p.stat().st_mtime)
                                print(f" - {p}  ({mtime})")
                            except Exception:
                                print(f" - {p}")
                        print("Refine your query (e.g., include more of the path or use a glob).")
                    return

                filepath = matches[0]
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        results = json.load(f)

                    if JSON_MODE:
                        print(json.dumps({"status": "ok", "path": str(filepath), "results": results}))
                    else:
                        print(f"📄 Results from {filepath}:")
                        print(json.dumps(results, indent=2, default=str))

                except Exception as e:
                    if JSON_MODE:
                        print(json.dumps({"status": "error", "error": str(e), "path": str(filepath)}))
                    else:
                        print(f"[ERROR] Failed to read results: {e}")
            else:
                # List results
                results = manager.list_results()
                
                print(f"\n📋 RECENT ANALYSIS RESULTS ({len(results)} files):")
                print("-" * 80)
                
                for result in results:
                    size_kb = result['size'] / 1024
                    batch_indicator = "📦" if result['is_batch'] else "📄"
                    print(f"{batch_indicator} {result['filename']:50} {size_kb:6.1f}KB {result['modified']}")
        
        elif command in ['help', '--help', '-h']:
            if JSON_MODE:
                print(json.dumps({"status": "ok", "commands": ["start","stop","restart","status","logs","analyze","batch","batch-models","test","health","ping","results"]}))
            else:
                print_help()
        
        else:
            print(f"[ERROR] Unknown command: {command}")
            print("Use 'python analyzer_manager.py help' for usage information")
    
    except KeyboardInterrupt:
        logger.info("Operation interrupted by user")
    except Exception as e:
        logger.error(f"Command failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Manager stopped by user")
    except Exception as e:
        logger.error(f"Manager failed: {e}")
        sys.exit(1)
