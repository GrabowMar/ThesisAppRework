"""
Docker Manager Service for Celery App

Manages Docker container operations for AI-generated applications.
Provides container lifecycle management, health monitoring, and log retrieval.
"""

import logging
import docker
from docker.errors import NotFound as DockerNotFound
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


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
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.models_dir = self.project_root / "misc" / "models"
    
    def _create_docker_client(self) -> Optional[docker.DockerClient]:
        """Create Docker client with Windows support."""
        try:
            # Try Windows named pipe first
            client = docker.DockerClient(base_url='npipe:////./pipe/docker_engine')
            client.ping()
            self.logger.info("Connected to Docker via Windows named pipe")
            return client
        except Exception:
            try:
                # Fallback to default
                client = docker.from_env()
                client.ping()
                self.logger.info("Connected to Docker via default client")
                return client
            except Exception as e:
                self.logger.error(f"Failed to connect to Docker: {e}")
                return None
    
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
        """Get all containers for a specific model/app project."""
        if not self.client:
            return []
        
        try:
            project_name = self._get_project_name(model, app_num)
            containers = self.client.containers.list(
                all=True,
                filters={'label': f'com.docker.compose.project={project_name}'}
            )
            
            result = []
            for container in containers:
                result.append({
                    'id': container.id,
                    'name': container.name,
                    'status': container.status,
                    'image': container.image.tags[0] if container.image.tags else 'unknown',
                    'ports': container.ports,
                    'labels': container.labels
                })
            
            return result
        except Exception as e:
            self.logger.error(f"Error getting project containers: {e}")
            return []
    
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
    
    def build_containers(self, model: str, app_num: int, no_cache: bool = True) -> Dict[str, Any]:
        """Build containers for a model/app using docker-compose."""
        compose_path = self._get_compose_path(model, app_num)
        if not compose_path.exists():
            return {
                'success': False,
                'error': f'Docker compose file not found: {compose_path}'
            }
        
        cmd = ['build']
        if no_cache:
            cmd.append('--no-cache')
        
        return self._execute_compose_command(
            compose_path, cmd, model, app_num, timeout=600  # 10 minutes for build
        )
    
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
                name_prefixes = [
                    f"{project_name}_{desired_service}",  # e.g., proj_backend
                    f"{project_name}-{desired_service}",  # e.g., proj-backend
                ]
                for c in self.client.containers.list(all=True):
                    try:
                        nm = c.name
                        if any(nm.startswith(pref) for pref in name_prefixes):
                            target = c
                            break
                    except Exception:
                        continue

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
        """Get path to docker-compose.yml for model/app."""
        return self.models_dir / model / f"app{app_num}" / "docker-compose.yml"
    
    def _get_project_name(self, model: str, app_num: int) -> str:
        """Get Docker Compose project name for model/app."""
        # Replace underscores and dots with hyphens for Docker compatibility
        safe_model = model.replace('_', '-').replace('.', '-')
        return f"{safe_model}-app{app_num}"
    
    def _execute_compose_command(self, compose_path: Path, command: List[str], 
                                model: str, app_num: int, timeout: int = 300) -> Dict[str, Any]:
        """Execute a docker-compose command."""
        import subprocess
        import shutil
        
        cmd = []  # Initialize cmd variable
        
        try:
            project_name = self._get_project_name(model, app_num)
            
            # Prefer modern 'docker compose', fallback to legacy 'docker-compose'
            if shutil.which('docker'):
                base_cmd = ['docker', 'compose']
            elif shutil.which('docker-compose'):
                base_cmd = ['docker-compose']
            else:
                return {
                    'success': False,
                    'error': 'Neither docker nor docker-compose CLI is available in PATH',
                    'command': ''
                }

            # Build the full command
            cmd = base_cmd + [
                '-f', str(compose_path),
                '-p', project_name
            ] + command
            
            self.logger.info(f"Executing: {' '.join(cmd)}")
            
            # Change to the directory containing docker-compose.yml
            cwd = compose_path.parent
            
            # Execute the command
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            success = result.returncode == 0
            
            return {
                'success': success,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'command': ' '.join(cmd)
            }
            
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f'Command timed out after {timeout} seconds',
                'command': ' '.join(cmd)
            }
        except Exception as e:
            self.logger.error(f"Error executing compose command: {e}")
            return {
                'success': False,
                'error': str(e),
                'command': ' '.join(cmd)
            }
    
    def list_all_containers(self) -> List[Dict[str, Any]]:
        """List all Docker containers."""
        if not self.client:
            return []
        
        try:
            containers = self.client.containers.list(all=True)
            result = []
            
            for container in containers:
                result.append({
                    'id': container.id[:12],  # Short ID
                    'name': container.name,
                    'status': container.status,
                    'image': container.image.tags[0] if container.image.tags else 'unknown',
                    'ports': container.ports,
                    'created': container.attrs['Created'],
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
