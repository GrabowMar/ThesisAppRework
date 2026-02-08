"""
Docker Manager Service for Celery App

Manages Docker container operations for AI-generated applications.
Provides container lifecycle management, health monitoring, and log retrieval.
"""

import logging
import shutil
import time
import threading
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


# Global lock for managing per-app build locks
_build_locks: Dict[str, threading.Lock] = {}
_build_locks_lock = threading.Lock()  # Protects access to _build_locks dict


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
    
    def get_running_build_id(self, model: str, app_num: int) -> Optional[str]:
        """Extract build_id from currently running containers via Docker labels.
        
        Scans running containers for this model/app and extracts the build_id
        from their compose project label. This is the authoritative source when
        containers are already running but database build_id may be stale.
        
        Args:
            model: Model slug (e.g., 'anthropic_claude-4.5-sonnet-20250929')
            app_num: Application number
            
        Returns:
            Build ID string (e.g., '6864b014') if found, None otherwise
        """
        if not self.client:
            return None
        
        import re
        # Construct the expected project name prefix (without build_id)
        safe_model = model.replace('/', '-').replace('_', '-').replace('.', '-')
        prefix_pattern = f"{safe_model}-app{app_num}"
        
        try:
            # Search all running containers for matching project labels
            for container in self.client.containers.list(all=False):  # Only running containers
                labels = container.labels or {}
                project = labels.get('com.docker.compose.project', '')
                
                # Check if this container belongs to our model/app
                if project.startswith(prefix_pattern):
                    # Extract build_id from project name: model-slug-appN-XXXXXXXX
                    # Pattern: prefix-{8-char-hex-build_id}
                    match = re.match(rf'^{re.escape(prefix_pattern)}-([a-f0-9]{{8}})$', project)
                    if match:
                        build_id = match.group(1)
                        self.logger.debug(
                            "Extracted build_id=%s from running container %s (project=%s)",
                            build_id, container.name, project
                        )
                        return build_id
                    elif project == prefix_pattern:
                        # No build_id suffix (legacy container)
                        self.logger.debug(
                            "Found legacy container without build_id: %s (project=%s)",
                            container.name, project
                        )
                        return None
            
            # No matching containers found
            return None
            
        except Exception as e:
            self.logger.warning("Error extracting build_id from containers: %s", e)
            return None
    
    def get_project_containers(self, model: str, app_num: int) -> List[Dict[str, Any]]:
        """Get containers for a model/app with resilient fallbacks.

        Fallback order:
          1. Compose project label with build_id pattern (e.g., model-app1-abc123)
          2. Compose project label without build_id (legacy)
          3. Explicit container_name entries parsed from compose file
          4. Heuristic name prefix scan (matches any build_id variant)
        """
        if not self.client:
            return []
        import re
        base_project_name = self._get_project_name(model, app_num)  # Without build_id
        results: List[Dict[str, Any]] = []

        def _c_dict(c):
            try:
                ports = c.ports
            except Exception:
                ports = {}
            # Extract build_id from project label if present
            labels = getattr(c, 'labels', {})
            project_label = labels.get('com.docker.compose.project', '')
            build_id = None
            if project_label.startswith(base_project_name + '-'):
                # Extract the build_id suffix: "model-app1-abc123" -> "abc123"
                build_id = project_label[len(base_project_name) + 1:]
            return {
                'id': c.id[:12],
                'name': c.name,
                'status': getattr(c, 'status', 'unknown'),
                'image': c.image.tags[0] if getattr(c.image, 'tags', []) else 'unknown',
                'ports': ports,
                'labels': labels,
                'build_id': build_id
            }
        try:
            # 1) Label-based: Find ANY project starting with base_project_name
            # This matches both "model-app1" and "model-app1-abc123"
            all_containers = self.client.containers.list(all=True)
            for c in all_containers:
                project_label = getattr(c, 'labels', {}).get('com.docker.compose.project', '')
                # Match exact base name OR base name with build_id suffix
                if project_label == base_project_name or project_label.startswith(base_project_name + '-'):
                    results.append(_c_dict(c))
            
            if results:
                # Log which build_ids we found
                build_ids = set(r.get('build_id') for r in results if r.get('build_id'))
                if build_ids:
                    self.logger.debug("Found containers for %s with build_ids: %s", base_project_name, build_ids)
                return results

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
                for c in all_containers:
                    if c.name in explicit:
                        results.append(_c_dict(c))
                if results:
                    self.logger.debug("Containers resolved via explicit container_name entries: %s", explicit)
                    return results

            # 3) Heuristic prefix scan - matches containers with any build_id
            # Pattern: {model-slug}-app{num}[-{build_id}]_{backend|frontend}
            safe_model = model.replace('/', '-').replace('_', '-').replace('.', '-')
            prefix_pattern = re.compile(
                rf'^{re.escape(safe_model)}-app{app_num}(-[a-f0-9]+)?_(backend|frontend)$'
            )
            for c in all_containers:
                if prefix_pattern.match(c.name):
                    results.append(_c_dict(c))
            
            return results
        except Exception as e:  # pragma: no cover
            self.logger.error("Error getting project containers: %s", e)
            return results
    
    def start_containers(self, model: str, app_num: int, wait_for_healthy: bool = True,
                         timeout_seconds: Optional[int] = None,
                         build_id: Optional[str] = None) -> Dict[str, Any]:
        """Start containers for a model/app using docker-compose.
        
        Args:
            model: Model slug
            app_num: Application number
            wait_for_healthy: If True, wait for containers to become healthy (default: True)
            timeout_seconds: Max seconds to wait for health (default: CONTAINER_READY_TIMEOUT env, or 180s)
            build_id: Optional short UUID for unique container naming
        
        Returns:
            Dict with success status, health check results, and any errors
        """
        import os
        
        compose_path = self._get_compose_path(model, app_num)
        if not compose_path.exists():
            return {
                'success': False,
                'error': f'Docker compose file not found: {compose_path}'
            }
        
        # If no build_id provided, try running containers first, then database
        if not build_id:
            build_id = self.get_running_build_id(model, app_num)
        if not build_id:
            build_id = self._get_or_create_build_id(model, app_num, force_new=False)
        
        result = self._execute_compose_command(
            compose_path, ['up', '-d'], model, app_num, build_id=build_id
        )
        
        if not result.get('success'):
            return result
        
        # Optionally wait for containers to become healthy
        if wait_for_healthy:
            # Use env var or default to 180s (must exceed healthcheck start_period + interval)
            if timeout_seconds is None:
                timeout_seconds = int(os.environ.get('CONTAINER_READY_TIMEOUT', '180'))
            
            health_result = self._wait_for_container_health(
                model, app_num, timeout_seconds=timeout_seconds, build_id=build_id
            )
            result['health_check'] = health_result
            
            # Check if containers are in a crash loop (permanent failure)
            if not health_result.get('all_healthy'):
                crash_check = self._check_for_crash_loop(model, app_num, build_id=build_id)
                result['crash_loop'] = crash_check
                
                if crash_check.get('has_crash_loop'):
                    # Permanent failure - don't mark as success
                    result['success'] = False
                    result['error'] = f"Container crash loop detected: {crash_check.get('crash_containers', [])}"
                    self.logger.error(
                        "[START] Crash loop detected for %s/app%s: %s",
                        model, app_num, crash_check.get('crash_containers', [])
                    )
        
        return result
    
    def stop_containers(self, model: str, app_num: int, build_id: Optional[str] = None) -> Dict[str, Any]:
        """Stop containers for a model/app using docker-compose.
        
        Args:
            model: Model slug
            app_num: Application number
            build_id: Optional short UUID for unique container naming
        """
        compose_path = self._get_compose_path(model, app_num)
        if not compose_path.exists():
            return {
                'success': False,
                'error': f'Docker compose file not found: {compose_path}'
            }
        
        # If no build_id provided, try to get from running containers first (no app context needed)
        if not build_id:
            build_id = self.get_running_build_id(model, app_num)
        if not build_id:
            build_id = self._get_or_create_build_id(model, app_num, force_new=False)
        
        return self._execute_compose_command(
            compose_path, ['down', '--remove-orphans'], model, app_num, build_id=build_id
        )
    
    def restart_containers(self, model: str, app_num: int, build_id: Optional[str] = None) -> Dict[str, Any]:
        """Restart containers for a model/app.
        
        Args:
            model: Model slug
            app_num: Application number
            build_id: Optional short UUID for unique container naming
        """
        # If no build_id provided, try running containers first, then database
        if not build_id:
            build_id = self.get_running_build_id(model, app_num)
        if not build_id:
            build_id = self._get_or_create_build_id(model, app_num, force_new=False)
        
        # Stop first
        stop_result = self.stop_containers(model, app_num, build_id=build_id)
        if not stop_result.get('success', False):
            return stop_result

        # Then start
        return self.start_containers(model, app_num, build_id=build_id)

    def get_container_health(self, model: str, app_num: int, build_id: Optional[str] = None) -> Dict[str, Any]:
        """Get current health status of containers without waiting.

        Public wrapper for getting immediate health status of app containers.
        Uses smart container discovery to find containers with any build_id.

        Args:
            model: Model slug
            app_num: Application number
            build_id: Optional short UUID for unique container naming (if None, discovers any running containers)

        Returns:
            Dictionary with health status information:
            - all_healthy: bool - True if all containers are healthy
            - containers: dict - Per-container health info
            - container_count: int - Number of containers found
            - build_id: str - The build_id of discovered containers
        """
        try:
            # Use smart container discovery that finds containers with any build_id
            discovered_containers = self.get_project_containers(model, app_num)
            
            if not discovered_containers:
                return {
                    'all_healthy': False,
                    'containers': {},
                    'container_count': 0,
                    'message': 'No containers found',
                    'build_id': None
                }
            
            # Get the build_id from discovered containers
            discovered_build_id = None
            for c in discovered_containers:
                if c.get('build_id'):
                    discovered_build_id = c.get('build_id')
                    break
            
            # Now get detailed health status for these containers
            container_status = {}
            all_healthy = True
            
            for c_info in discovered_containers:
                container_name = c_info.get('name', 'unknown')
                try:
                    container = self.client.containers.get(container_name)
                    health_status = container.attrs.get('State', {}).get('Health', {}).get('Status')
                    state = container.attrs.get('State', {})
                    status = state.get('Status', 'unknown')
                    
                    container_status[container_name] = {
                        'health': health_status or 'no_healthcheck',
                        'status': status,
                        'running': status == 'running'
                    }
                    
                    # Check if this container counts as "healthy"
                    if health_status not in ['healthy', None]:  # None means no healthcheck
                        all_healthy = False
                    elif status != 'running':
                        all_healthy = False
                except Exception as e:
                    self.logger.debug("Could not get health for container %s: %s", container_name, e)
                    container_status[container_name] = {
                        'health': 'unknown',
                        'status': 'unknown',
                        'running': False,
                        'error': str(e)
                    }
                    all_healthy = False

            return {
                'all_healthy': all_healthy,
                'containers': container_status,
                'container_count': len(discovered_containers),
                'build_id': discovered_build_id
            }

        except Exception as e:
            self.logger.warning("Error getting container health for %s/app%s: %s", model, app_num, e)
            return {
                'all_healthy': False,
                'containers': {},
                'container_count': 0,
                'error': str(e),
                'build_id': None
            }

    def _check_for_crash_loop(self, model: str, app_num: int,
                               build_id: Optional[str] = None) -> Dict[str, Any]:
        """Check if any containers are in a crash/restart loop.
        
        Detects containers that are continuously restarting due to application errors.
        This is a permanent failure state that won't be fixed by waiting longer.
        
        Args:
            model: Model slug
            app_num: Application number
            build_id: Optional short UUID for unique container naming
        
        Returns:
            Dict with has_crash_loop boolean and list of affected containers
        """
        if not self.client:
            return {'has_crash_loop': False, 'error': 'Docker client unavailable'}
        
        project_name = self._get_project_name(model, app_num, build_id)
        crash_containers = []
        
        try:
            containers = self.client.containers.list(
                all=True,
                filters={'label': f'com.docker.compose.project={project_name}'}
            )
            
            for container in containers:
                status = container.status.lower()
                # Check for restarting state or high restart count
                if status == 'restarting':
                    crash_containers.append({
                        'name': container.name,
                        'status': status,
                        'reason': 'Container is in restarting state'
                    })
                elif status == 'exited':
                    # Check exit code - non-zero indicates crash
                    exit_code = container.attrs.get('State', {}).get('ExitCode', 0)
                    if exit_code != 0:
                        crash_containers.append({
                            'name': container.name,
                            'status': status,
                            'exit_code': exit_code,
                            'reason': f'Container exited with code {exit_code}'
                        })
            
            return {
                'has_crash_loop': len(crash_containers) > 0,
                'crash_containers': crash_containers
            }
        except Exception as e:
            self.logger.warning("Error checking for crash loop: %s", e)
            return {'has_crash_loop': False, 'error': str(e)}
    
    def _wait_for_container_health(self, model: str, app_num: int, 
                                    timeout_seconds: int = 180,
                                    build_id: Optional[str] = None) -> Dict[str, Any]:
        """Wait for containers to become healthy after startup.
        
        Polls container health status with retries to handle slow startup times.
        Addresses intermittent health check failures that skip analysis subtasks.
        Also detects crash loops early to fail fast on permanent errors.
        
        Args:
            model: Model slug
            app_num: Application number
            timeout_seconds: Maximum time to wait for health (default: 180s to exceed
                           docker-compose healthcheck start_period + interval)
            build_id: Optional short UUID for unique container naming
        
        Returns:
            Dictionary with health check results
        """
        import time
        
        project_name = self._get_project_name(model, app_num, build_id)
        start_time = time.time()
        poll_interval = 2  # seconds
        
        self.logger.info(
            "[HEALTH] Waiting up to %ds for containers to become healthy: %s/app%s (build_id=%s)",
            timeout_seconds, model, app_num, build_id
        )
        
        while (time.time() - start_time) < timeout_seconds:
            try:
                containers = self.client.containers.list(
                    filters={'label': f'com.docker.compose.project={project_name}'}
                )
                
                if not containers:
                    self.logger.debug("[HEALTH] No containers found yet for %s", project_name)
                    time.sleep(poll_interval)
                    continue
                
                all_healthy = True
                unhealthy = []
                
                for container in containers:
                    health_status = container.attrs.get('State', {}).get('Health', {}).get('Status')
                    container_name = container.name
                    
                    if health_status == 'healthy':
                        continue
                    elif health_status == 'unhealthy':
                        all_healthy = False
                        unhealthy.append(container_name)
                    elif health_status in (None, 'none'):
                        # Container has no health check defined - consider it healthy
                        continue
                    else:
                        # Starting state - keep waiting
                        all_healthy = False
                
                if all_healthy:
                    elapsed = time.time() - start_time
                    self.logger.info(
                        "[HEALTH] All containers healthy for %s/app%s (took %.1fs)",
                        model, app_num, elapsed
                    )
                    return {
                        'all_healthy': True,
                        'elapsed_seconds': elapsed,
                        'container_count': len(containers)
                    }
                
                if unhealthy:
                    self.logger.debug(
                        "[HEALTH] Waiting for containers to become healthy: %s",
                        ', '.join(unhealthy)
                    )
                
                # Check for crash loops periodically (every 4th poll = ~8 seconds)
                elapsed = time.time() - start_time
                if int(elapsed) % 8 == 0 and elapsed > 5:
                    crash_check = self._check_for_crash_loop(model, app_num)
                    if crash_check.get('has_crash_loop'):
                        self.logger.warning(
                            "[HEALTH] Crash loop detected during health wait for %s/app%s: %s",
                            model, app_num, crash_check.get('crash_containers', [])
                        )
                        return {
                            'all_healthy': False,
                            'elapsed_seconds': elapsed,
                            'crash_loop': True,
                            'crash_containers': crash_check.get('crash_containers', [])
                        }
                
                time.sleep(poll_interval)
                
            except Exception as e:
                self.logger.warning(
                    "[HEALTH] Error checking container health for %s/app%s: %s",
                    model, app_num, e
                )
                time.sleep(poll_interval)
        
        # Timeout reached
        elapsed = time.time() - start_time
        self.logger.warning(
            "[HEALTH] Health check timeout after %.1fs for %s/app%s",
            elapsed, model, app_num
        )
        
        # Get final container states for diagnostics
        try:
            containers = self.client.containers.list(
                filters={'label': f'com.docker.compose.project={project_name}'}
            )
            states = {}
            for container in containers:
                health_status = container.attrs.get('State', {}).get('Health', {}).get('Status')
                states[container.name] = health_status or 'no_healthcheck'
            
            return {
                'all_healthy': False,
                'elapsed_seconds': elapsed,
                'timeout': True,
                'container_states': states
            }
        except Exception:
            return {
                'all_healthy': False,
                'elapsed_seconds': elapsed,
                'timeout': True,
                'error': 'Could not retrieve container states'
            }
    
    def _cleanup_images_before_build(self, model: str, app_num: int) -> Dict[str, Any]:
        """Clean up existing images for model/app to prevent conflicts.
        
        Addresses 'image already exists' errors that can block builds.
        Uses 'docker compose down --remove-orphans --rmi local' to clean state.
        """
        compose_path = self._get_compose_path(model, app_num)
        if not compose_path.exists():
            return {'success': True, 'message': 'No compose file, skipping cleanup'}
        
        self.logger.info("Pre-build cleanup for %s/app%s: removing existing images", model, app_num)
        cleanup_result = self._execute_compose_command(
            compose_path,
            ['down', '--remove-orphans', '--rmi', 'local'],
            model,
            app_num,
            timeout=120
        )
        
        if cleanup_result.get('success'):
            self.logger.info("Pre-build cleanup succeeded for %s/app%s", model, app_num)
        else:
            # Log warning but don't fail - cleanup failure shouldn't block build attempt
            self.logger.warning(
                "Pre-build cleanup had issues for %s/app%s (continuing anyway): %s",
                model, app_num, cleanup_result.get('error', 'unknown')
            )
        
        return cleanup_result
    
    def build_containers(self, model: str, app_num: int, no_cache: bool = True, start_after: bool = True) -> Dict[str, Any]:
        """Build containers for a model/app using docker-compose.

        If start_after=True (default) and build succeeds, will run 'up -d' to
        bring containers online so UI reflects a running state immediately.
        
        Includes automatic image cleanup before build to prevent conflicts.
        Uses per-app locks to prevent race conditions during parallel builds.
        """
        # Acquire per-app build lock to prevent parallel builds for same model/app
        lock_key = f"{model}:app{app_num}"
        with _build_locks_lock:
            if lock_key not in _build_locks:
                _build_locks[lock_key] = threading.Lock()
            build_lock = _build_locks[lock_key]
        
        # Try to acquire lock with timeout to avoid indefinite blocking
        lock_acquired = build_lock.acquire(timeout=600)  # 10 minute timeout
        if not lock_acquired:
            self.logger.warning(
                "Build lock timeout for %s/app%s - another build may be stuck",
                model, app_num
            )
            return {
                'success': False,
                'error': f'Could not acquire build lock for {model}/app{app_num} (timeout after 600s)'
            }
        
        try:
            return self._build_containers_impl(model, app_num, no_cache, start_after)
        finally:
            build_lock.release()
    
    def _build_containers_impl(self, model: str, app_num: int, no_cache: bool, start_after: bool) -> Dict[str, Any]:
        """Internal implementation of build_containers (called with lock held)."""
        compose_path = self._get_compose_path(model, app_num)
        if not compose_path.exists():
            return {
                'success': False,
                'error': f'Docker compose file not found: {compose_path}'
            }
        
        # Generate new build_id for this build to ensure unique container names
        build_id = self._get_or_create_build_id(model, app_num, force_new=no_cache)
        self.logger.info("Building containers for %s/app%s with build_id=%s", model, app_num, build_id)
        
        # Clean up existing images to prevent conflicts
        cleanup_result = self._cleanup_images_before_build(model, app_num)
        
        cmd = ['build']
        if no_cache:
            cmd.append('--no-cache')
        
        # Use retry wrapper for build command (most failure-prone operation)
        build_result = self._execute_compose_with_retry(
            compose_path, cmd, model, app_num,
            timeout=600,  # 10 minutes for build
            max_retries=3,
            operation_name='build',
            build_id=build_id
        )
        if not build_result.get('success') or not start_after:
            return build_result

        # Start containers (docker compose up -d)
        up_result = self._execute_compose_command(
            compose_path, ['up', '-d'], model, app_num, timeout=300, build_id=build_id
        )
        
        # Wait for containers to become healthy (addresses intermittent health check failures)
        if up_result.get('success'):
            health_result = self._wait_for_container_health(model, app_num, timeout_seconds=180, build_id=build_id)
            up_result['health_check'] = health_result
            if not health_result.get('all_healthy'):
                self.logger.warning(
                    "Containers started but not all became healthy for %s/app%s: %s. Cleaning up...",
                    model, app_num, health_result.get('unhealthy_containers', [])
                )
                # Cleanup on health failure to prevent "failing containers" from lingering
                self.stop_containers(model, app_num, build_id=build_id)
                # Mark as failed in the result
                up_result['success'] = False
                up_result['error'] = f"Containers failed health check: {health_result.get('unhealthy_containers', [])}"
        else:
             # Cleanup on start failure (e.g. port conflict)
             self.logger.warning(
                 "Container start failed for %s/app%s. Cleaning up...", model, app_num
             )
             self.stop_containers(model, app_num, build_id=build_id)

        # Merge summaries
        merged = {
            'success': build_result.get('success') and up_result.get('success'),
            'build': build_result,
            'up': up_result,
            'build_id': build_id
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

        Uses the centralized get_app_directory() helper to support both flat
        and template-based directory structures automatically.

        Returns the path to docker-compose.yml within the resolved app directory.
        """
        from app.utils.helpers import get_app_directory
        
        app_dir = get_app_directory(model, app_num)
        compose_path = app_dir / 'docker-compose.yml'
        return compose_path

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
    
    def _get_project_name(self, model: str, app_num: int, build_id: Optional[str] = None) -> str:
        """Get Docker Compose project name for model/app.
        
        Args:
            model: Model slug
            app_num: Application number
            build_id: Optional short UUID for unique container naming (e.g., 'a3f2c1b9')
        
        Returns:
            Project name like 'model-name-app1-a3f2c1b9' or 'model-name-app1' if no build_id
        """
        # Replace underscores and dots with hyphens for Docker compatibility
        safe_model = model.replace('/', '-').replace('_', '-').replace('.', '-')
        if build_id:
            return f"{safe_model}-app{app_num}-{build_id}"
        return f"{safe_model}-app{app_num}"
    
    def _generate_build_id(self) -> str:
        """Generate a short UUID for unique container naming."""
        import uuid
        return uuid.uuid4().hex[:8]
    
    def _get_or_create_build_id(self, model: str, app_num: int, force_new: bool = False) -> Optional[str]:
        """Get existing build_id from database or create a new one.
        
        Args:
            model: Model slug
            app_num: Application number
            force_new: If True, always generate a new build_id (for rebuilds)
        
        Returns:
            Build ID string or None if app not found
        """
        from flask import current_app
        from app.models import GeneratedApplication
        from app.extensions import db
        
        try:
            with current_app.app_context():
                app = GeneratedApplication.query.filter_by(
                    model_slug=model, app_number=app_num
                ).first()
                
                if not app:
                    self.logger.warning(f"App not found for build_id lookup: {model}/app{app_num}")
                    return self._generate_build_id()  # Generate anyway for standalone builds
                
                if force_new or not app.build_id:
                    app.build_id = self._generate_build_id()
                    db.session.commit()
                    self.logger.info(f"Generated new build_id for {model}/app{app_num}: {app.build_id}")
                
                return app.build_id
        except Exception as e:
            self.logger.warning(f"Could not get/create build_id: {e}, generating new one")
            return self._generate_build_id()
    
    def _execute_compose_with_retry(self, compose_path: Path, command: List[str],
                                   model: str, app_num: int, timeout: int = 300,
                                   max_retries: int = 3, operation_name: str = 'compose',
                                   build_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute docker compose command with exponential backoff retry logic.
        
        Handles transient BuildKit failures that occur at Dockerfile:59 (React build step).
        Retries with delays: 2s, 4s, 8s (exponential backoff).
        
        Args:
            compose_path: Path to docker-compose.yml
            command: Compose command to execute (e.g., ['build'])
            model: Model slug
            app_num: Application number
            timeout: Command timeout in seconds
            max_retries: Maximum retry attempts (default: 3)
            operation_name: Human-readable operation name for logging
            build_id: Optional short UUID for unique container naming
        
        Returns:
            Result dictionary with success/error information
        """
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            self.logger.info(
                "[RETRY] Attempt %d/%d for %s operation: %s/app%s (build_id=%s)",
                attempt, max_retries, operation_name, model, app_num, build_id
            )
            
            result = self._execute_compose_command(
                compose_path, command, model, app_num, timeout, build_id=build_id
            )
            
            if result.get('success'):
                if attempt > 1:
                    self.logger.info(
                        "[RETRY] %s operation succeeded on attempt %d for %s/app%s",
                        operation_name, attempt, model, app_num
                    )
                return result
            
            last_error = result.get('error', 'Unknown error')
            stderr = result.get('stderr', '')
            
            # Check if this is a retryable error (BuildKit, network issues)
            is_retryable = any([
                'buildkit' in str(last_error).lower(),
                'buildkit' in stderr.lower(),
                'solver' in stderr.lower(),
                'network' in str(last_error).lower(),
                'timeout' in str(last_error).lower(),
                'temporary failure' in str(last_error).lower(),
            ])
            
            if not is_retryable:
                self.logger.warning(
                    "[RETRY] Non-retryable error for %s operation %s/app%s: %s",
                    operation_name, model, app_num, last_error
                )
                return result
            
            if attempt < max_retries:
                # Exponential backoff: 2s, 4s, 8s
                delay = 2 ** attempt
                self.logger.warning(
                    "[RETRY] %s operation failed (attempt %d/%d) for %s/app%s: %s. "
                    "Retrying in %ds...",
                    operation_name, attempt, max_retries, model, app_num,
                    last_error, delay
                )
                time.sleep(delay)
            else:
                self.logger.error(
                    "[RETRY] %s operation failed after %d attempts for %s/app%s: %s",
                    operation_name, max_retries, model, app_num, last_error
                )
        
        # All retries exhausted
        return {
            'success': False,
            'error': f'{operation_name} failed after {max_retries} attempts: {last_error}',
            'last_error': last_error,
            'attempts': max_retries
        }
    
    def _execute_compose_command(self, compose_path: Path, command: List[str], 
                                model: str, app_num: int, timeout: int = 300,
                                build_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute a docker compose command (v2 preferred, v1 fallback).

        Adds richer logging so we can debug why UI build/start buttons may
        appear to do nothing. Returns structured result including stdout/stderr.
        
        Args:
            compose_path: Path to docker-compose.yml
            command: Compose command arguments (e.g., ['build', '--no-cache'])
            model: Model slug
            app_num: Application number
            timeout: Command timeout in seconds
            build_id: Optional short UUID for unique container naming
        """
        import subprocess

        docker_path = shutil.which('docker')
        docker_compose_path = shutil.which('docker-compose')
        # Pre-compute project name for diagnostics (was previously referenced before assignment)
        project_name = self._get_project_name(model, app_num, build_id)
        cli_diagnostics: Dict[str, Any] = {
            'docker_in_path': bool(docker_path),
            'docker_compose_in_path': bool(docker_compose_path),
            'project_name': project_name,
            'build_id': build_id,
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
            "Compose exec variant=%s docker_path=%s compose_path=%s project=%s build_id=%s action=%s cwd=%s",
            compose_variant,
            docker_path or docker_compose_path,
            compose_path,
            project_name,
            build_id,
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
        """Summarize container statuses for the model/app pair.
        
        Returns:
            Dict with:
                - model: Model slug
                - app_num: App number
                - containers_found: Number of containers discovered
                - states: List of unique container states
                - containers: List of container dicts
                - build_ids: Set of build_ids found (for containers with build_id)
                - active_build_id: The build_id of running containers (if any)
        """
        containers = self.get_project_containers(model, app_num)
        states = {c['status'] for c in containers} if containers else set()
        
        # Extract build_ids from discovered containers
        build_ids = set(c.get('build_id') for c in containers if c.get('build_id'))
        
        # Find the build_id of running containers (prefer running over stopped)
        active_build_id = None
        for c in containers:
            if c.get('status') == 'running' and c.get('build_id'):
                active_build_id = c.get('build_id')
                break
        # Fallback to any build_id if no running containers
        if not active_build_id and build_ids:
            active_build_id = next(iter(build_ids))
        
        return {
            'model': model,
            'app_num': app_num,
            'containers_found': len(containers),
            'states': list(states),
            'containers': containers,
            'build_ids': list(build_ids),
            'active_build_id': active_build_id,
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
