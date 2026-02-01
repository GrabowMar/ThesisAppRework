#!/usr/bin/env python3
"""
Curl Scanner Tool
================
Lightweight HTTP endpoint validation using curl-like requests.
Ported from ai-analyzer.
"""

import aiohttp
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class CurlScanner:
    """HTTP endpoint validator using requirements template."""
    
    def __init__(self):
        self.log = logger

    async def _test_single_endpoint(
        self, 
        base_url: str, 
        method: str, 
        path: str, 
        auth_token: Optional[str] = None,
        expected_status: Any = None
    ) -> Dict[str, Any]:
        """Test a single HTTP endpoint and return result."""
        if expected_status is None:
            expected_status = [200, 201]
        
        # Normalize expected_status to list
        if isinstance(expected_status, int):
            expected_status = [expected_status]
        
        try:
            headers = {'Content-Type': 'application/json'}
            if auth_token:
                headers['Authorization'] = f'Bearer {auth_token}'
            
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method, 
                    f"{base_url}{path}", 
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    actual_status = response.status
                    passed = actual_status in expected_status or (200 <= actual_status < 300)
                    
                    return {
                        'endpoint': path,
                        'method': method,
                        'expected_status': expected_status,
                        'actual_status': actual_status,
                        'passed': passed
                    }
        except Exception as e:
            error_msg = str(e)
            if 'Cannot connect to host' in error_msg or 'Connection refused' in error_msg:
                error_msg = f"App not running at {base_url}"
            
            return {
                'endpoint': path,
                'method': method,
                'expected_status': expected_status,
                'actual_status': None,
                'passed': False,
                'error': error_msg
            }

    async def _get_auth_token(self, base_url: str) -> Optional[str]:
        """Attempt to get auth token from common endpoints."""
        endpoints = [
            ('/api/auth/login', {'username': 'admin', 'password': 'admin_password'}),
            ('/api/login', {'username': 'admin', 'password': 'admin_password'}),
            ('/auth/login', {'username': 'admin', 'password': 'admin_password'}),
            ('/login', {'username': 'admin', 'password': 'admin_password'})
        ]
        
        async with aiohttp.ClientSession() as session:
            for path, payload in endpoints:
                try:
                    async with session.post(
                        f"{base_url}{path}",
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data.get('token') or data.get('access_token')
                except Exception:
                    continue
        return None

    async def scan(self, model_slug: str, app_number: int, target_urls: List[str], config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run endpoint validation.
        
        Args:
            model_slug: Model identifier
            app_number: App identifier
            target_urls: List of target URLs (expected [backend_url, frontend_url])
            config: Configuration dictionary containing template_slug
        """
        try:
            self.log.info(f"Starting curl endpoint testing for {model_slug} app {app_number}")
            self.log.info(f"Target URLs received: {target_urls}")
            
            # Determine base URL (backend) - look for _backend in URL, or exclude frontend
            base_url = None
            for url in target_urls:
                # Primary check: look for _backend container name
                if '_backend' in url:
                    base_url = url
                    break
            
            # Fallback: find URL that's not the frontend (doesn't end with :80 or have _frontend)
            if not base_url:
                for url in target_urls:
                    if '_frontend' not in url and not url.endswith(':80'):
                        base_url = url
                        break
            
            # Last resort: use first URL
            if not base_url and target_urls:
                base_url = target_urls[0]
            
            if not base_url:
                return {
                    'status': 'error',
                    'error': 'No target URL provided',
                    'tool_name': 'curl-endpoint-tester'
                }
            
            # Locate requirements template
            # In dynamic-analyzer, we need to access the shared templates
            # Assuming volume mount or copy exists. 
            # If not, we might need to rely on config passed from manager.
            
            template_slug = config.get('template_slug', 'crud_todo_list') if config else 'crud_todo_list'
            
            # Try to find template file
            # Path logic depends on container structure. 
            # Assuming /app/misc/requirements_templates or similar
            template_path = Path("/app/misc/requirements_templates") / f"{template_slug}.json"
            
            if not template_path.exists():
                # Fallback path (dev environment)
                template_path = Path("/app/src/data/requirements_templates") / f"{template_slug}.json"
            
            if not template_path.exists():
                return {
                    'status': 'error',
                    'error': f'Requirements template not found: {template_slug}',
                    'tool_name': 'curl-endpoint-tester'
                }
            
            with open(template_path, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
            
            # Extract endpoints logic (same as in ai-analyzer)
            api_endpoints = template_data.get('api_endpoints', [])
            control_endpoints = [
                {
                    'path': ep.get('path', '/'),
                    'method': ep.get('method', 'GET'),
                    'expected_status': 200,
                    'description': ep.get('description', 'API endpoint'),
                    'request_body': ep.get('request'),
                    'requires_auth': False
                }
                for ep in api_endpoints
            ]
            
            admin_api_endpoints = template_data.get('admin_api_endpoints', [])
            admin_endpoints = [
                {
                    'path': ep.get('path', '/').replace(':id', '1'),
                    'method': ep.get('method', 'GET'),
                    'expected_status': 200,
                    'description': ep.get('description', 'Admin API endpoint'),
                    'request_body': ep.get('request'),
                    'requires_auth': True
                }
                for ep in admin_api_endpoints
            ]
            
            if not control_endpoints and not admin_endpoints:
                control_endpoints = template_data.get('control', {}).get('endpoints', [])
                admin_endpoints = template_data.get('admin', {}).get('endpoints', [])
            
            all_endpoints = control_endpoints + admin_endpoints
            
            if not all_endpoints:
                return {
                    'status': 'success',
                    'message': 'No endpoints defined in template',
                    'endpoint_tests': {'passed': 0, 'failed': 0, 'total': 0, 'results': []},
                    'tool_name': 'curl-endpoint-tester'
                }
            
            self.log.info(f"Using base URL for endpoint testing: {base_url}")
            
            # Try to get auth token for admin endpoints
            auth_token = None
            if admin_endpoints:
                auth_token = await self._get_auth_token(base_url)
            
            # Test all endpoints
            endpoint_results = []
            passed = 0
            failed = 0
            
            for ep in all_endpoints:
                requires_auth = ep.get('requires_auth', False)
                token = auth_token if requires_auth else None
                
                result = await self._test_single_endpoint(
                    base_url,
                    ep.get('method', 'GET'),
                    ep.get('path', '/'),
                    token,
                    ep.get('expected_status', 200)
                )
                
                if result['passed']:
                    passed += 1
                else:
                    failed += 1
                endpoint_results.append(result)
            
            return {
                'status': 'success',
                'tool_name': 'curl-endpoint-tester',
                'endpoint_tests': {
                    'passed': passed,
                    'failed': failed,
                    'total': len(all_endpoints),
                    'results': endpoint_results
                },
                'duration_seconds': 0.0, # Filled by caller
                'total_issues': failed
            }
            
        except Exception as e:
            self.log.error(f"Curl scanner failed: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'tool_name': 'curl-endpoint-tester'
            }
