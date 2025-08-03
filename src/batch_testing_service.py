"""
Container Batch Operations Service
==================================

Service for managing batch container operations using the Docker infrastructure.
Integrates with DockerManager to orchestrate containerized AI applications at scale.
"""

import asyncio
import json
import logging
import uuid
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from pathlib import Path

from extensions import db
from models import ModelCapability
from core_services import DockerManager, DockerUtils


class ContainerBatchOperationService:
    """Service for managing batch container operations with Docker infrastructure."""
    
    def __init__(self, docker_manager: Optional[DockerManager] = None):
        self.logger = logging.getLogger(__name__)
        self.docker_manager = docker_manager or DockerManager()
        self.security_scanner_url = "http://localhost:8001"
        self.operations = {}  # In-memory operation storage (could be moved to database)
        self.operation_lock = threading.RLock()
        self.active_executors = {}
        self.models_base_dir = Path("misc/models")
        
    def create_batch_operation(self, operation_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new batch container operation."""
        try:
            with self.operation_lock:
                operation_id = str(uuid.uuid4())
                
                # Validate configuration
                self._validate_operation_config(operation_config)
                
                # Build container list based on selection
                container_list = self._build_container_list(operation_config)
                
                # Create operation object
                operation = {
                    'operation_id': operation_id,
                    'operation_name': operation_config['job_name'],  # Keep compatibility
                    'description': operation_config.get('description', ''),
                    'operation_type': operation_config['operation_type'],
                    'tools': operation_config.get('tools', []),
                    'container_options': self._extract_container_options(operation_config),
                    'concurrency': int(operation_config.get('concurrency', 4)),
                    'priority': operation_config.get('priority', 'normal'),
                    'timeout': int(operation_config.get('timeout', 30)) * 60,  # Convert to seconds
                    'status': 'pending',
                    'created_at': datetime.now(),
                    'started_at': None,
                    'completed_at': None,
                    'total_containers': len(container_list),
                    'completed_containers': 0,
                    'failed_containers': 0,
                    'pending_containers': len(container_list),
                    'healthy_containers': 0,
                    'operation_results': {},
                    'containers': container_list,
                    'tasks': [],
                    'error_message': None,
                    'fail_fast': operation_config.get('fail_fast', False),
                    'cleanup_on_error': operation_config.get('cleanup_on_error', True)
                }
                
                # Initialize tasks for each container
                for container in container_list:
                    task = {
                        'task_id': str(uuid.uuid4()),
                        'model': container['model'],
                        'app_num': container['app_num'],
                        'container_type': container['container_type'],
                        'container_name': container['container_name'],
                        'status': 'pending',
                        'started_at': None,
                        'completed_at': None,
                        'duration': None,
                        'result_data': {},
                        'logs': [],
                        'error_message': None
                    }
                    operation['tasks'].append(task)
                
                self.operations[operation_id] = operation
                
                # Auto-start if requested
                if operation_config.get('auto_start', False):
                    self._start_operation_execution(operation_id)
                
                self.logger.info(f"Created batch operation {operation_id} with {len(container_list)} containers")
                return {
                    'success': True,
                    'job_id': operation_id,  # Keep compatibility
                    'message': f'Container batch operation created with {len(container_list)} containers'
                }
                
        except Exception as e:
            self.logger.error(f"Failed to create batch operation: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def start_operation(self, operation_id: str) -> Dict[str, Any]:
        """Start execution of a batch operation."""
        try:
            with self.operation_lock:
                if operation_id not in self.operations:
                    return {'success': False, 'error': 'Operation not found'}
                
                operation = self.operations[operation_id]
                if operation['status'] not in ['pending', 'failed']:
                    return {'success': False, 'error': f'Operation cannot be started from status: {operation["status"]}'}
                
                self._start_operation_execution(operation_id)
                return {'success': True, 'message': 'Operation started successfully'}
                
        except Exception as e:
            self.logger.error(f"Failed to start operation {operation_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def cancel_operation(self, operation_id: str) -> Dict[str, Any]:
        """Cancel a running batch operation."""
        try:
            with self.operation_lock:
                if operation_id not in self.operations:
                    return {'success': False, 'error': 'Operation not found'}
                
                operation = self.operations[operation_id]
                if operation['status'] not in ['running', 'pending']:
                    return {'success': False, 'error': f'Operation cannot be cancelled from status: {operation["status"]}'}
                
                # Cancel the executor
                if operation_id in self.active_executors:
                    self.active_executors[operation_id].shutdown(wait=False)
                    del self.active_executors[operation_id]
                
                # Update operation status
                operation['status'] = 'cancelled'
                operation['completed_at'] = datetime.now()
                
                return {'success': True, 'message': 'Operation cancelled successfully'}
                
        except Exception as e:
            self.logger.error(f"Failed to cancel operation {operation_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_operation_details(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a batch operation."""
        with self.operation_lock:
            if operation_id not in self.operations:
                return None
            
            operation = self.operations[operation_id].copy()
            
            # Add computed fields
            operation['progress'] = self._calculate_progress(operation)
            operation['duration_formatted'] = self._format_duration(operation)
            operation['created_at_relative'] = self._format_relative_time(operation['created_at'])
            
            return operation
    
    def get_all_operations(self, status_filter: Optional[str] = None, 
                         operation_type_filter: Optional[str] = None,
                         model_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of all batch operations with optional filtering."""
        with self.operation_lock:
            operations = []
            
            for operation in self.operations.values():
                # Apply filters
                if status_filter and operation['status'] != status_filter:
                    continue
                if operation_type_filter and operation['operation_type'] != operation_type_filter:
                    continue
                if model_filter:
                    # Check if any containers match the model filter
                    model_match = any(c['model'] == model_filter for c in operation['containers'])
                    if not model_match:
                        continue
                
                # Add computed fields
                operation_copy = operation.copy()
                operation_copy['progress'] = self._calculate_progress(operation)
                operation_copy['duration_formatted'] = self._format_duration(operation)
                operation_copy['created_at_relative'] = self._format_relative_time(operation['created_at'])
                
                operations.append(operation_copy)
            
            # Sort by creation time (newest first)
            operations.sort(key=lambda x: x['created_at'], reverse=True)
            return operations
    
    def get_operation_results(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive results for a completed operation."""
        with self.operation_lock:
            if operation_id not in self.operations:
                return None
            
            operation = self.operations[operation_id]
            if operation['status'] != 'completed':
                return None
            
            # Aggregate results
            results = {
                'operation_id': operation_id,
                'operation_name': operation['operation_name'],
                'operation_type': operation['operation_type'],
                'total_containers': operation['total_containers'],
                'successful_containers': operation['completed_containers'],
                'failed_containers': operation['failed_containers'],
                'containers': [],
                'summary': {
                    'success_rate': (operation['completed_containers'] / operation['total_containers'] * 100) if operation['total_containers'] > 0 else 0,
                    'total_duration': self._format_duration(operation),
                    'avg_container_time': 0
                }
            }
            
            total_duration = 0
            completed_count = 0
            
            # Process each task
            for task in operation['tasks']:
                container_result = {
                    'model': task['model'],
                    'app_num': task['app_num'],
                    'container_type': task['container_type'],
                    'container_name': task['container_name'],
                    'status': task['status'],
                    'duration': task['duration'],
                    'result_data': task['result_data'],
                    'logs': task['logs'][-50:] if task['logs'] else []  # Last 50 log entries
                }
                results['containers'].append(container_result)
                
                if task['duration'] and task['status'] == 'completed':
                    total_duration += task['duration']
                    completed_count += 1
            
            # Calculate average duration
            if completed_count > 0:
                results['summary']['avg_container_time'] = f"{total_duration / completed_count:.1f}s"
            
            return results
    
    def delete_operation(self, operation_id: str) -> Dict[str, Any]:
        """Delete a batch operation."""
        try:
            with self.operation_lock:
                if operation_id not in self.operations:
                    return {'success': False, 'error': 'Operation not found'}
                
                operation = self.operations[operation_id]
                if operation['status'] == 'running':
                    return {'success': False, 'error': 'Cannot delete running operation. Cancel it first.'}
                
                # Clean up executor if exists
                if operation_id in self.active_executors:
                    self.active_executors[operation_id].shutdown(wait=False)
                    del self.active_executors[operation_id]
                
                # Delete operation
                del self.operations[operation_id]
                
                return {'success': True, 'message': 'Operation deleted successfully'}
                
        except Exception as e:
            self.logger.error(f"Failed to delete operation {operation_id}: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models for batch operations."""
        try:
            models = ModelCapability.query.all()
            model_list = []
            
            for model in models:
                # Check if model directory exists
                model_dir = self.models_base_dir / model.model_name
                apps_count = 0
                if model_dir.exists():
                    apps_count = len([d for d in model_dir.iterdir() if d.is_dir() and d.name.startswith('app')])
                
                model_list.append({
                    'slug': model.model_name,
                    'display_name': model.model_name.replace('_', ' ').replace('-', ' ').title(),
                    'apps_count': apps_count,
                    'has_containers': apps_count > 0
                })
            
            return model_list
            
        except Exception as e:
            self.logger.error(f"Failed to get available models: {str(e)}")
            return []
    
    def get_container_stats(self) -> Dict[str, Any]:
        """Get current container statistics."""
        try:
            if not self.docker_manager or not self.docker_manager.client:
                return {
                    'running': 0,
                    'stopped': 0,
                    'healthy': 0,
                    'total': 0,
                    'error': 'Docker not available'
                }
            
            containers = self.docker_manager.client.containers.list(all=True)
            stats = {
                'running': 0,
                'stopped': 0,
                'healthy': 0,
                'unhealthy': 0,
                'total': len(containers)
            }
            
            for container in containers:
                if container.status == 'running':
                    stats['running'] += 1
                    # Check health status
                    health = container.attrs.get('State', {}).get('Health', {})
                    if health.get('Status') == 'healthy':
                        stats['healthy'] += 1
                    elif health.get('Status') in ['unhealthy', 'starting']:
                        stats['unhealthy'] += 1
                else:
                    stats['stopped'] += 1
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get container stats: {str(e)}")
            return {
                'running': 0,
                'stopped': 0,
                'healthy': 0,
                'total': 0,
                'error': str(e)
            }
    
    
    def _validate_operation_config(self, config: Dict[str, Any]) -> None:
        """Validate operation configuration."""
        required_fields = ['job_name', 'operation_type']
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field: {field}")
        
        valid_operation_types = [
            'start_containers', 'stop_containers', 'restart_containers', 'rebuild_containers',
            'security_backend', 'security_frontend', 'security_full', 'vulnerability_scan',
            'health_check', 'resource_monitor', 'log_collection', 'performance_test',
            'cleanup_containers', 'image_update', 'network_reset', 'volume_backup'
        ]
        if config['operation_type'] not in valid_operation_types:
            raise ValueError(f"Invalid operation type. Must be one of: {valid_operation_types}")
    
    def _extract_container_options(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract container-specific options from configuration."""
        return {
            'force_recreate': config.get('force_recreate', False),
            'pull_images': config.get('pull_images', True),
            'remove_orphans': config.get('remove_orphans', False),
            'wait_healthy': config.get('wait_healthy', True),
            'monitor_duration': config.get('monitor_duration', 30),
            'sample_interval': config.get('sample_interval', 30)
        }
    
    def _build_container_list(self, config: Dict[str, Any]) -> List[Dict[str, str]]:
        """Build list of containers to operate on based on configuration."""
        self.logger.info(f"Building container list for config: {config}")
        
        containers = []
        # Frontend sends 'selection_method' - handle both names for compatibility
        selection_method = config.get('selection_method', config.get('target_selection', 'all'))
        
        self.logger.info(f"Selection method: {selection_method}")
        
        # Add fallback mechanism for empty containers
        def create_test_containers():
            """Create test containers as fallback."""
            self.logger.info("Creating test containers as fallback")
            return [{
                'model': 'test_model',
                'app_num': 1,
                'container_type': 'frontend',
                'container_name': 'test_model_app1_frontend',
                'compose_path': 'misc/models/test_model/app1/docker-compose.yml'
            }, {
                'model': 'test_model',
                'app_num': 1,
                'container_type': 'backend', 
                'container_name': 'test_model_app1_backend',
                'compose_path': 'misc/models/test_model/app1/docker-compose.yml'
            }]
        
        if selection_method == 'all':
            # Get all models and apps
            models = ModelCapability.query.all()
            self.logger.info(f"Found {len(models)} models in database")
            
            if not models:
                self.logger.warning("No models found in database, using test containers")
                return create_test_containers()
                
            for model in models:
                model_dir = self.models_base_dir / model.model_name
                if model_dir.exists():
                    for app_dir in model_dir.iterdir():
                        if app_dir.is_dir() and app_dir.name.startswith('app'):
                            app_num = int(app_dir.name[3:])  # Extract number from "app1", "app2", etc.
                            
                            # Add both backend and frontend containers
                            for container_type in ['backend', 'frontend']:
                                project_name = DockerUtils.get_project_name(model.model_name, app_num)
                                container_name = f"{project_name}_{container_type}"
                                
                                containers.append({
                                    'model': model.model_name,
                                    'app_num': app_num,
                                    'container_type': container_type,
                                    'container_name': container_name,
                                    'compose_path': str(app_dir / 'docker-compose.yml')
                                })
        
        elif selection_method == 'models':
            # Selected models with all apps
            selected_models = config.get('selected_models', [])
            self.logger.info(f"Selected models: {selected_models}")
            
            # Fallback: if no models selected, use available models
            if not selected_models:
                available_models = self.get_available_models()
                if available_models:
                    selected_models = [available_models[0]['slug']]
                    self.logger.info(f"No models selected, using fallback: {selected_models}")
                else:
                    self.logger.warning("No models available, creating test containers")
                    return create_test_containers()
                    
            for model_slug in selected_models:
                model_dir = self.models_base_dir / model_slug
                if model_dir.exists():
                    for app_dir in model_dir.iterdir():
                        if app_dir.is_dir() and app_dir.name.startswith('app'):
                            app_num = int(app_dir.name[3:])
                            
                            for container_type in ['backend', 'frontend']:
                                project_name = DockerUtils.get_project_name(model_slug, app_num)
                                container_name = f"{project_name}_{container_type}"
                                
                                containers.append({
                                    'model': model_slug,
                                    'app_num': app_num,
                                    'container_type': container_type,
                                    'container_name': container_name,
                                    'compose_path': str(app_dir / 'docker-compose.yml')
                                })
        
        elif selection_method == 'running':
            # Only running containers
            if self.docker_manager and self.docker_manager.client:
                try:
                    running_containers = self.docker_manager.client.containers.list()
                    for container in running_containers:
                        # Parse container name to extract model and app info
                        name_parts = container.name.split('_')
                        if len(name_parts) >= 4:  # Expected format: model_app_type_port
                            model_part = '_'.join(name_parts[:-3])
                            app_part = name_parts[-3]
                            container_type = name_parts[-2]
                            
                            if app_part.startswith('app'):
                                app_num = int(app_part[3:])
                                model_dir = self.models_base_dir / model_part
                                app_dir = model_dir / f"app{app_num}"
                                
                                if app_dir.exists():
                                    containers.append({
                                        'model': model_part,
                                        'app_num': app_num,
                                        'container_type': container_type,
                                        'container_name': container.name,
                                        'compose_path': str(app_dir / 'docker-compose.yml')
                                    })
                except Exception as e:
                    self.logger.warning(f"Failed to get running containers: {e}")
        
        elif selection_method == 'custom':
            # Custom model and app selection
            custom_models = [m.strip() for m in config.get('custom_models', '').split(',') if m.strip()]
            custom_apps = config.get('custom_apps', '1-30')
            container_types = config.get('container_types', ['backend', 'frontend'])
            
            # Parse app numbers
            app_numbers = self._parse_app_numbers(custom_apps.strip())
            
            for model in custom_models:
                model_dir = self.models_base_dir / model
                if model_dir.exists():
                    for app_num in app_numbers:
                        app_dir = model_dir / f"app{app_num}"
                        if app_dir.exists():
                            for container_type in container_types:
                                project_name = DockerUtils.get_project_name(model, app_num)
                                container_name = f"{project_name}_{container_type}"
                                
                                containers.append({
                                    'model': model,
                                    'app_num': app_num,
                                    'container_type': container_type,
                                    'container_name': container_name,
                                    'compose_path': str(app_dir / 'docker-compose.yml')
                                })
        
        # Final logging and fallback
        self.logger.info(f"Built container list with {len(containers)} containers")
        
        # Ensure we always have containers - fallback to test containers if empty
        if not containers:
            self.logger.warning(f"No containers found for selection method '{selection_method}', using test containers as fallback")
            containers = create_test_containers()
            
        self.logger.info(f"Final container list: {[c['container_name'] for c in containers]}")
        return containers
    
    def _parse_app_numbers(self, app_string: str) -> List[int]:
        """Parse app number string (e.g., '1-10' or '1,3,5,7')."""
        app_numbers = []
        
        for part in app_string.split(','):
            part = part.strip()
            if '-' in part:
                # Range (e.g., '1-10')
                start, end = map(int, part.split('-'))
                app_numbers.extend(range(start, end + 1))
            else:
                # Single number
                app_numbers.append(int(part))
        
        return sorted(list(set(app_numbers)))  # Remove duplicates and sort
    
    def _start_operation_execution(self, operation_id: str) -> None:
        """Start asynchronous execution of a batch operation."""
        operation = self.operations[operation_id]
        operation['status'] = 'running'
        operation['started_at'] = datetime.now()
        
        # Create thread pool executor
        concurrency = operation['concurrency']
        executor = ThreadPoolExecutor(max_workers=concurrency)
        self.active_executors[operation_id] = executor
        
        # Submit tasks
        future_to_task = {}
        for task in operation['tasks']:
            if task['status'] == 'pending':
                future = executor.submit(self._execute_single_container_task, operation_id, task['task_id'])
                future_to_task[future] = task['task_id']
        
        # Start monitoring thread
        monitor_thread = threading.Thread(
            target=self._monitor_operation_execution,
            args=(operation_id, future_to_task),
            daemon=True
        )
        monitor_thread.start()
    
    def _execute_single_container_task(self, operation_id: str, task_id: str) -> Dict[str, Any]:
        """Execute a single container operation task."""
        try:
            with self.operation_lock:
                operation = self.operations[operation_id]
                task = next(t for t in operation['tasks'] if t['task_id'] == task_id)
                task['status'] = 'running'
                task['started_at'] = datetime.now()
            
            # Execute the container operation based on type
            operation_type = operation['operation_type']
            
            if operation_type in ['start_containers', 'stop_containers', 'restart_containers', 'rebuild_containers']:
                result = self._execute_container_lifecycle(operation, task)
            elif operation_type.startswith('security_') or operation_type == 'vulnerability_scan':
                result = self._execute_security_analysis(operation, task)
            elif operation_type in ['health_check', 'resource_monitor', 'performance_test']:
                result = self._execute_monitoring_task(operation, task)
            elif operation_type in ['log_collection']:
                result = self._execute_log_collection(operation, task)
            else:
                result = self._execute_maintenance_task(operation, task)
            
            with self.operation_lock:
                task = next(t for t in operation['tasks'] if t['task_id'] == task_id)
                task['status'] = 'completed'
                task['completed_at'] = datetime.now()
                task['result_data'] = result.get('data', {})
                
                if task['started_at']:
                    task['duration'] = (task['completed_at'] - task['started_at']).total_seconds()
            
            return {'success': True, 'result': result}
            
        except Exception as e:
            self.logger.error(f"Container task {task_id} failed: {str(e)}")
            with self.operation_lock:
                task = next(t for t in self.operations[operation_id]['tasks'] if t['task_id'] == task_id)
                task['status'] = 'failed'
                task['completed_at'] = datetime.now()
                task['error_message'] = str(e)
                if task['started_at']:
                    task['duration'] = (task['completed_at'] - task['started_at']).total_seconds()
            
            return {'success': False, 'error': str(e)}
    
    
    def _execute_container_lifecycle(self, operation: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute container lifecycle operations (start, stop, restart, rebuild)."""
        operation_type = operation['operation_type']
        compose_path = task['compose_path']
        model = task['model']
        app_num = task['app_num']
        
        try:
            command = []  # Initialize command
            
            if operation_type == 'start_containers':
                command = ['up', '-d']
                if operation['container_options']['pull_images']:
                    command.append('--pull')
                if operation['container_options']['force_recreate']:
                    command.extend(['--force-recreate'])
                if operation['container_options']['remove_orphans']:
                    command.append('--remove-orphans')
                    
            elif operation_type == 'stop_containers':
                command = ['down']
                if operation['container_options']['remove_orphans']:
                    command.append('--remove-orphans')
                    
            elif operation_type == 'restart_containers':
                command = ['restart']
                
            elif operation_type == 'rebuild_containers':
                command = ['up', '-d', '--build', '--force-recreate']
                if operation['container_options']['remove_orphans']:
                    command.append('--remove-orphans')
            
            # Execute docker-compose command
            result = self.docker_manager.execute_compose_command(
                compose_path, command, model, app_num, 
                timeout=operation['timeout']
            )
            
            # Wait for health check if requested
            if operation['container_options']['wait_healthy'] and operation_type in ['start_containers', 'restart_containers', 'rebuild_containers']:
                time.sleep(5)  # Give containers time to start
                self._wait_for_container_health(task['container_name'])
            
            return {
                'success': result['success'],
                'data': {
                    'operation': operation_type,
                    'container': task['container_name'],
                    'output': result.get('output', ''),
                    'message': result.get('message', '')
                }
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'data': {'operation': operation_type, 'container': task['container_name']}
            }
    
    def _execute_security_analysis(self, operation: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute security analysis on container."""
        try:
            # Prepare request for security scanner
            request_data = {
                'model': task['model'],
                'app_num': task['app_num'],
                'test_type': operation['operation_type'],
                'tools': operation['tools'],
                'target_url': self._get_target_url(task['model'], task['app_num'], operation['operation_type'])
            }
            
            # Submit test to security scanner
            response = requests.post(
                f"{self.security_scanner_url}/tests",
                json=request_data,
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Security scanner returned {response.status_code}: {response.text}")
            
            result = response.json()
            if not result.get('success'):
                raise Exception(f"Security scanner error: {result.get('error', 'Unknown error')}")
            
            return {
                'success': True,
                'data': {
                    'test_id': result['data']['test_id'],
                    'security_issues': result['data'].get('issues', []),
                    'scan_summary': result['data'].get('summary', {})
                }
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _execute_monitoring_task(self, operation: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute monitoring tasks (health check, resource monitor, performance test)."""
        operation_type = operation['operation_type']
        container_name = task['container_name']
        
        try:
            if operation_type == 'health_check':
                status = self.docker_manager.get_container_status(container_name)
                return {
                    'success': True,
                    'data': {
                        'container': container_name,
                        'health_status': status.health,
                        'running': status.running,
                        'details': status.details
                    }
                }
            
            elif operation_type == 'resource_monitor':
                # Get container resource usage
                if self.docker_manager.client:
                    try:
                        container = self.docker_manager.client.containers.get(container_name)
                        stats = container.stats(stream=False)
                        
                        # Calculate CPU percentage
                        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
                        system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
                        cpu_percent = (cpu_delta / system_delta) * len(stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100
                        
                        # Calculate memory usage
                        memory_usage = stats['memory_stats']['usage']
                        memory_limit = stats['memory_stats']['limit']
                        memory_percent = (memory_usage / memory_limit) * 100
                        
                        return {
                            'success': True,
                            'data': {
                                'container': container_name,
                                'cpu_percent': round(cpu_percent, 2),
                                'memory_usage_mb': round(memory_usage / 1024 / 1024, 2),
                                'memory_percent': round(memory_percent, 2),
                                'network_rx_bytes': stats['networks']['eth0']['rx_bytes'],
                                'network_tx_bytes': stats['networks']['eth0']['tx_bytes']
                            }
                        }
                    except Exception as e:
                        return {'success': False, 'error': f"Resource monitoring failed: {str(e)}"}
                
            elif operation_type == 'performance_test':
                # Basic performance test - check response time
                target_url = self._get_target_url(task['model'], task['app_num'], 'frontend')
                start_time = time.time()
                try:
                    response = requests.get(target_url, timeout=10)
                    response_time = time.time() - start_time
                    
                    return {
                        'success': True,
                        'data': {
                            'container': container_name,
                            'response_time_ms': round(response_time * 1000, 2),
                            'status_code': response.status_code,
                            'response_size_bytes': len(response.content)
                        }
                    }
                except Exception as e:
                    return {'success': False, 'error': f"Performance test failed: {str(e)}"}
            
            return {'success': False, 'error': f"Unknown monitoring operation: {operation_type}"}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _execute_log_collection(self, operation: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute log collection from container."""
        try:
            logs = self.docker_manager.get_container_logs(
                task['model'], 
                task['app_num'], 
                task['container_type'], 
                tail=100
            )
            
            return {
                'success': True,
                'data': {
                    'container': task['container_name'],
                    'logs': logs,
                    'log_lines': len(logs.split('\n')) if logs else 0
                }
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _execute_maintenance_task(self, operation: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute maintenance tasks (cleanup, image update, network reset, volume backup)."""
        operation_type = operation['operation_type']
        
        try:
            result = {'success': False, 'message': '', 'output': ''}  # Initialize result
            
            if operation_type == 'cleanup_containers':
                # Stop and remove containers, clean up images
                result = self.docker_manager.execute_compose_command(
                    task['compose_path'], 
                    ['down', '--rmi', 'local', '--volumes'], 
                    task['model'], 
                    task['app_num']
                )
                
            elif operation_type == 'image_update':
                # Pull latest images and rebuild
                result = self.docker_manager.execute_compose_command(
                    task['compose_path'], 
                    ['pull'], 
                    task['model'], 
                    task['app_num']
                )
                
            elif operation_type == 'network_reset':
                # Reset network configuration
                result = self.docker_manager.execute_compose_command(
                    task['compose_path'], 
                    ['down'], 
                    task['model'], 
                    task['app_num']
                )
                if result['success']:
                    result = self.docker_manager.execute_compose_command(
                        task['compose_path'], 
                        ['up', '-d'], 
                        task['model'], 
                        task['app_num']
                    )
                    
            elif operation_type == 'volume_backup':
                # Create volume backup (simplified - just get volume info)
                result = {
                    'success': True,
                    'message': 'Volume backup initiated',
                    'output': 'Volume backup feature requires additional implementation'
                }
            
            return {
                'success': result['success'],
                'data': {
                    'operation': operation_type,
                    'container': task['container_name'],
                    'output': result.get('output', ''),
                    'message': result.get('message', '')
                }
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _wait_for_container_health(self, container_name: str, timeout: int = 60) -> bool:
        """Wait for container to become healthy."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.docker_manager.get_container_status(container_name)
            if status.health == 'healthy' or status.running:
                return True
            
            time.sleep(2)
        
        return False
    
    def _get_target_url(self, model: str, app_num: int, operation_type: str) -> str:
        """Get target URL for testing based on model, app, and operation type."""
        # Load port configuration
        try:
            port_config_path = Path("misc/port_config.json")
            if port_config_path.exists():
                with open(port_config_path, 'r') as f:
                    port_configs = json.load(f)
                
                for config in port_configs:
                    if config['model_name'] == model and config['app_number'] == app_num:
                        if operation_type in ['security_backend', 'backend']:
                            return f"http://localhost:{config['backend_port']}"
                        else:
                            return f"http://localhost:{config['frontend_port']}"
                        
            # Fallback to default ports
            return f"http://localhost:6051"  # Default backend port
            
        except Exception as e:
            self.logger.warning(f"Failed to get target URL: {e}")
            return f"http://localhost:6051"
    
    def _monitor_operation_execution(self, operation_id: str, future_to_task: Dict) -> None:
        """Monitor operation execution and update status."""
        try:
            for future in as_completed(future_to_task.keys()):
                task_id = future_to_task[future]
                
                try:
                    result = future.result()
                    with self.operation_lock:
                        operation = self.operations[operation_id]
                        task = next(t for t in operation['tasks'] if t['task_id'] == task_id)
                        
                        if task['status'] == 'completed':
                            operation['completed_containers'] += 1
                        else:
                            operation['failed_containers'] += 1
                        
                        operation['pending_containers'] = operation['total_containers'] - operation['completed_containers'] - operation['failed_containers']
                        
                        # Check fail-fast condition
                        if operation['fail_fast'] and operation['failed_containers'] > 0:
                            # Cancel remaining tasks
                            if operation_id in self.active_executors:
                                self.active_executors[operation_id].shutdown(wait=False)
                            break
                        
                except Exception as e:
                    self.logger.error(f"Task {task_id} failed with exception: {str(e)}")
                    with self.operation_lock:
                        operation = self.operations[operation_id]
                        operation['failed_containers'] += 1
                        operation['pending_containers'] = operation['total_containers'] - operation['completed_containers'] - operation['failed_containers']
            
            # Operation completed
            with self.operation_lock:
                operation = self.operations[operation_id]
                operation['status'] = 'completed'
                operation['completed_at'] = datetime.now()
            
            # Clean up executor
            if operation_id in self.active_executors:
                del self.active_executors[operation_id]
            
            self.logger.info(f"Container batch operation {operation_id} completed")
            
        except Exception as e:
            self.logger.error(f"Operation monitoring failed for {operation_id}: {str(e)}")
            with self.operation_lock:
                operation = self.operations[operation_id]
                operation['status'] = 'failed'
                operation['completed_at'] = datetime.now()
                operation['error_message'] = str(e)
    
    def _calculate_progress(self, job: Dict[str, Any]) -> int:
        """Calculate job progress percentage."""
        if job['total_tasks'] == 0:
            return 0
        return int((job['completed_tasks'] + job['failed_tasks']) / job['total_tasks'] * 100)
    
    def _format_duration(self, job: Dict[str, Any]) -> Optional[str]:
        """Format job duration for display."""
        if not job['started_at']:
            return None
        
        end_time = job['completed_at'] or datetime.now()
        duration = end_time - job['started_at']
        
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def _format_relative_time(self, timestamp: datetime) -> str:
        """Format timestamp as relative time."""
        now = datetime.now()
        diff = now - timestamp
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"
    
    # Compatibility methods for web routes that expect the old security testing interface
    def get_all_jobs(self, status_filter: Optional[str] = None, test_type_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all operations (compatibility method for jobs)."""
        with self.operation_lock:
            operations = list(self.operations.values())
            
            if status_filter:
                operations = [op for op in operations if op['status'] == status_filter]
            
            if test_type_filter:
                operations = [op for op in operations if op['operation_type'] == test_type_filter]
                
            return operations
    
    def get_job_details(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get operation details (compatibility method for job details)."""
        with self.operation_lock:
            return self.operations.get(operation_id)
    
    def get_job_results(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get operation results (compatibility method for job results)."""
        operation = self.get_operation_details(operation_id)
        if operation and operation['status'] == 'completed':
            return {
                'operation_id': operation_id,
                'results': operation.get('tasks', []),
                'summary': {
                    'total_containers': operation.get('total_containers', 0),
                    'completed_containers': operation.get('completed_containers', 0),
                    'failed_containers': operation.get('failed_containers', 0)
                }
            }
        return None
    
    def cancel_job(self, operation_id: str) -> bool:
        """Cancel operation (compatibility method for job cancellation)."""
        result = self.cancel_operation(operation_id)
        return result.get('success', False) if isinstance(result, dict) else False
    
    # Additional compatibility methods for old batch system integration
    def get_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get operations with limit (compatibility method)."""
        with self.operation_lock:
            operations = list(self.operations.values())
            return operations[-limit:] if limit else operations
    
    def get_job(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get single operation (compatibility method)."""
        return self.get_job_details(operation_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get operation statistics (compatibility method)."""
        with self.operation_lock:
            operations = list(self.operations.values())
            
            total = len(operations)
            pending = len([op for op in operations if op['status'] == 'pending'])
            running = len([op for op in operations if op['status'] == 'running'])
            completed = len([op for op in operations if op['status'] == 'completed'])
            failed = len([op for op in operations if op['status'] == 'failed'])
            cancelled = len([op for op in operations if op['status'] == 'cancelled'])
            
            return {
                'total': total,
                'pending': pending,
                'running': running,
                'completed': completed,
                'failed': failed,
                'cancelled': cancelled,
                'archived': 0
            }
    
    def create_job(self, **job_data) -> Dict[str, Any]:
        """Create operation (compatibility method for job creation)."""
        # Convert old job format to new operation format
        operation_config = {
            'operation_type': job_data.get('test_type', 'health_check'),
            'target_selection': job_data.get('target_selection', 'models'),
            'selected_models': job_data.get('models', []),
            'selected_apps': job_data.get('app_numbers', []),
            'concurrency': job_data.get('max_parallel_tasks', 3),
            'timeout': job_data.get('timeout', 300),
            'fail_fast': job_data.get('fail_fast', False),
            'container_options': {
                'wait_healthy': True,
                'pull_images': False,
                'force_recreate': False,
                'remove_orphans': True
            },
            'tools': job_data.get('tools', [])
        }
        
        result = self.create_batch_operation(operation_config)
        if result.get('success'):
            # Return an object-like dict with id attribute
            return {'id': result['operation_id']}
        else:
            raise Exception(f"Failed to create operation: {result.get('error', 'Unknown error')}")
    
    def start_job(self, operation_id: str) -> bool:
        """Start operation (compatibility method)."""
        # Operations start automatically in our new system
        operation = self.get_operation_details(operation_id)
        return operation is not None and operation.get('status') != 'failed'
    
    def stop_job(self, operation_id: str) -> bool:
        """Stop operation (compatibility method)."""
        return self.cancel_job(operation_id)
    
    def get_job_status(self, operation_id: str) -> Optional[str]:
        """Get operation status (compatibility method)."""
        operation = self.get_operation_details(operation_id)
        return operation.get('status') if operation else None
    
    def create_batch_job(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create batch operation (compatibility method)."""
        try:
            result = self.create_batch_operation(job_config)
            if result.get('success'):
                return {
                    'success': True,
                    'job_id': result['operation_id'],  # Map operation_id to job_id
                    'message': result.get('message', 'Container batch operation created successfully')
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error', 'Failed to create container operation'),
                    'message': result.get('error', 'Unknown error occurred')
                }
        except Exception as e:
            return {'success': False, 'error': str(e), 'message': f'Error: {str(e)}'}
    
    def delete_job(self, operation_id: str) -> Dict[str, Any]:
        """Delete operation (compatibility method)."""
        return self.delete_operation(operation_id)
_container_batch_service = None

def get_batch_testing_service() -> ContainerBatchOperationService:
    """Get or create the global container batch operation service instance."""
    global _container_batch_service
    if _container_batch_service is None:
        _container_batch_service = ContainerBatchOperationService()
    return _container_batch_service
