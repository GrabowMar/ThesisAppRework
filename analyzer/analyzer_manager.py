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
- Security scanning (Bandit, Safety, OWASP ZAP)
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
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import websockets
from websockets.exceptions import ConnectionClosed

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
    timeout: int = 300

    def __post_init__(self):
        if self.options is None:
            self.options = {}
        if not self.source_path:
            self.source_path = f"../misc/models/{self.model_slug}/app{self.app_number}"


@dataclass
class ServiceInfo:
    """Information about an analyzer service."""
    name: str
    port: int
    container_name: str
    websocket_url: str
    health_status: str = "unknown"
    last_check: Optional[datetime] = None


class AnalyzerManager:
    """Main manager for analyzer infrastructure."""
    
    def __init__(self):
        self.services = {
            'static-analyzer': ServiceInfo(
                name='static-analyzer',
                port=2001,
                container_name='analyzer-static-analyzer-1',
                websocket_url='ws://localhost:2001'
            ),
            'dynamic-analyzer': ServiceInfo(
                name='dynamic-analyzer', 
                port=2002,
                container_name='analyzer-dynamic-analyzer-1',
                websocket_url='ws://localhost:2002'
            ),
            'performance-tester': ServiceInfo(
                name='performance-tester',
                port=2003, 
                container_name='analyzer-performance-tester-1',
                websocket_url='ws://localhost:2003'
            ),
            'ai-analyzer': ServiceInfo(
                name='ai-analyzer',
                port=2004,
                container_name='analyzer-ai-analyzer-1', 
                websocket_url='ws://localhost:2004'
            )
        }
        
        self.compose_file = Path("docker-compose.yml")
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)

        # Determine docker compose command (prefer modern 'docker compose')
        self._compose_cmd = self._resolve_compose_cmd()
        # Discover available model slugs under ../misc/models for convenience
        try:
            self._models_root = (Path(__file__).parent / ".." / "misc" / "models").resolve()
        except Exception:
            self._models_root = None

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
    
    def run_command(self, command: List[str], capture_output: bool = False, 
                   timeout: int = 60) -> Tuple[int, str, str]:
        """Run a shell command and return result."""
        try:
            logger.info(f"Running: {' '.join(command)}")
            result = subprocess.run(
                command,
                capture_output=capture_output,
                text=True,
                cwd=Path(__file__).parent,
                timeout=timeout
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
        logger.info("🚀 Starting analyzer infrastructure...")
        
        if not self.compose_file.exists():
            logger.error(f"❌ Docker Compose file not found: {self.compose_file}")
            return False
        
        # Build and start services
        returncode, stdout, stderr = self.run_command(
            self._compose_cmd + ['up', '--build', '-d'], timeout=300
        )  # 5 minutes for building
        
        if returncode == 0:
            logger.info("✅ All services started successfully!")
            
            # Wait for services to initialize
            logger.info("⏳ Waiting for services to initialize...")
            time.sleep(15)
            
            # Check service health (but don't wait for it)
            asyncio.create_task(self.check_all_services_health())
            return True
        else:
            logger.error(f"❌ Failed to start services: {stderr}")
            return False
    
    def stop_services(self) -> bool:
        """Stop all analyzer services."""
        logger.info("🛑 Stopping analyzer infrastructure...")
        
        returncode, stdout, stderr = self.run_command(self._compose_cmd + ['down'])
        
        if returncode == 0:
            logger.info("✅ All services stopped successfully!")
            return True
        else:
            logger.error(f"❌ Failed to stop services: {stderr}")
            return False
    
    def restart_services(self) -> bool:
        """Restart all analyzer services."""
        logger.info("🔄 Restarting analyzer infrastructure...")
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
        logger.info("📊 Checking service status...")
        
        print("\n" + "=" * 80)
        print("🐳 ANALYZER INFRASTRUCTURE STATUS")
        print("=" * 80)
        
        # Docker container status
        containers = self.get_container_status()
        
        print("\n🔧 CONTAINER STATUS:")
        print("-" * 50)
        
        for service_name, service_info in self.services.items():
            container_data = containers.get(service_name, {})
            state = container_data.get('state', 'Not found')
            status = container_data.get('status', 'Unknown')
            
            state_icon = "✅" if state == "running" else "❌"
            print(f"{state_icon} {service_name:20} | {state:10} | {status}")
        
        # Port accessibility
        print("\n📡 PORT ACCESSIBILITY:")
        print("-" * 50)
        
        for service_name, service_info in self.services.items():
            accessible = self.check_port_accessibility('localhost', service_info.port)
            access_icon = "✅" if accessible else "❌"
            print(f"{access_icon} {service_name:20} | localhost:{service_info.port:5} | {'ACCESSIBLE' if accessible else 'NOT ACCESSIBLE'}")
        
        # WebSocket health check
        print("\n💓 SERVICE HEALTH:")
        print("-" * 50)
        
        # Check if we can run health checks (avoid event loop conflicts)
        try:
            # Try to get the current event loop
            try:
                asyncio.get_running_loop()
                # If we're already in an event loop, skip detailed health check
                logger.info("Already in event loop, skipping detailed health check")
                for service_name in self.services.keys():
                    print(f"ℹ️  {service_name:20} | RUNNING    | Use 'health' command for details")
            except RuntimeError:
                # No running loop, safe to create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    health_results = loop.run_until_complete(self.check_all_services_health())
                    
                    for service_name, health_data in health_results.items():
                        if health_data.get('status') == 'healthy':
                            health_icon = "✅"
                            health_status = "HEALTHY"
                            extra_info = f"v{health_data.get('version', 'unknown')}"
                        else:
                            health_icon = "❌" 
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
                logger.error(f"❌ Unknown service: {service}")
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
            logger.error(f"❌ Failed to get logs: {stderr}")
    
    # =================================================================
    # WEBSOCKET COMMUNICATION
    # =================================================================
    
    async def send_websocket_message(self, service_name: str, message: Dict[str, Any], 
                                   timeout: int = 30) -> Dict[str, Any]:
        """Send a message to a service via WebSocket."""
        if service_name not in self.services:
            return {'status': 'error', 'error': f'Unknown service: {service_name}'}
        
        service_info = self.services[service_name]
        
        try:
            async with websockets.connect(
                service_info.websocket_url, 
                open_timeout=10,
                close_timeout=5,
                ping_interval=20,
                ping_timeout=10
            ) as websocket:
                
                # Send message
                await websocket.send(json.dumps(message))
                
                # Wait for response
                response = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                return json.loads(response)
                
        except asyncio.TimeoutError:
            return {'status': 'timeout', 'error': f'Request to {service_name} timed out'}
        except ConnectionClosed:
            return {'status': 'error', 'error': f'Connection to {service_name} closed'}
        except Exception as e:
            return {'status': 'error', 'error': f'WebSocket error: {str(e)}'}
    
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
    
    # =================================================================
    # ANALYSIS OPERATIONS
    # =================================================================
    
    async def run_security_analysis(self, model_slug: str, app_number: int, 
                                  tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run security analysis on an application."""
        if tools is None:
            tools = ['bandit', 'safety']
        
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
        
        return await self.send_websocket_message('static-analyzer', message, timeout=180)

    async def run_dynamic_analysis(self, model_slug: str, app_number: int,
                                  target_urls: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run dynamic (ZAP-like) analysis against running app endpoints."""
        logger.info(f"🕷️  Running dynamic (ZAP) analysis on {model_slug} app {app_number}")

        message = {
            "type": "dynamic_analyze",
            "model_slug": model_slug,
            "app_number": app_number,
            "target_urls": target_urls or [],
            "timestamp": datetime.now().isoformat(),
            "id": str(uuid.uuid4())
        }

        return await self.send_websocket_message('dynamic-analyzer', message, timeout=180)
    
    async def run_performance_test(self, model_slug: str, app_number: int,
                                 target_url: Optional[str] = None, users: int = 10, 
                                 duration: int = 60) -> Dict[str, Any]:
        """Run performance test on an application."""
        logger.info(f"⚡ Running performance test on {model_slug} app {app_number}")
        
        if not target_url:
            target_url = f"http://localhost:300{app_number}"  # Default port pattern
        
        message = {
            "type": "performance_test",
            "model_slug": model_slug,
            "app_number": app_number,
            "target_url": target_url,
            "users": users,
            "duration": duration,
            "timestamp": datetime.now().isoformat(),
            "id": str(uuid.uuid4())
        }
        
        return await self.send_websocket_message('performance-tester', message, timeout=duration + 60)
    
    async def run_ai_analysis(self, model_slug: str, app_number: int,
                            ai_model: Optional[str] = None) -> Dict[str, Any]:
        """Run AI-powered code analysis."""
        logger.info(f"🤖 Running AI analysis on {model_slug} app {app_number}")
        
        request = AnalysisRequest(
            model_slug=model_slug,
            app_number=app_number,
            analysis_type='ai_analysis'
        )
        
        message = {
            "type": "ai_analysis",
            "model_slug": model_slug,
            "app_number": app_number,
            "source_path": request.source_path,
            "ai_model": ai_model or "anthropic/claude-3-haiku",
            "timestamp": datetime.now().isoformat(),
            "id": str(uuid.uuid4())
        }
        
        return await self.send_websocket_message('ai-analyzer', message, timeout=180)
    
    async def run_static_analysis(self, model_slug: str, app_number: int,
                                tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run static code analysis."""
        if tools is None:
            # Broaden to common static tools across Python/JS/CSS
            tools = ['pylint', 'flake8', 'mypy', 'eslint', 'stylelint']
        
        logger.info(f"🔍 Running static analysis on {model_slug} app {app_number}")
        
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
        
        return await self.send_websocket_message('static-analyzer', message, timeout=180)
    
    async def run_comprehensive_analysis(self, model_slug: str, app_number: int) -> Dict[str, Dict[str, Any]]:
        """Run comprehensive analysis (security, static, performance, dynamic) without AI."""
        logger.info(f"🎯 Running comprehensive analysis on {model_slug} app {app_number}")

        # Prepare tasks (no AI per request)
        analysis_tasks = [
            ('security', self.run_security_analysis(model_slug, app_number)),
            ('static', self.run_static_analysis(model_slug, app_number)),
            ('performance', self.run_performance_test(model_slug, app_number)),
            ('dynamic', self.run_dynamic_analysis(model_slug, app_number)),
        ]
        
        results = {}

        for analysis_type, task in analysis_tasks:
            try:
                logger.info(f"Starting {analysis_type} analysis...")
                result = await task
                results[analysis_type] = result

                status = result.get('status', 'unknown')
                if status == 'success':
                    logger.info(f"✅ {analysis_type.title()} analysis completed")
                else:
                    logger.warning(f"⚠️ {analysis_type.title()} analysis failed: {result.get('error', 'Unknown error')}")

            except Exception as e:
                logger.error(f"❌ {analysis_type.title()} analysis error: {e}")
                results[analysis_type] = {'status': 'error', 'error': str(e)}

        # Save comprehensive results
        await self.save_analysis_results(model_slug, app_number, 'comprehensive', results)

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
                logger.error(f"❌ Failed to analyze {app_key}: {e}")
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
        
        logger.info(f"✅ Batch analysis completed: {successful}/{len(models_and_apps)} successful")
        return batch_results
    
    # =================================================================
    # RESULTS MANAGEMENT
    # =================================================================
    
    async def save_analysis_results(self, model_slug: str, app_number: int, 
                                  analysis_type: str, results: Dict[str, Any]) -> Path:
        """Save analysis results to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{model_slug}_app{app_number}_{analysis_type}_{timestamp}.json"
        filepath = self.results_dir / filename
        
        # Add metadata
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
            
            logger.info(f"💾 Results saved to: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"❌ Failed to save results: {e}")
            raise
    
    async def save_batch_results(self, batch_results: Dict[str, Any]) -> Path:
        """Save batch analysis results to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"batch_analysis_{batch_results['batch_id'][:8]}_{timestamp}.json"
        filepath = self.results_dir / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(batch_results, f, indent=2, default=str)
            
            logger.info(f"💾 Batch results saved to: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"❌ Failed to save batch results: {e}")
            raise
    
    def list_results(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent analysis results."""
        result_files = []
        
        for filepath in self.results_dir.glob("*.json"):
            try:
                stat = filepath.stat()
                result_files.append({
                    'filename': filepath.name,
                    'path': str(filepath),
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime),
                    'is_batch': 'batch_analysis' in filepath.name
                })
            except Exception as e:
                logger.warning(f"Could not read file info for {filepath}: {e}")
        
        # Sort by modification time (newest first)
        result_files.sort(key=lambda x: x['modified'], reverse=True)
        
        return result_files[:limit]
    
    # =================================================================
    # TESTING AND VALIDATION
    # =================================================================
    
    async def test_all_services(self) -> Dict[str, Any]:
        """Run comprehensive tests on all services."""
        logger.info("🧪 Running comprehensive analyzer service tests")
        
        test_results = {
            'test_start_time': datetime.now().isoformat(),
            'services_tested': len(self.services),
            'health_checks': {},
            'ping_tests': {},
            'functional_tests': {},
            'summary': {}
        }
        
        # Health check tests
        logger.info("Running health check tests...")
        health_results = await self.check_all_services_health()
        test_results['health_checks'] = health_results
        
        # Ping tests
        logger.info("Running ping tests...")
        ping_tasks = [
            self._test_service_ping(service_name)
            for service_name in self.services.keys()
        ]
        ping_results = await asyncio.gather(*ping_tasks, return_exceptions=True)
        
        for i, (service_name, result) in enumerate(zip(self.services.keys(), ping_results)):
            if isinstance(result, Exception):
                test_results['ping_tests'][service_name] = {
                    'status': 'error',
                    'error': str(result)
                }
            else:
                test_results['ping_tests'][service_name] = result
        
        # Functional tests (on working services only)
        logger.info("Running functional tests...")
        
        # Test a sample application if services are healthy
        healthy_services = [
            name for name, result in health_results.items()
            if result.get('status') == 'healthy'
        ]
        
        # Choose a real model slug that exists on disk to avoid path-not-found
        sample_model = self._pick_available_model_slug(
            preferred=[
                'anthropic_claude-3.7-sonnet',
                'openai_gpt_4',
                'openai_gpt-4.1',
            ]
        ) or 'anthropic_claude-3.7-sonnet'

        if 'static-analyzer' in healthy_services:
            try:
                security_result = await self.run_security_analysis(sample_model, 1)
                test_results['functional_tests']['static-analyzer'] = security_result
            except Exception as e:
                test_results['functional_tests']['static-analyzer'] = {
                    'status': 'error', 'error': str(e)
                }
        
        if 'ai-analyzer' in healthy_services:
            try:
                ai_result = await self.run_ai_analysis(sample_model, 1)
                test_results['functional_tests']['ai-analyzer'] = ai_result
            except Exception as e:
                test_results['functional_tests']['ai-analyzer'] = {
                    'status': 'error', 'error': str(e)
                }
        
        # Calculate summary
        healthy_count = sum(1 for result in health_results.values() 
                          if result.get('status') == 'healthy')
        ping_success_count = sum(1 for result in test_results['ping_tests'].values() 
                               if result.get('status') == 'success')
        functional_success_count = sum(1 for result in test_results['functional_tests'].values() 
                                     if result.get('status') == 'success')
        
        test_results['summary'] = {
            'healthy_services': healthy_count,
            'total_services': len(self.services),
            'successful_pings': ping_success_count,
            'functional_tests_passed': functional_success_count,
            'overall_health': 'good' if healthy_count >= 4 else 'partial' if healthy_count >= 2 else 'poor',
            'test_completion_time': datetime.now().isoformat()
        }
        
        return test_results

    def _pick_available_model_slug(self, preferred: Optional[List[str]] = None) -> Optional[str]:
        """Pick a model slug that exists under misc/models and has an app1 folder.

        Preference order:
        - Any slug in the preferred list that exists and contains app1
        - Otherwise, the first directory with an app1 child
        Returns None if none are found.
        """
        try:
            root = self._models_root
            if not root or not root.exists():
                return None

            def has_app1(p: Path) -> bool:
                return (p / 'app1').exists()

            # Try preferred list first
            if preferred:
                for slug in preferred:
                    candidate = root / slug
                    if candidate.exists() and candidate.is_dir() and has_app1(candidate):
                        return slug

            # Fallback: scan all directories
            for entry in sorted(root.iterdir()):
                try:
                    if entry.is_dir() and has_app1(entry):
                        return entry.name
                except Exception:
                    continue
        except Exception:
            return None
        return None
    
    async def _test_service_ping(self, service_name: str) -> Dict[str, Any]:
        """Test ping/pong for a service."""
        ping_message = {
            "type": "ping",
            "timestamp": datetime.now().isoformat(),
            "id": str(uuid.uuid4())
        }
        
        start_time = time.time()
        result = await self.send_websocket_message(service_name, ping_message, timeout=10)
        end_time = time.time()
        
        if result.get('type') == 'pong' or 'pong' in str(result):
            return {
                'status': 'success',
                'service': service_name,
                'response_time': end_time - start_time,
                'response': result
            }
        else:
            return {
                'status': 'error',
                'service': service_name,
                'error': result.get('error', 'No pong response')
            }


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
                                                                     Types: comprehensive, security, static, performance, dynamic (zap), ai
  
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
                    print("❌ Usage: python analyzer_manager.py analyze <model> <app_number> [type]")
                return
            
            model_slug = sys.argv[2]
            app_number = int(sys.argv[3])
            analysis_type = sys.argv[4] if len(sys.argv) > 4 else 'comprehensive'
            
            if not JSON_MODE:
                print(f"🎯 Analyzing {model_slug} app {app_number} ({analysis_type})")
            
            if analysis_type == 'comprehensive':
                results = await manager.run_comprehensive_analysis(model_slug, app_number)
            elif analysis_type == 'security':
                results = await manager.run_security_analysis(model_slug, app_number)
                # Persist results for single analysis types
                try:
                    await manager.save_analysis_results(model_slug, app_number, 'security', results)
                except Exception as e:
                    logger.warning(f"Could not save security analysis results: {e}")
            elif analysis_type == 'performance':
                results = await manager.run_performance_test(model_slug, app_number)
                try:
                    await manager.save_analysis_results(model_slug, app_number, 'performance', results)
                except Exception as e:
                    logger.warning(f"Could not save performance test results: {e}")
            elif analysis_type in ['dynamic', 'zap']:
                results = await manager.run_dynamic_analysis(model_slug, app_number)
                try:
                    await manager.save_analysis_results(model_slug, app_number, 'dynamic', results)
                except Exception as e:
                    logger.warning(f"Could not save dynamic analysis results: {e}")
            elif analysis_type == 'ai':
                results = await manager.run_ai_analysis(model_slug, app_number)
                try:
                    await manager.save_analysis_results(model_slug, app_number, 'ai', results)
                except Exception as e:
                    logger.warning(f"Could not save AI analysis results: {e}")
            elif analysis_type == 'static':
                results = await manager.run_static_analysis(model_slug, app_number)
                try:
                    await manager.save_analysis_results(model_slug, app_number, 'static', results)
                except Exception as e:
                    logger.warning(f"Could not save static analysis results: {e}")
            else:
                if JSON_MODE:
                    print(json.dumps({"status": "error", "error": f"unknown_type:{analysis_type}"}))
                else:
                    print(f"❌ Unknown analysis type: {analysis_type}")
                return
            
            if JSON_MODE:
                # Emit raw JSON for machine consumption
                try:
                    print(json.dumps(results, ensure_ascii=False))
                except Exception as e:
                    print(json.dumps({"status": "error", "error": f"json_dump_failed:{str(e)}"}))
            else:
                print("✅ Analysis completed. Results summary:")
                if isinstance(results, dict):
                    # For comprehensive results (dict of dicts), print each section
                    if any(isinstance(v, dict) for v in results.values()):
                        for key, result in results.items():
                            if isinstance(result, dict):
                                status = result.get('status', 'unknown')
                                print(f"  {key}: {status}")
                    else:
                        status = results.get('status', 'unknown')
                        print(f"  type: {analysis_type}, status: {status}")
        
        elif command == 'batch':
            if len(sys.argv) < 3:
                print("❌ Usage: python analyzer_manager.py batch <models_file.json>")
                return
            
            models_file = Path(sys.argv[2])
            if not models_file.exists():
                print(f"❌ File not found: {models_file}")
                return
            
            try:
                with open(models_file, 'r') as f:
                    models_and_apps = json.load(f)
                
                results = await manager.run_batch_analysis(models_and_apps)
                print("✅ Batch analysis completed:")
                print(f"  Success rate: {results['summary']['success_rate']:.1f}%")
                print(f"  Duration: {results['summary']['total_duration']:.1f}s")
                
            except Exception as e:
                print(f"❌ Failed to run batch analysis: {e}")
        
        elif command == 'batch-models':
            if len(sys.argv) < 3:
                print("❌ Usage: python analyzer_manager.py batch-models <model1,model2,...>")
                return
            
            model_names = sys.argv[2].split(',')
            models_and_apps = [(model.strip(), 1) for model in model_names]
            
            print(f"📦 Running batch analysis on {len(models_and_apps)} models (app 1)")
            
            results = await manager.run_batch_analysis(models_and_apps)
            print("✅ Batch analysis completed:")
            print(f"  Success rate: {results['summary']['success_rate']:.1f}%")
            print(f"  Duration: {results['summary']['total_duration']:.1f}s")
        
        elif command == 'test':
            print("🧪 Running comprehensive service tests...")
            test_results = await manager.test_all_services()
            
            summary = test_results['summary']
            print("\n📊 TEST RESULTS:")
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
                print("❌ Usage: python analyzer_manager.py ping <service_name>")
                return
            
            service_name = sys.argv[2]
            if service_name not in manager.services:
                print(f"❌ Unknown service: {service_name}")
                print(f"Available services: {', '.join(manager.services.keys())}")
                return
            
            result = await manager._test_service_ping(service_name)
            if result['status'] == 'success':
                print(f"✅ {service_name} responded in {result['response_time']:.3f}s")
            else:
                print(f"❌ {service_name} ping failed: {result.get('error')}")
        
        elif command == 'results':
            if len(sys.argv) > 2:
                # Show specific result file
                filename = sys.argv[2]
                filepath = manager.results_dir / filename
                
                if not filepath.exists():
                    print(f"❌ Result file not found: {filepath}")
                    return
                
                try:
                    with open(filepath, 'r') as f:
                        results = json.load(f)
                    
                    print(f"📄 Results from {filename}:")
                    print(json.dumps(results, indent=2, default=str))
                    
                except Exception as e:
                    print(f"❌ Failed to read results: {e}")
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
            print(f"❌ Unknown command: {command}")
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
