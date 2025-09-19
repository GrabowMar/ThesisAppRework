#!/usr/bin/env python3
"""
Performance Tester Service - Simplified and Robust Load Testing
==============================================================

A complete rewrite focused on actually working rather than complex error handling.
Based on proven patterns from performance_analysis.py and Docker best practices.
"""

import os
import json
import asyncio
import aiohttp
import subprocess
import statistics
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime
from typing import Dict, List, Any, Optional
from analyzer.shared.service_base import BaseWSService

class PerformanceTester(BaseWSService):
    """Simplified, robust performance testing service."""
    
    def __init__(self):
        super().__init__(service_name="performance-tester", default_port=2003, version="2.0.0")
        self.test_output_dir = Path("/tmp/performance_tests")
        self.test_output_dir.mkdir(exist_ok=True)
    
    def _detect_available_tools(self) -> List[str]:
        """Detect which performance testing tools are available."""
        tools = []
        
        # Check for curl (basic)
        try:
            result = subprocess.run(['curl', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('curl')
                self.log.debug("curl available")
        except Exception as e:
            self.log.debug(f"curl not available: {e}")
        
        # Check for ab (Apache Bench)
        try:
            result = subprocess.run(['ab', '-V'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('ab')
                self.log.debug("Apache Bench available")
        except Exception as e:
            self.log.debug(f"Apache Bench not available: {e}")
        
        # Check for Artillery
        try:
            result = subprocess.run(['artillery', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                tools.append('artillery')
                self.log.debug("Artillery available")
        except Exception as e:
            self.log.debug(f"Artillery not available: {e}")
        
        # Check for locust python package
        try:
            import importlib.util
            if importlib.util.find_spec('locust') is not None:
                tools.append('locust')
                self.log.debug("Locust available")
            else:
                self.log.debug("Locust not available")
        except Exception as e:
            self.log.debug(f"Locust check failed: {e}")
        
        # Always available - built-in aiohttp
        tools.append('aiohttp')
        self.log.debug("aiohttp available (built-in)")
        
        return tools
    
    async def simple_response_check(self, url: str, num_requests: int = 3) -> Dict[str, Any]:
        """Simple response check - just verify the app is reachable."""
        try:
            self.log.info(f"Quick response check for {url}")
            await self.send_progress('checking', f'Checking connectivity: {url}', url=url)

            # Try multiple hostnames for Docker networking
            test_urls = [url]
            parsed = urlparse(url)
            if parsed.hostname in ['localhost', '127.0.0.1']:
                # Add host.docker.internal alternative
                alt_url = url.replace(parsed.netloc, f"host.docker.internal:{parsed.port}")
                test_urls.append(alt_url)
            
            successful_url = None
            last_error = None
            
            for test_url in test_urls:
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                        async with session.get(test_url) as response:
                            if response.status < 500:  # Accept anything that's not a server error
                                successful_url = test_url
                                self.log.info(f"✓ Successfully connected to {test_url} (status: {response.status})")
                                break
                except Exception as e:
                    last_error = str(e)
                    self.log.debug(f"Failed to connect to {test_url}: {e}")
                    continue
            
            if successful_url:
                await self.send_progress('connected', f'Connected to: {successful_url}')
                return {
                    'status': 'success',
                    'original_url': url,
                    'working_url': successful_url,
                    'message': f'Successfully connected to {successful_url}'
                }
            else:
                await self.send_progress('failed', f'Could not connect to {url}')
                return {
                    'status': 'error',
                    'original_url': url,
                    'error': f'Could not connect to any variant of {url}. Last error: {last_error}'
                }

        except Exception as e:
            await self.send_progress('error', f'Response check error: {e}')
            return {'status': 'error', 'original_url': url, 'error': str(e)}
    
    async def run_apache_bench_test(self, url: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run Apache Bench load test."""
        if 'ab' not in self.available_tools:
            return {'status': 'unavailable', 'tool': 'apache_bench', 'error': 'Apache Bench not available'}
        
        try:
            # Get configuration
            ab_config = config.get('apache_bench', {}) if config else {}
            requests = ab_config.get('requests', 100)
            concurrency = ab_config.get('concurrency', 10)
            
            self.log.info(f"Running Apache Bench: {requests} requests, {concurrency} concurrent on {url}")
            await self.send_progress('ab_start', f'Apache Bench starting: {url}', 
                                   requests=requests, concurrency=concurrency)
            
            # Build command
            cmd = ['ab', '-n', str(requests), '-c', str(concurrency), '-g', 'ab_results.tsv', url]
            
            # Run test
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=str(self.test_output_dir))
            
            if result.returncode == 0:
                # Parse results from stdout
                output = result.stdout
                
                # Extract key metrics using simple parsing
                metrics = self._parse_ab_output(output)
                metrics.update({
                    'status': 'success',
                    'tool': 'apache_bench',
                    'url': url,
                    'configuration': {'requests': requests, 'concurrency': concurrency}
                })
                
                await self.send_progress('ab_complete', f'Apache Bench completed: {url}', 
                                       rps=metrics.get('requests_per_second', 0))
                return metrics
            else:
                error_msg = result.stderr or "Apache Bench failed"
                self.log.error(f"Apache Bench failed: {error_msg}")
                return {'status': 'error', 'tool': 'apache_bench', 'error': error_msg, 'url': url}
                
        except subprocess.TimeoutExpired:
            return {'status': 'timeout', 'tool': 'apache_bench', 'error': 'Test timed out', 'url': url}
        except Exception as e:
            return {'status': 'error', 'tool': 'apache_bench', 'error': str(e), 'url': url}
    
    def _parse_ab_output(self, output: str) -> Dict[str, Any]:
        """Parse Apache Bench output for key metrics."""
        metrics = {}
        
        for line in output.split('\n'):
            line = line.strip()
            
            if 'Requests per second:' in line:
                try:
                    rps = float(line.split(':')[1].split('[')[0].strip())
                    metrics['requests_per_second'] = rps
                except (ValueError, IndexError):
                    pass
            
            elif 'Time per request:' in line and '[ms]' in line:
                try:
                    time_per_req = float(line.split(':')[1].split('[')[0].strip())
                    metrics['avg_response_time'] = time_per_req
                except (ValueError, IndexError):
                    pass
            
            elif 'Complete requests:' in line:
                try:
                    completed = int(line.split(':')[1].strip())
                    metrics['completed_requests'] = completed
                except (ValueError, IndexError):
                    pass
            
            elif 'Failed requests:' in line:
                try:
                    failed = int(line.split(':')[1].strip())
                    metrics['failed_requests'] = failed
                except (ValueError, IndexError):
                    pass
        
        return metrics
    
    async def run_locust_test(self, url: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run Locust load test using CLI."""
        if 'locust' not in self.available_tools:
            return {'status': 'unavailable', 'tool': 'locust', 'error': 'Locust not available'}
        
        try:
            # Get configuration
            locust_config = config.get('locust', {}) if config else {}
            users = locust_config.get('users', 50)
            spawn_rate = locust_config.get('spawn_rate', 2)
            run_time = locust_config.get('run_time', '30s')
            
            self.log.info(f"Running Locust: {users} users, {spawn_rate}/s spawn rate, {run_time} duration on {url}")
            await self.send_progress('locust_start', f'Locust starting: {url}', 
                                   users=users, spawn_rate=spawn_rate, duration=run_time)
            
            # Create simple locustfile
            locustfile_path = self.test_output_dir / "simple_locustfile.py"
            locustfile_content = f'''
from locust import HttpUser, task, between

class SimpleUser(HttpUser):
    host = "{url}"
    wait_time = between(1, 2)
    
    @task
    def load_test(self):
        self.client.get("/")
'''
            locustfile_path.write_text(locustfile_content)
            
            # Build command
            csv_prefix = str(self.test_output_dir / "locust_stats")
            cmd = [
                'locust',
                '-f', str(locustfile_path),
                '--headless',
                '--users', str(users),
                '--spawn-rate', str(spawn_rate),
                '--run-time', str(run_time),
                '--host', url,
                '--csv', csv_prefix
            ]
            
            # Run test
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=str(self.test_output_dir))
            
            if result.returncode == 0:
                # Parse CSV results
                metrics = self._parse_locust_csv(csv_prefix)
                metrics.update({
                    'status': 'success',
                    'tool': 'locust',
                    'url': url,
                    'configuration': {'users': users, 'spawn_rate': spawn_rate, 'run_time': run_time}
                })
                
                await self.send_progress('locust_complete', f'Locust completed: {url}', 
                                       rps=metrics.get('requests_per_second', 0))
                return metrics
            else:
                error_msg = result.stderr or "Locust failed"
                self.log.error(f"Locust failed: {error_msg}")
                return {'status': 'error', 'tool': 'locust', 'error': error_msg, 'url': url}
                
        except subprocess.TimeoutExpired:
            return {'status': 'timeout', 'tool': 'locust', 'error': 'Test timed out', 'url': url}
        except Exception as e:
            return {'status': 'error', 'tool': 'locust', 'error': str(e), 'url': url}
    
    def _parse_locust_csv(self, csv_prefix: str) -> Dict[str, Any]:
        """Parse Locust CSV results for key metrics."""
        metrics = {}
        
        try:
            stats_file = f"{csv_prefix}_stats.csv"
            if os.path.exists(stats_file):
                with open(stats_file, 'r') as f:
                    lines = f.readlines()
                    if len(lines) > 1:  # Skip header
                        # Parse aggregated stats (last line is usually "Aggregated")
                        for line in reversed(lines[1:]):
                            parts = line.strip().split(',')
                            if len(parts) >= 10 and ('Aggregated' in parts[1] or parts[1] == '"Aggregated"'):
                                # Extract metrics from aggregated row
                                metrics['requests'] = int(parts[2]) if parts[2].isdigit() else 0
                                metrics['failures'] = int(parts[3]) if parts[3].isdigit() else 0
                                metrics['avg_response_time'] = float(parts[4]) if parts[4].replace('.','').isdigit() else 0
                                metrics['min_response_time'] = float(parts[5]) if parts[5].replace('.','').isdigit() else 0
                                metrics['max_response_time'] = float(parts[6]) if parts[6].replace('.','').isdigit() else 0
                                metrics['requests_per_second'] = float(parts[9]) if parts[9].replace('.','').isdigit() else 0
                                break
        except Exception as e:
            self.log.warning(f"Could not parse Locust CSV: {e}")
        
        return metrics
    
    async def run_aiohttp_load_test(self, url: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run simple concurrent load test using aiohttp."""
        try:
            # Get configuration
            aiohttp_config = config.get('aiohttp', {}) if config else {}
            requests = aiohttp_config.get('requests', 50)
            concurrency = aiohttp_config.get('concurrency', 5)
            
            self.log.info(f"Running aiohttp load test: {requests} requests, {concurrency} concurrent on {url}")
            await self.send_progress('aiohttp_start', f'aiohttp load test starting: {url}', 
                                   requests=requests, concurrency=concurrency)
            
            semaphore = asyncio.Semaphore(concurrency)
            response_times = []
            status_codes = []
            errors = []
            
            async def single_request(session: aiohttp.ClientSession):
                async with semaphore:
                    try:
                        start_time = datetime.now()
                        async with session.get(url) as response:
                            await response.read()
                            end_time = datetime.now()
                            response_time = (end_time - start_time).total_seconds() * 1000
                            response_times.append(response_time)
                            status_codes.append(response.status)
                            return True
                    except Exception as e:
                        errors.append(str(e))
                        return False
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                tasks = [single_request(session) for _ in range(requests)]
                results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Calculate metrics
            successful_requests = sum(1 for r in results if r is True)
            failed_requests = len(results) - successful_requests
            
            metrics = {
                'status': 'success',
                'tool': 'aiohttp',
                'url': url,
                'requests': requests,
                'successful_requests': successful_requests,
                'failed_requests': failed_requests,
                'success_rate': (successful_requests / requests) * 100 if requests > 0 else 0,
                'configuration': {'requests': requests, 'concurrency': concurrency}
            }
            
            if response_times:
                metrics.update({
                    'avg_response_time': statistics.mean(response_times),
                    'min_response_time': min(response_times),
                    'max_response_time': max(response_times),
                    'median_response_time': statistics.median(response_times)
                })
            
            await self.send_progress('aiohttp_complete', f'aiohttp load test completed: {url}', 
                                   success_rate=metrics['success_rate'])
            return metrics
            
        except Exception as e:
            return {'status': 'error', 'tool': 'aiohttp', 'error': str(e), 'url': url}
    
    async def test_application_performance(self, model_slug: str, app_number: int, target_urls: List[str], 
                                         config: Optional[Dict[str, Any]] = None, 
                                         selected_tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Perform comprehensive performance testing on application."""
        try:
            self.log.info(f"Performance testing {model_slug} app {app_number} with tools: {selected_tools}")
            
            results = {
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_time': datetime.now().isoformat(),
                'tools_used': [],
                'target_urls': target_urls,
                'results': {}
            }
            
            # Determine which tools to run
            available_tools = {'locust', 'ab', 'aiohttp'} & set(self.available_tools)
            if selected_tools:
                # Map tool names
                tool_mapping = {
                    'locust-performance': 'locust',
                    'ab-load-test': 'ab', 
                    'aiohttp-load': 'aiohttp'
                }
                requested_tools = {tool_mapping.get(tool, tool) for tool in selected_tools}
                tools_to_run = available_tools & requested_tools
            else:
                tools_to_run = available_tools
            
            self.log.info(f"Running tools: {list(tools_to_run)}")
            
            # Test each URL
            for url in target_urls:
                self.log.info(f"Testing URL: {url}")
                url_results = {}
                
                # 1. Quick connectivity check
                connectivity = await self.simple_response_check(url)
                url_results['connectivity'] = connectivity
                
                if connectivity['status'] != 'success':
                    self.log.warning(f"Connectivity failed for {url}, skipping load tests")
                    results['results'][url] = url_results
                    continue
                
                # Use the working URL from connectivity check
                working_url = connectivity['working_url']
                self.log.info(f"Using working URL: {working_url}")
                
                # 2. Run selected tools
                if 'aiohttp' in tools_to_run:
                    self.log.info(f"Running aiohttp test on {working_url}")
                    aiohttp_result = await self.run_aiohttp_load_test(working_url, config)
                    url_results['aiohttp'] = aiohttp_result
                    if aiohttp_result.get('status') == 'success':
                        results['tools_used'].append('aiohttp')
                
                if 'ab' in tools_to_run:
                    self.log.info(f"Running Apache Bench test on {working_url}")
                    ab_result = await self.run_apache_bench_test(working_url, config)
                    url_results['apache_bench'] = ab_result
                    if ab_result.get('status') == 'success':
                        results['tools_used'].append('ab')
                
                if 'locust' in tools_to_run:
                    self.log.info(f"Running Locust test on {working_url}")
                    locust_result = await self.run_locust_test(working_url, config)
                    url_results['locust'] = locust_result
                    if locust_result.get('status') == 'success':
                        results['tools_used'].append('locust')
                
                results['results'][url] = url_results
            
            # Remove duplicates from tools_used
            results['tools_used'] = list(set(results['tools_used']))
            
            self.log.info(f"Performance testing completed. Tools used: {results['tools_used']}")
            return results
            
        except Exception as e:
            self.log.error(f"Performance testing failed: {e}")
            return {
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_time': datetime.now().isoformat(),
                'status': 'error',
                'error': str(e),
                'tools_used': []
            }
    
    async def handle_message(self, websocket, message_data):
        """Handle incoming WebSocket messages."""
        try:
            message_type = message_data.get('type')
            
            if message_type == 'performance_analysis':
                model_slug = message_data.get('model_slug', 'unknown')
                app_number = message_data.get('app_number', 0)
                target_urls = message_data.get('target_urls', [])
                config = message_data.get('config', {})
                selected_tools = message_data.get('selected_tools', [])
                
                self.log.info(f"Received performance analysis request for {model_slug} app {app_number}")
                result = await self.test_application_performance(
                    model_slug, app_number, target_urls, config, selected_tools
                )
                
                await websocket.send(json.dumps({
                    'type': 'analysis_result',
                    'id': message_data.get('id'),
                    'result': result
                }))
            
            elif message_type == 'health_check':
                await websocket.send(json.dumps({
                    'type': 'health_response',
                    'status': 'healthy',
                    'service': 'performance-tester',
                    'version': '2.0.0',
                    'available_tools': self.available_tools,
                    'timestamp': datetime.now().isoformat()
                }))
            
            else:
                await websocket.send(json.dumps({
                    'type': 'error',
                    'error': f'Unknown message type: {message_type}'
                }))
                
        except Exception as e:
            self.log.error(f"Error handling message: {e}")
            await websocket.send(json.dumps({
                'type': 'error',
                'error': str(e)
            }))

async def main():
    service = PerformanceTester()
    await service.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass