"""
Docker Manager Service for Celery App

Manages Docker container operations for AI-generated applications.
Provides container lifecycle management, health monitoring, and log retrieval.
"""

import logging
import shutil
import time
import docker
from docker.errors import NotFound as DockerNotFound
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

"""NOTE: Use 'svc.docker_manager' logger name to align with existing log format.
This ensures compose command execution lines show up in app.log alongside
earlier Docker client connection diagnostics."""
logger = logging.getLogger('svc.docker_manager')


class DockerStatus:
    """Docker container status representation."""
    
    def __init__(self, success: bool = False, state: str = 'unknown', message: str = ''):
        self.success = success
        self.state = state
        self.message = message
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'state': self.state,
            'message': self.message,
            'timestamp': self.timestamp.isoformat()
        }


class DockerManager:
    """Docker container management service for Celery-based app."""

    def __init__(self):
        self.logger = logger
        self.client = self._create_docker_client()
        # Determine project root robustly (expect docker_manager at: <root>/src/app/services/docker_manager.py)
        # parents[0]=services, [1]=app, [2]=src, [3]=<project root>
        try:
            self.project_root = Path(__file__).resolve().parents[3]
        except Exception:
            # Fallback: climb until we find pytest.ini or docs folder
            p = Path(__file__).resolve()
            candidate = None
            for parent in p.parents:
                if (parent / 'pytest.ini').exists() or (parent / 'docs').exists():
                    candidate = parent
                    break
            self.project_root = candidate or Path.cwd()
        # Candidate roots where generated apps may live (project-root only)
        self.generated_roots: List[Path] = [
            self.project_root / 'generated',                     # project-root generated (preferred)
            self.project_root / 'generated' / 'apps',            # explicit apps folder under generated
        ]
        # Filter existing for faster lookups, but keep original list order for attempts logging
        self._existing_generated_roots = [r for r in self.generated_roots if r.exists()]
        # Default models_dir (first existing or first candidate for path echoes)
        self.models_dir = (self._existing_generated_roots[0]
                           if self._existing_generated_roots else self.generated_roots[0])
    
    def _create_docker_client(self) -> Optional[docker.DockerClient]:
        """Create Docker client with retries and diagnostics.

        Strategy order:
        1. docker.from_env() - respects DOCKER_HOST and works in containers
        2. Unix socket (Linux/Mac) - common daemon endpoint
        3. Named pipes (Windows) - Docker Desktop endpoints

        Retries each endpoint a few times with short backoff to handle race
        conditions when Docker is still initializing.
        """
        import platform
        import os
        
        # Determine platform-specific connection URLs
        system = platform.system().lower()
        base_urls = []
        
        if system == 'windows':
            base_urls = [
                'npipe:////./pipe/docker_engine',
                'npipe:////./pipe/dockerDesktopLinuxEngine',
            ]
        else:  # Linux/Mac or container environment
            base_urls = [
                'unix:///var/run/docker.sock',
            ]
        
        attempts_per_url = 3
        backoff_seconds = 1.0
        last_error: Optional[Exception] = None

        # First try docker.from_env() - works in most container environments
        try:
            client = docker.from_env()
            client.ping()
            self.logger.info("Connected to Docker via environment configuration")
            return client
        except Exception as e:
            self.logger.debug(f"Failed to connect via from_env(): {e}")
            last_error = e

        # Try platform-specific URLs
        for url in base_urls:
            for attempt in range(1, attempts_per_url + 1):
                try:
                    client = docker.DockerClient(base_url=url)
                    client.ping()
                    self.logger.info(f"Connected to Docker via {url} (attempt {attempt})")
                    return client
                except Exception as e:
                    last_error = e
                    # Only log at debug level to avoid noise unless final attempt
                    if attempt == attempts_per_url:
                        self.logger.debug(f"Failed to connect using {url} after {attempts_per_url} attempts: {e}")
                    time.sleep(backoff_seconds)

        # Fallback to default environment based client
        for attempt in range(1, attempts_per_url + 1):
            try:
                client = docker.from_env()
                client.ping()
                self.logger.info("Connected to Docker via default environment client")
                return client
            except Exception as e:
                last_error = e
                if attempt == attempts_per_url:
                    self.logger.error(f"Failed to connect to Docker via any method (env client final attempt): {e}")
                time.sleep(backoff_seconds)

        # If we reach here, we failed all attempts
        if last_error:
            self.logger.error(
                "Docker client unavailable after retries. Last error: %s. "
                "HINT: Ensure Docker Desktop is running and that the named pipe is accessible. "
                "If using a custom DOCKER_HOST, verify it is reachable.", last_error
            )
        return None

    def diagnose(self) -> Dict[str, Any]:
        """Return structured diagnostic information about Docker connectivity.

        Provides hints to surface in UI or logs, enabling faster troubleshooting.
        """
        info: Dict[str, Any] = {
            'connected': bool(self.client),
            'engine_info': None,
            'errors': [],
            'suggestions': []
        }
        if not self.client:
            info['suggestions'].extend([
                'Confirm Docker Desktop is running',
                'Run: docker version (should succeed without error)',
                'If DOCKER_HOST is set, ensure it points to a reachable daemon',
                'Try restarting Docker service/daemon',
            ])
            return info

        try:
            raw = self.client.info()
            info['engine_info'] = {
                'server_version': raw.get('ServerVersion'),
                'os_type': raw.get('OSType'),
                'architecture': raw.get('Architecture'),
                'kernel_version': raw.get('KernelVersion'),
                'containers_running': raw.get('ContainersRunning'),
                'images': raw.get('Images')
            }
        except Exception as e:
            info['errors'].append(str(e))
            info['suggestions'].append('Could not retrieve engine info – check daemon health with: docker info')
        return info
    
    def get_container_status(self, container_name: str) -> DockerStatus:
        """Get status of a specific container."""
        if not self.client:
            return DockerStatus(False, 'unknown', 'Docker client unavailable')
        
        try:
            container = self.client.containers.get(container_name)
            return DockerStatus(
                success=True,
                state=container.status,
                message=f"Container {container_name} is {container.status}"
            )
        except DockerNotFound:
            return DockerStatus(False, 'not_found', f'Container {container_name} not found')
        except Exception as e:
            return DockerStatus(False, 'error', f'Error checking container: {e}')
    
    def get_project_containers(self, model: str, app_num: int) -> List[Dict[str, Any]]:
        """Get containers for a model/app with resilient fallbacks.

        Fallback order:
          1. Compose project label (standard case)
          2. Explicit container_name entries parsed from compose file
          3. Heuristic name prefix scan (model[_|-]{backend|frontend}_)
        """
        if not self.client:
            return []
        import re
        project_name = self._get_project_name(model, app_num)
        results: List[Dict[str, Any]] = []

        def _c_dict(c):
            try:
                ports = c.ports
            except Exception:
                ports = {}
            return {
                'id': c.id[:12],
                'name': c.name,
                'status': getattr(c, 'status', 'unknown'),
                'image': c.image.tags[0] if getattr(c.image, 'tags', []) else 'unknown',
                'ports': ports,
                'labels': getattr(c, 'labels', {})
            }
        try:
            # 1) Label-based
            labeled = self.client.containers.list(all=True, filters={'label': f'com.docker.compose.project={project_name}'})
            if labeled:
                return [_c_dict(c) for c in labeled]

            # 2) Explicit names from compose file
            compose_path = self._get_compose_path(model, app_num)
            explicit = []
            if compose_path.exists():
                try:
                    for line in compose_path.read_text(encoding='utf-8', errors='ignore').splitlines():
                        m = re.search(r'container_name:\s*([A-Za-z0-9_.\-]+)', line)
                        if m:
                            explicit.append(m.group(1).strip())
                except Exception:
                    pass
            if explicit:
                for c in self.client.containers.list(all=True):
                    if c.name in explicit:
                        results.append(_c_dict(c))
                if results:
                    self.logger.debug("Containers resolved via explicit container_name entries: %s", explicit)
                    return results

            # 3) Heuristic prefixes
            variants = {model, model.replace('-', '_'), model.replace('_', '-')}
            prefixes = []
            for v in variants:
                prefixes.extend([f"{v}_backend_", f"{v}_frontend_"])
            for c in self.client.containers.list(all=True):
                if any(c.name.startswith(p) for p in prefixes):
                    results.append(_c_dict(c))
            return results
        except Exception as e:  # pragma: no cover
            self.logger.error("Error getting project containers: %s", e)
            return results
    
    def start_containers(self, model: str, app_num: int) -> Dict[str, Any]:
        """Start containers for a model/app using docker-compose."""
        compose_path = self._get_compose_path(model, app_num)
        if not compose_path.exists():
            return {
                'success': False,
                'error': f'Docker compose file not found: {compose_path}'
            }
        
        return self._execute_compose_command(
            compose_path, ['up', '-d'], model, app_num
        )
    
    def stop_containers(self, model: str, app_num: int) -> Dict[str, Any]:
        """Stop containers for a model/app using docker-compose."""
        compose_path = self._get_compose_path(model, app_num)
        if not compose_path.exists():
            return {
                'success': False,
                'error': f'Docker compose file not found: {compose_path}'
            }
        
        return self._execute_compose_command(
            compose_path, ['down'], model, app_num
        )
    
    def restart_containers(self, model: str, app_num: int) -> Dict[str, Any]:
        """Restart containers for a model/app."""
        # Stop first
        stop_result = self.stop_containers(model, app_num)
        if not stop_result.get('success', False):
            return stop_result
        
        # Then start
        return self.start_containers(model, app_num)
    
    def build_containers(self, model: str, app_num: int, no_cache: bool = True, start_after: bool = True) -> Dict[str, Any]:
        """Build containers for a model/app using docker-compose.

        If start_after=True (default) and build succeeds, will run 'up -d' to
        bring containers online so UI reflects a running state immediately.
        """
        compose_path = self._get_compose_path(model, app_num)
        if not compose_path.exists():
            return {
                'success': False,
                'error': f'Docker compose file not found: {compose_path}'
            }
        
        cmd = ['build']
        if no_cache:
            cmd.append('--no-cache')
        
        build_result = self._execute_compose_command(
            compose_path, cmd, model, app_num, timeout=600  # 10 minutes for build
        )
        if not build_result.get('success') or not start_after:
            return build_result

        # Start containers (docker compose up -d)
        up_result = self._execute_compose_command(
            compose_path, ['up', '-d'], model, app_num, timeout=300
        )
        # Merge summaries
        merged = {
            'success': build_result.get('success') and up_result.get('success'),
            'build': build_result,
            'up': up_result
        }
        # Add top-level error if either step failed
        if not merged['success']:
            if not build_result.get('success'):
                merged['error'] = build_result.get('error', 'Build failed')
            elif not up_result.get('success'):
                merged['error'] = up_result.get('error', 'Start failed')
        return merged
    
    def get_container_logs(self, model: str, app_num: int,
                          container_type: str = 'backend', tail: int = 100) -> str:
        """Get logs from a specific Compose container for an app.

        Tries multiple strategies to find the container:
        - Compose labels (project + service)
        - Name prefix match (handles _1 / -1 suffix differences)
        - Direct name (legacy)
        """
        if not self.client:
            return "Docker client unavailable"

        project_name = self._get_project_name(model, app_num)
        desired_service = container_type

        try:
            # 1) Prefer label-based lookup (most reliable across Compose versions)
            containers = self.client.containers.list(
                all=True,
                filters={'label': [
                    f'com.docker.compose.project={project_name}',
                    f'com.docker.compose.service={desired_service}'
                ]}
            )
            target = containers[0] if containers else None

            # 2) Fallback: name prefix search (handles -1/_1 suffix)
            if target is None:
                # Include explicit container_name patterns
                name_prefixes = [
                    f"{project_name}_{desired_service}",
                    f"{project_name}-{desired_service}",
                    f"{model}_{desired_service}_",  # explicit generated form
                    f"{model.replace('-', '_')}_{desired_service}_",
                ]
                for c in self.client.containers.list(all=True):
                    nm = getattr(c, 'name', '')
                    if any(nm.startswith(pref) for pref in name_prefixes):
                        target = c
                        break

            # 3) Legacy direct get (may fail depending on suffix differences)
            if target is None:
                try:
                    target = self.client.containers.get(f"{project_name}_{desired_service}")
                except Exception:
                    try:
                        target = self.client.containers.get(f"{project_name}-{desired_service}")
                    except Exception:
                        target = None

            if target is None:
                return f"Container for {project_name}/{desired_service} not found"

            logs = target.logs(tail=tail).decode("utf-8", errors="replace")
            return logs
        except Exception as e:
            self.logger.error(f"Error getting logs for {project_name}/{desired_service}: {e}")
            return f"Error getting logs: {e}"
    
    def _get_compose_path(self, model: str, app_num: int) -> Path:
        """Resolve docker-compose.yml path for a model/app.

        Tries multiple layout variants (migration-friendly):
          1) <root>/generated/{model}/appN/docker-compose.yml (preferred project-root layout)
          2) <root>/generated/apps/{model}/appN/docker-compose.yml (explicit apps folder)
          3) Legacy/transitional src/ locations removed from lookup — project-root generated/ is now authoritative

        Returns the first existing path; if none exist, returns the first candidate
        so callers have a deterministic expected location.
        """
        # Prefer project-root generated/apps layout first, then transitional src/ locations, then legacy root
        candidates: List[Path] = [
            self.project_root / 'generated' / 'apps' / model / f'app{app_num}' / 'docker-compose.yml',
            self.project_root / 'generated' / model / f'app{app_num}' / 'docker-compose.yml',
        ]
        for c in candidates:
            if c.exists():
                return c
        # Return last candidate (current layout) even if missing for error messaging
        return candidates[-1]

    def debug_compose_resolution(self, model: str, app_num: int) -> Dict[str, Any]:
        """Provide detailed diagnostics for compose path resolution.

        Returns structured data enumerating candidate paths, which exist,
        chosen path, and basic docker connectivity/engine info.
        """
        chosen = self._get_compose_path(model, app_num)
        variants = [
            {
                'path': str(self.project_root / 'src' / 'generated' / 'apps' / model / f'app{app_num}' / 'docker-compose.yml'),
                'exists': (self.project_root / 'src' / 'generated' / 'apps' / model / f'app{app_num}' / 'docker-compose.yml').exists(),
                'variant': 'src-generated-apps (preferred)'
            },
            {
                'path': str(self.project_root / 'src' / 'generated' / model / f'app{app_num}' / 'docker-compose.yml'),
                'exists': (self.project_root / 'src' / 'generated' / model / f'app{app_num}' / 'docker-compose.yml').exists(),
                'variant': 'src-generated (transitional)'
            },
            {
                'path': str(self.project_root / 'generated' / model / f'app{app_num}' / 'docker-compose.yml'),
                'exists': (self.project_root / 'generated' / model / f'app{app_num}' / 'docker-compose.yml').exists(),
                'variant': 'legacy-root-generated'
            },
        ]
        diag = self.diagnose()
        return {
            'project_root': str(self.project_root),
            'models_dir_selected': str(self.models_dir),
            'candidate_roots_existing': [str(r) for r in self._existing_generated_roots],
            'compose_variants': variants,
            'chosen_compose_path': str(chosen),
            'chosen_exists': chosen.exists(),
            'docker_connected': diag.get('connected'),
            'docker_engine': diag.get('engine_info'),
        }
    
    def _get_project_name(self, model: str, app_num: int) -> str:
        """Get Docker Compose project name for model/app."""
        # Replace underscores and dots with hyphens for Docker compatibility
        safe_model = model.replace('_', '-').replace('.', '-')
        return f"{safe_model}-app{app_num}"
    
    def _execute_compose_command(self, compose_path: Path, command: List[str], 
                                model: str, app_num: int, timeout: int = 300) -> Dict[str, Any]:
        """Execute a docker compose command (v2 preferred, v1 fallback).

        Adds richer logging so we can debug why UI build/start buttons may
        appear to do nothing. Returns structured result including stdout/stderr.
        """
        import subprocess

        docker_path = shutil.which('docker')
        docker_compose_path = shutil.which('docker-compose')
        # Pre-compute project name for diagnostics (was previously referenced before assignment)
        project_name = self._get_project_name(model, app_num)
        cli_diagnostics: Dict[str, Any] = {
            'docker_in_path': bool(docker_path),
            'docker_compose_in_path': bool(docker_compose_path),
            'project_name': project_name,
            'compose_file_exists': compose_path.exists(),
            'compose_file': str(compose_path)
        }

        if docker_path:  # Prefer modern docker CLI with compose subcommand
            base_cmd = ['docker', 'compose']
            compose_variant = 'docker compose'
        elif docker_compose_path:
            base_cmd = ['docker-compose']
            compose_variant = 'docker-compose'
        else:
            self.logger.error("No docker CLI found in PATH; cannot execute compose command")
            return {
                'success': False,
                'error': 'Neither docker nor docker-compose CLI is available in PATH',
                'command': '',
                'compose_variant': None,
                'diagnostics': cli_diagnostics
            }

    # project_name already computed above
        cmd = base_cmd + ['-f', str(compose_path), '-p', project_name] + command
        cwd = compose_path.parent
        self.logger.info(
            "Compose exec variant=%s docker_path=%s compose_path=%s project=%s action=%s cwd=%s",
            compose_variant,
            docker_path or docker_compose_path,
            compose_path,
            project_name,
            ' '.join(command),
            cwd
        )

        start_ts = time.time()
        try:
            # Pass PROJECT_NAME environment variable to subprocess
            # This ensures docker-compose.yml can use ${PROJECT_NAME} for unique container names
            import os
            env = os.environ.copy()
            env['PROJECT_NAME'] = project_name
            
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
            duration = time.time() - start_ts
            success = result.returncode == 0
            # Trim stdout/stderr for logging
            trimmed_stdout = (result.stdout[:400] + '...') if len(result.stdout) > 400 else result.stdout
            trimmed_stderr = (result.stderr[:400] + '...') if len(result.stderr) > 400 else result.stderr
            level = self.logger.info if success else self.logger.error
            level(
                "Compose result rc=%s success=%s duration=%.2fs action=%s stdout_snip=%r stderr_snip=%r",
                result.returncode, success, duration, ' '.join(command), trimmed_stdout, trimmed_stderr
            )
            out: Dict[str, Any] = {
                'success': success,
                'returncode': result.returncode,
                'exit_code': result.returncode,  # Add for consistency with log modal
                'stdout': result.stdout,
                'stderr': result.stderr,
                'command': ' '.join(cmd),
                'compose_variant': compose_variant,
                'duration_seconds': duration,
                'diagnostics': cli_diagnostics
            }
            if not success:
                # Provide a concise error summary for API layer convenience
                # Extract the most relevant error message from stderr or stdout
                error_text = result.stderr.strip() if result.stderr.strip() else result.stdout.strip()
                # Try to extract the actual error message (often the last non-empty line)
                if error_text:
                    lines = [l.strip() for l in error_text.splitlines() if l.strip()]
                    out['error'] = lines[-1] if lines else f'Command failed with exit code {result.returncode}'
                else:
                    out['error'] = f'Command failed with exit code {result.returncode}'
            return out
        except subprocess.TimeoutExpired:
            self.logger.error("Compose command timeout after %ss: %s", timeout, ' '.join(cmd))
            return {
                'success': False,
                'error': f'Command timed out after {timeout} seconds',
                'command': ' '.join(cmd),
                'compose_variant': compose_variant,
                'diagnostics': cli_diagnostics
            }
        except Exception as e:  # pragma: no cover (environment dependent)
            self.logger.exception("Compose command failed: %s", ' '.join(cmd))
            return {
                'success': False,
                'error': str(e),
                'command': ' '.join(cmd),
                'compose_variant': compose_variant,
                'diagnostics': cli_diagnostics
            }

    # ------------------------------------------------------------------
    # Diagnostics / Preflight Helpers
    # ------------------------------------------------------------------
    def compose_preflight(self, model: str, app_num: int) -> Dict[str, Any]:
        """Return fast diagnostic info prior to attempting compose operations.

        Helps front-end display actionable hints instead of opaque APIError.
        """
        compose_path = self._get_compose_path(model, app_num)
        docker_cli = shutil.which('docker')
        docker_compose_cli = shutil.which('docker-compose')
        diag = self.diagnose()
        return {
            'model': model,
            'app_num': app_num,
            'compose_file': str(compose_path),
            'compose_file_exists': compose_path.exists(),
            'docker_cli': docker_cli,
            'docker_compose_cli': docker_compose_cli,
            'can_use_compose': bool(docker_cli or docker_compose_cli),
            'docker_connected': diag.get('connected'),
            'docker_engine': diag.get('engine_info'),
            'project_name': self._get_project_name(model, app_num)
        }

    def container_status_summary(self, model: str, app_num: int) -> Dict[str, Any]:
        """Summarize container statuses for the model/app pair."""
        containers = self.get_project_containers(model, app_num)
        states = {c['status'] for c in containers} if containers else set()
        return {
            'model': model,
            'app_num': app_num,
            'containers_found': len(containers),
            'states': list(states),
            'containers': containers,
        }
    
    def list_all_containers(self) -> List[Dict[str, Any]]:
        """List all Docker containers."""
        if not self.client:
            return []
        
        try:
            from datetime import timezone
            from dateutil import parser as date_parser
            containers = self.client.containers.list(all=True)
            result = []
            
            for container in containers:
                # Parse created timestamp and ensure it's timezone-aware (UTC)
                created_str = container.attrs.get('Created', '')
                try:
                    created_dt = date_parser.parse(created_str)
                    if created_dt.tzinfo is None:
                        # If naive, assume UTC
                        created_dt = created_dt.replace(tzinfo=timezone.utc)
                    created = created_dt.isoformat()
                except Exception:
                    created = created_str  # Fallback to raw string
                
                # Calculate uptime if container is running
                uptime = None
                if container.status == 'running':
                    try:
                        started_str = container.attrs.get('State', {}).get('StartedAt', '')
                        if started_str:
                            started_dt = date_parser.parse(started_str)
                            if started_dt.tzinfo is None:
                                started_dt = started_dt.replace(tzinfo=timezone.utc)
                            now = datetime.now(timezone.utc)
                            uptime_seconds = (now - started_dt).total_seconds()
                            uptime = int(uptime_seconds)
                    except Exception as e:
                        self.logger.debug(f"Error calculating uptime for {container.name}: {e}")
                
                result.append({
                    'id': container.id[:12],  # Short ID
                    'name': container.name,
                    'status': container.status,
                    'state': container.attrs.get('State', {}).get('Status', 'unknown'),
                    'image': container.image.tags[0] if container.image.tags else 'unknown',
                    'ports': container.ports,
                    'created': created,
                    'uptime': uptime,
                    'labels': container.labels
                })
            
            return result
        except Exception as e:
            self.logger.error(f"Error listing containers: {e}")
            return []
    
    def cleanup_unused_containers(self) -> Dict[str, Any]:
        """Clean up unused containers and images."""
        if not self.client:
            return {'success': False, 'error': 'Docker client unavailable'}
        
        try:
            # Remove stopped containers
            removed_containers = self.client.containers.prune()
            
            # Remove unused images
            removed_images = self.client.images.prune()
            
            return {
                'success': True,
                'containers_removed': removed_containers.get('ContainersDeleted', []),
                'space_reclaimed': removed_containers.get('SpaceReclaimed', 0) + 
                                 removed_images.get('SpaceReclaimed', 0)
            }
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_docker_info(self) -> Dict[str, Any]:
        """Get Docker system information."""
        if not self.client:
            # As a fallback, attempt CLI to provide some signal
            try:
                import subprocess
                result = subprocess.run(['docker', 'info', '--format', '{{json .}}'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0 and result.stdout.strip():
                    import json
                    info = json.loads(result.stdout)
                    return {
                        'containers': info.get('Containers', 0),
                        'containers_running': info.get('ContainersRunning', 0),
                        'containers_paused': info.get('ContainersPaused', 0),
                        'containers_stopped': info.get('ContainersStopped', 0),
                        'images': info.get('Images', 0),
                        'server_version': info.get('ServerVersion', 'unknown'),
                        'memory_total': info.get('MemTotal', 0),
                        'cpus': info.get('NCPU', 0)
                    }
            except Exception as e:
                self.logger.warning(f"Docker client unavailable and CLI info failed: {e}")
            return {'error': 'Docker client unavailable'}

        try:
            info = self.client.info()
            return {
                'containers': info.get('Containers', 0),
                'containers_running': info.get('ContainersRunning', 0),
                'containers_paused': info.get('ContainersPaused', 0),
                'containers_stopped': info.get('ContainersStopped', 0),
                'images': info.get('Images', 0),
                'server_version': info.get('ServerVersion', 'unknown'),
                'memory_total': info.get('MemTotal', 0),
                'cpus': info.get('NCPU', 0)
            }
        except Exception as e:
            self.logger.error(f"Error getting Docker info: {e}")
            return {'error': str(e)}
