#!/usr/bin/env python3
"""
AI Analyzer Service - Requirement-Based Code Analysis & Code Quality Metrics
============================================================================

AI-powered analyzer that:
1. Requirements Scanner - Checks backend, frontend, and admin requirements compliance
2. Code Quality Analyzer - Measures actual code quality metrics (error handling, 
   type annotations, documentation, anti-patterns, code organization)

Uses OpenRouter APIs. Based on methodology from:
- SoftwareQuality4AI (SQ4AI) framework concepts
- ISO/IEC 25010 software quality characteristics
"""

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Add the analyzer directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from analyzer.shared.service_base import BaseWSService
from analyzer.shared.path_utils import resolve_app_source_path
import aiohttp


# =============================================================================
# Code Quality Metrics Definitions (inspired by SQ4AI framework)
# =============================================================================

CODE_QUALITY_METRICS = {
    "error_handling": {
        "name": "Error Handling Coverage",
        "description": "Proper try-catch blocks, error boundaries, and graceful error handling",
        "weight": 1.5,  # Higher weight for critical metric
        "checks": [
            "try-catch blocks for async operations",
            "Error boundaries in React components",
            "API error response handling",
            "User-friendly error messages",
            "Logging of errors for debugging"
        ]
    },
    "type_safety": {
        "name": "Type Safety & Annotations",
        "description": "Use of TypeScript/type hints, proper typing throughout codebase",
        "weight": 1.2,
        "checks": [
            "Type annotations on function parameters",
            "Return type annotations",
            "Interface/type definitions for data structures",
            "Avoidance of 'any' type",
            "Proper null/undefined handling"
        ]
    },
    "code_organization": {
        "name": "Code Organization & Structure",
        "description": "Clean file structure, separation of concerns, modular design",
        "weight": 1.0,
        "checks": [
            "Logical file/folder structure",
            "Separation of concerns (MVC/components)",
            "Single responsibility principle",
            "Reasonable file sizes",
            "Clear naming conventions"
        ]
    },
    "documentation": {
        "name": "Documentation & Comments",
        "description": "Code comments, docstrings, README, inline documentation",
        "weight": 0.8,
        "checks": [
            "Function/method docstrings",
            "Complex logic explanations",
            "API endpoint documentation",
            "README with setup instructions",
            "Inline comments for non-obvious code"
        ]
    },
    "anti_patterns": {
        "name": "Anti-Pattern Detection",
        "description": "Detection of code smells, bad practices, and security issues",
        "weight": 1.5,  # Higher weight for critical metric
        "checks": [
            "No console.log in production code",
            "No hardcoded secrets/credentials",
            "No TODO/FIXME in critical paths",
            "No unused imports/variables",
            "No deeply nested callbacks (callback hell)"
        ]
    },
    "security_practices": {
        "name": "Security Best Practices",
        "description": "Input validation, sanitization, secure coding patterns",
        "weight": 1.3,
        "checks": [
            "Input validation on user data",
            "SQL injection prevention (parameterized queries)",
            "XSS prevention (output encoding)",
            "CORS configuration",
            "Authentication/authorization checks"
        ]
    },
    "performance_patterns": {
        "name": "Performance Patterns",
        "description": "Efficient algorithms, caching, lazy loading, optimization",
        "weight": 1.0,
        "checks": [
            "Efficient database queries (no N+1)",
            "Proper use of async/await",
            "Memoization where appropriate",
            "Lazy loading of components/data",
            "Avoiding unnecessary re-renders"
        ]
    },
    "testing_readiness": {
        "name": "Testing Readiness",
        "description": "Code structured for testability, presence of tests",
        "weight": 0.7,
        "checks": [
            "Dependency injection patterns",
            "Pure functions where possible",
            "Mockable external dependencies",
            "Test files present",
            "Testable component structure"
        ]
    }
}


@dataclass
class RequirementResult:
    """Result of a requirement analysis."""
    met: bool = False
    confidence: str = "LOW"
    explanation: str = ""
    error: Optional[str] = None
    frontend_analysis: Optional[Dict] = None
    backend_analysis: Optional[Dict] = None


@dataclass
class QualityMetricResult:
    """Result of a code quality metric analysis."""
    metric_id: str = ""
    metric_name: str = ""
    passed: bool = False
    score: float = 0.0  # 0-100 scale
    confidence: str = "LOW"
    findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RequirementCheck:
    """Container for a requirement and its analysis result."""
    requirement: str
    result: RequirementResult = field(default_factory=RequirementResult)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'requirement': self.requirement,
            'result': asdict(self.result)
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RequirementCheck':
        """Create from dictionary."""
        result_data = data.get('result', {})
        result = RequirementResult(**result_data)
        return cls(requirement=data['requirement'], result=result)


class AIAnalyzer(BaseWSService):
    """AI-powered requirement analyzer for web applications."""
    
    def __init__(self):
        super().__init__(service_name="ai-analyzer", default_port=2004, version="1.0.0")
        try:
            
            # API configuration
            self.openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
            
            # Default models - Gemini Flash is cheaper than Claude Haiku
            # Available models: google/gemini-2.5-flash (cheap), anthropic/claude-3.5-haiku, openai/gpt-4o-mini
            self.default_openrouter_model = os.getenv('AI_MODEL', 'google/gemini-2.5-flash')
            
            # Cost optimization settings (defaults are cheap mode)
            # BATCH_MODE: true = batch all requirements in single API call (recommended)
            #             false = individual API call per requirement (legacy, expensive)
            self.batch_mode = os.getenv('AI_BATCH_MODE', 'true').lower() == 'true'
            # Code truncation limit - must be large enough to include ALL LLM-generated files
            # Default 30000 chars handles typical apps (~27KB of code in 7 whitelisted files)
            # Previous default of 4000 was too low and truncated frontend files
            self.code_truncation_limit = int(os.getenv('AI_CODE_TRUNCATION_LIMIT', '30000'))
            # Max tokens for responses - lower = cheaper
            self.max_response_tokens = int(os.getenv('AI_MAX_RESPONSE_TOKENS', '300'))
            # Batch max tokens - larger for batch mode since it contains multiple results
            self.batch_max_response_tokens = int(os.getenv('AI_BATCH_MAX_TOKENS', '1500'))
            # Enable/disable code quality analyzer tool (8 extra API calls when granular)
            self.quality_analyzer_enabled = os.getenv('AI_QUALITY_ANALYZER_ENABLED', 'false').lower() == 'true'
            
            # OPTIMIZED MODE: Only scan LLM-generated files (not scaffolding)
            # This dramatically reduces token usage by ~60-70%
            self.optimized_mode = os.getenv('AI_OPTIMIZED_MODE', 'true').lower() == 'true'
            
            # LLM-generated files whitelist (files that contain app-specific code)
            # Single-file mode: app.py for backend, App.jsx for frontend
            self.llm_generated_files = {
                'backend': [
                    'app.py',              # Complete backend in single file
                ],
                'frontend': [
                    'src/App.jsx',         # Complete frontend in single file
                ]
            }
            
            self.log.info("AI Analyzer initialized (template-based requirements system)")
            self.log.info(f"Using model: {self.default_openrouter_model}, batch_mode={self.batch_mode}, optimized_mode={self.optimized_mode}, code_limit={self.code_truncation_limit}")
            self.log.info("AIAnalyzer initialization complete")
            if not self.openrouter_api_key:
                self.log.warning("OPENROUTER_API_KEY not set - OpenRouter analysis will be unavailable")
                
        except Exception as e:
            self.log.error(f"ERROR during initialization: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _detect_available_tools(self) -> List[str]:
        """Detect available AI analysis tools (template-based only)."""
        tools = [
            "requirements-scanner",      # Unified: Backend + Frontend + Admin requirements + AI code analysis
            "curl-endpoint-tester",      # HTTP endpoint validation with curl tests (no AI, just functional tests)
            "code-quality-analyzer"      # True code quality metrics (error handling, types, anti-patterns, etc.)
        ]
        
        self.log.info(f"Available tools: {tools}")
        return tools
    
    def _resolve_app_path(self, model_slug: str, app_number: int) -> Optional[Path]:
        """Resolve application path for analysis."""
        # Use shared path resolution supporting template-based structures
        path = resolve_app_source_path(model_slug, app_number)
        if path:
            return path
        
        # Fallback to legacy locations if not found in main sources
        legacy_paths = [
            Path('/app/generated/apps') / model_slug / f'app{app_number}',
            Path('/app/misc/models') / model_slug / f'app{app_number}',
        ]
        
        for legacy_path in legacy_paths:
            if legacy_path.exists():
                return legacy_path
        
        return None
    
    async def _read_app_code(self, app_path: Path) -> str:
        """Read all relevant code files from the application."""
        code_content = ""
        
        # Common file extensions to analyze
        extensions = ['.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.vue', '.php', '.java', '.cs']
        
        try:
            for ext in extensions:
                for file_path in app_path.rglob(f'*{ext}'):
                    # Skip common directories
                    if any(part in str(file_path) for part in ['node_modules', '__pycache__', '.git', 'venv']):
                        continue
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            code_content += f"\n\n=== {file_path.relative_to(app_path)} ===\n{content}"
                    except Exception as e:
                        self.log.debug(f"Could not read file {file_path}: {e}")
                        continue
        except Exception as e:
            self.log.error(f"Error reading application code: {e}")
        
        return code_content
    
    async def _analyze_requirement(self, code_content: str, requirement: str, config: Optional[Dict[str, Any]] = None) -> RequirementResult:
        """Analyze a single requirement against the code using AI."""
        result = await self._try_openrouter_analysis(code_content, requirement, config)
        
        if result is None:
            return RequirementResult(
                met=False,
                confidence="LOW",
                explanation="No AI service available for analysis",
                error="OpenRouter unavailable"
            )
        
        return result
    
    async def _try_openrouter_analysis(self, code_content: str, requirement: str, config: Optional[Dict[str, Any]] = None) -> Optional[RequirementResult]:
        """Try analysis using OpenRouter API."""
        try:
            if not self.openrouter_api_key:
                self.log.warning("[API] OpenRouter API key not available")
                return None
            
            prompt = self._build_analysis_prompt(code_content, requirement, None)
            self.log.debug(f"[API-OPENROUTER] Built prompt: {len(prompt)} chars for requirement: {requirement[:100]}...")
            
            async with aiohttp.ClientSession() as session:
                import aiohttp as _aiohttp
                _timeout = _aiohttp.ClientTimeout(total=30)
                headers = {
                    "Authorization": f"Bearer {self.openrouter_api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": self.default_openrouter_model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 500,
                    "temperature": 0.1
                }
                # Log sanitized version for security
                sanitized_key = f"{self.openrouter_api_key[:10]}...{self.openrouter_api_key[-5:]}"
                self.log.info(f"[API-OPENROUTER] Sending request to OpenRouter (model={self.default_openrouter_model}, prompt_len={len(prompt)}, key={sanitized_key})")
                print(f"[ai-analyzer] API call to OpenRouter: model={self.default_openrouter_model}")
                
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=_timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        ai_response = data['choices'][0]['message']['content']
                        self.log.info(f"[API-OPENROUTER] Success - Response length: {len(ai_response)} chars")
                        self.log.debug(f"[API-OPENROUTER] Raw response: {ai_response[:200]}...")
                        print(f"[ai-analyzer] OpenRouter API success: {len(ai_response)} chars")
                        
                        parsed_result = self._parse_ai_response(ai_response)
                        self.log.debug(f"[API-OPENROUTER] Parsed result: met={parsed_result.met}, confidence={parsed_result.confidence}")
                        return parsed_result
                    else:
                        error_text = await response.text()
                        self.log.warning(f"[API-OPENROUTER] API error: {response.status} - {error_text[:200]}")
                        print(f"[ai-analyzer] OpenRouter API error: {response.status}")
                        return None
        except Exception as e:
            self.log.error(f"[API-OPENROUTER] Exception: {e}")
            print(f"[ai-analyzer] OpenRouter exception: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _build_analysis_prompt(self, code_content: str, requirement: str, template_context: Optional[Dict[str, Any]] = None) -> str:
        """Build analysis prompt for AI with optional template context."""
        # Truncate code if too long (use configurable limit for cost control)
        max_code_length = self.code_truncation_limit
        if len(code_content) > max_code_length:
            code_content = code_content[:max_code_length] + "\n[...truncated...]"
        
        # Add template context if provided
        context_section = ""
        if template_context:
            context_section = f"""
APPLICATION CONTEXT:
- Template: {template_context.get('name', 'Unknown')} ({template_context.get('category', 'Unknown')})
- Description: {template_context.get('description', 'N/A')}
- Data Model: {json.dumps(template_context.get('data_model', {}), indent=2) if template_context.get('data_model') else 'N/A'}

"""
        
        return f"""Analyze the following web application code to determine if it meets this specific requirement:

REQUIREMENT: {requirement}
{context_section}
CODE:
{code_content}

Please analyze the code and respond in this exact format:
MET: [YES/NO]
CONFIDENCE: [HIGH/MEDIUM/LOW]
EXPLANATION: [Brief explanation of your analysis]

Focus on whether the functionality described in the requirement is actually implemented in the code."""
    
    def _parse_ai_response(self, response: str) -> RequirementResult:
        """Parse AI response into RequirementResult."""
        result = RequirementResult()
        
        self.log.debug(f"[PARSE] Parsing AI response ({len(response)} chars): {response[:150]}...")
        print(f"[ai-analyzer] Parsing response: {response[:100]}...")
        
        try:
            # Extract structured information from response
            met_match = re.search(r'MET:\s*(YES|NO)', response, re.IGNORECASE)
            if met_match:
                result.met = met_match.group(1).upper() == 'YES'
                self.log.debug(f"[PARSE] Extracted MET={result.met}")
            else:
                self.log.warning(f"[PARSE] Could not find MET field in response")
                print(f"[ai-analyzer] WARNING: No MET field found in response")
            
            confidence_match = re.search(r'CONFIDENCE:\s*(HIGH|MEDIUM|LOW)', response, re.IGNORECASE)
            if confidence_match:
                result.confidence = confidence_match.group(1).upper()
                self.log.debug(f"[PARSE] Extracted CONFIDENCE={result.confidence}")
            else:
                self.log.warning(f"[PARSE] Could not find CONFIDENCE field in response")
                print(f"[ai-analyzer] WARNING: No CONFIDENCE field found in response")
            
            explanation_match = re.search(r'EXPLANATION:\s*(.+)', response, re.IGNORECASE | re.DOTALL)
            if explanation_match:
                result.explanation = explanation_match.group(1).strip()
                self.log.debug(f"[PARSE] Extracted EXPLANATION ({len(result.explanation)} chars)")
            else:
                result.explanation = response  # Fallback to full response
                self.log.warning(f"[PARSE] Could not find EXPLANATION field, using full response")
                print(f"[ai-analyzer] WARNING: No EXPLANATION field, using full response")
            
            self.log.info(f"[PARSE] Parse complete: met={result.met}, confidence={result.confidence}")
            print(f"[ai-analyzer] Parse result: met={result.met}, confidence={result.confidence}")
        
        except Exception as e:
            result.explanation = f"Error parsing AI response: {e}"
            result.error = str(e)
            self.log.error(f"[PARSE] Exception during parsing: {e}")
            print(f"[ai-analyzer] Parse exception: {e}")
            import traceback
            traceback.print_exc()
        
        return result
    
    async def _get_auth_token(self, base_url: str, admin_username: str = "admin", admin_password: str = "admin2025") -> Optional[str]:
        """
        Attempt to get an authentication token by logging in.
        Tries to register first if login fails (for fresh apps).
        
        Returns JWT token or None if auth not available.
        """
        auth_endpoints = [
            "/api/auth/login",
            "/api/login",
            "/auth/login",
            "/login"
        ]
        register_endpoints = [
            "/api/auth/register",
            "/api/register",
            "/auth/register",
            "/register"
        ]
        
        async with aiohttp.ClientSession() as session:
            # Try to register admin user first (in case it's a fresh app)
            for register_path in register_endpoints:
                try:
                    async with session.post(
                        f"{base_url}{register_path}",
                        json={"username": admin_username, "password": admin_password, "email": f"{admin_username}@test.local"},
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        if response.status in [200, 201]:
                            self.log.info(f"Registered test admin user via {register_path}")
                            break
                        elif response.status == 409:  # Already exists
                            self.log.debug(f"Admin user already exists")
                            break
                except Exception:
                    continue
            
            # Try to login and get token
            for login_path in auth_endpoints:
                try:
                    async with session.post(
                        f"{base_url}{login_path}",
                        json={"username": admin_username, "password": admin_password},
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            # Common token field names
                            token = data.get('token') or data.get('access_token') or data.get('jwt')
                            if token:
                                self.log.info(f"Got auth token via {login_path}")
                                return token
                except Exception:
                    continue
        
        return None

    async def _read_app_env(self, app_path: Path) -> Dict[str, str]:
        """Read .env file from application directory."""
        env_vars = {}
        env_file = app_path / ".env"
        
        if env_file.exists():
            try:
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            env_vars[key.strip()] = value.strip()
            except Exception as e:
                self.log.warning(f"Could not read .env file: {e}")
        
        return env_vars

    async def scan_requirements(self, model_slug: str, app_number: int, backend_port: int, frontend_port: int, config: Optional[Dict[str, Any]] = None, analysis_id: Optional[str] = None) -> Dict[str, Any]:
        """
        UNIFIED REQUIREMENTS SCANNER - Analyzes Backend + Frontend + Admin requirements.
        
        Analyzes:
        1. Backend requirements (functional/API) via AI code analysis
        2. Frontend requirements (UI/UX) via AI code analysis  
        3. Admin requirements (admin panel) via AI code analysis
        4. API endpoints testing (public + admin with auth)
        
        Scans backend/ and frontend/ directories for code analysis.
        """
        try:
            # Find application path
            app_path = self._resolve_app_path(model_slug, app_number)
            if not app_path or not app_path.exists():
                return {
                    'status': 'error',
                    'error': f'Application path not found: {model_slug} app {app_number}',
                    'tool_name': 'requirements-scanner'
                }
            
            self.log.info(f"Requirements scanner for {model_slug} app {app_number}")
            await self.send_progress('starting', f"Starting unified requirements scanner for {model_slug} app {app_number}", analysis_id=analysis_id)
            
            # Auto-detect ports from app's .env file
            app_env = await self._read_app_env(app_path)
            if app_env.get('BACKEND_PORT'):
                backend_port = int(app_env['BACKEND_PORT'])
                self.log.info(f"Using BACKEND_PORT from .env: {backend_port}")
            if app_env.get('FRONTEND_PORT'):
                frontend_port = int(app_env['FRONTEND_PORT'])
                self.log.info(f"Using FRONTEND_PORT from .env: {frontend_port}")
            
            # Get admin credentials from .env or use defaults
            admin_username = app_env.get('ADMIN_USERNAME', 'admin')
            admin_password = app_env.get('ADMIN_PASSWORD', 'admin2025')
            
            # Load requirements template with smart detection
            template_slug = config.get('template_slug') if config else None
            
            # If no template_slug provided or it's the default, try to detect it
            if not template_slug or template_slug == 'crud_todo_list':
                detected_template = self._detect_template_from_app(model_slug, app_number)
                if detected_template:
                    template_slug = detected_template
                    self.log.info(f"Using auto-detected template: {template_slug}")
                else:
                    template_slug = template_slug or 'crud_todo_list'  # Keep provided or use default
                    self.log.warning(f"Could not detect template, using: {template_slug}")
            
            requirements_file = self._find_requirements_template(template_slug)
            if not requirements_file:
                return {
                    'status': 'error',
                    'error': f'Requirements template {template_slug} not found',
                    'tool_name': 'requirements-scanner'
                }
            
            with open(requirements_file, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
            
            # Extract ALL requirement types from template
            backend_requirements = template_data.get('backend_requirements', [])
            frontend_requirements = template_data.get('frontend_requirements', [])
            admin_requirements = template_data.get('admin_requirements', [])
            
            # Extract ALL api_endpoints from requirements
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
            
            # Extract ALL admin_api_endpoints (these require authentication)
            admin_api_endpoints = template_data.get('admin_api_endpoints', [])
            admin_endpoints = [
                {
                    'path': ep.get('path', '/').replace(':id', '1'),  # Replace :id with test ID
                    'method': ep.get('method', 'GET'),
                    'expected_status': 200,
                    'description': ep.get('description', 'Admin API endpoint'),
                    'request_body': ep.get('request'),
                    'requires_auth': True
                }
                for ep in admin_api_endpoints
            ]
            
            # Combine all endpoints
            all_endpoints = control_endpoints + admin_endpoints
            
            # If no endpoints defined at all, add a default health check
            if not all_endpoints:
                all_endpoints = [
                    {
                        'path': '/api/health',
                        'method': 'GET',
                        'expected_status': 200,
                        'description': 'Health check endpoint',
                        'requires_auth': False
                    }
                ]
            
            total_requirements = len(backend_requirements) + len(frontend_requirements) + len(admin_requirements)
            
            if total_requirements == 0 and not all_endpoints:
                return {
                    'status': 'warning',
                    'message': 'No requirements or API endpoints found in template',
                    'tool_name': 'requirements-scanner'
                }
            
            await self.send_progress('testing_endpoints', f"Testing {len(all_endpoints)} API endpoints ({len(control_endpoints)} public, {len(admin_endpoints)} admin)", analysis_id=analysis_id)
            
            # Use host.docker.internal when running inside Docker container to reach host services
            # localhost won't work from inside a container
            host = os.getenv('TARGET_HOST', 'host.docker.internal')
            base_url = f"http://{host}:{backend_port}"
            self.log.info(f"Using base URL for endpoint testing: {base_url}")
            
            # Get auth token for admin endpoints
            auth_token = None
            if admin_endpoints:
                await self.send_progress('authenticating', "Getting authentication token for admin endpoints", analysis_id=analysis_id)
                auth_token = await self._get_auth_token(base_url, admin_username, admin_password)
                if auth_token:
                    self.log.info("Successfully obtained auth token for admin endpoint testing")
                else:
                    self.log.warning("Could not obtain auth token - admin endpoints will be tested without auth")
            
            # Test all endpoints
            endpoint_results = []
            for i, endpoint in enumerate(all_endpoints, 1):
                path = endpoint.get('path', '/')
                method = endpoint.get('method', 'GET')
                expected_status = endpoint.get('expected_status', 200)
                description = endpoint.get('description', 'API endpoint')
                requires_auth = endpoint.get('requires_auth', False)
                request_body = endpoint.get('request_body')
                
                await self.send_progress('testing_endpoint', f"Testing endpoint {i}/{len(all_endpoints)}: {method} {path}", analysis_id=analysis_id)
                
                try:
                    headers = {'Content-Type': 'application/json'}
                    if requires_auth and auth_token:
                        headers['Authorization'] = f'Bearer {auth_token}'
                    
                    async with aiohttp.ClientSession() as session:
                        kwargs = {
                            'timeout': aiohttp.ClientTimeout(total=10),
                            'headers': headers
                        }
                        
                        # Add request body for POST/PUT/PATCH methods
                        if method.upper() in ['POST', 'PUT', 'PATCH'] and request_body:
                            kwargs['json'] = request_body
                        
                        async with session.request(method, f"{base_url}{path}", **kwargs) as response:
                            actual_status = response.status
                            passed = (
                                actual_status == expected_status or
                                (200 <= actual_status < 300) or
                                (requires_auth and not auth_token and actual_status in [401, 403])
                            )
                            
                            endpoint_results.append({
                                'endpoint': path,
                                'method': method,
                                'expected_status': expected_status,
                                'actual_status': actual_status,
                                'passed': passed,
                                'description': description,
                                'requires_auth': requires_auth,
                                'auth_used': requires_auth and auth_token is not None,
                                'base_url': base_url
                            })
                except Exception as e:
                    error_msg = str(e)
                    # Make connection errors more user-friendly
                    if 'Cannot connect to host' in error_msg or 'Connection refused' in error_msg:
                        error_msg = f"App not running at {base_url} - start the generated app containers first"
                    
                    endpoint_results.append({
                        'endpoint': path,
                        'method': method,
                        'expected_status': expected_status,
                        'actual_status': None,
                        'passed': False,
                        'error': error_msg,
                        'description': description,
                        'requires_auth': requires_auth,
                        'base_url': base_url
                    })
            
            # Read code for AI analysis - use optimized mode if enabled (default)
            use_optimized_mode = config.get('optimized_mode', self.optimized_mode) if config else self.optimized_mode
            
            if use_optimized_mode:
                # OPTIMIZED: Only scan LLM-generated files (~60-70% token reduction)
                code_content = await self._collect_llm_generated_code(app_path)
                self.log.info(f"Using OPTIMIZED mode: scanning only LLM-generated files ({len(code_content)} chars)")
            else:
                # FULL: Scan all backend/frontend files (legacy, more tokens)
                code_content = await self._read_app_code_focused(app_path, focus_dirs=['backend', 'frontend'])
                self.log.info(f"Using FULL mode: scanning all backend/frontend files ({len(code_content)} chars)")
            
            # Build template context for AI prompts
            template_context = {
                'name': template_data.get('name', template_slug),
                'category': template_data.get('category', 'Unknown'),
                'description': template_data.get('description', ''),
                'data_model': template_data.get('data_model', {}),
                'optimized_mode': use_optimized_mode
            }
            
            # Get AI model from config or use default (Gemini Flash is cheaper)
            gemini_model = config.get('gemini_model', self.default_openrouter_model) if config else self.default_openrouter_model
            
            # Get batch mode from config or use instance default
            use_batch_mode = config.get('batch_mode', self.batch_mode) if config else self.batch_mode
            
            self.log.info(f"Requirements analysis using model={gemini_model}, batch_mode={use_batch_mode}, optimized_mode={use_optimized_mode}")
            
            # ===== BATCH MODE: Single API call per category (CHEAP - default) =====
            if use_batch_mode:
                backend_results = []
                frontend_results = []
                admin_results = []
                
                # Batch analyze backend requirements (1 API call instead of N)
                if backend_requirements:
                    await self.send_progress('analyzing_backend', f"Batch analyzing {len(backend_requirements)} backend requirements", analysis_id=analysis_id)
                    backend_results = await self._analyze_requirements_batch(
                        code_content, backend_requirements, gemini_model, 'backend', template_context
                    )
                
                # Batch analyze frontend requirements (1 API call instead of N)
                if frontend_requirements:
                    await self.send_progress('analyzing_frontend', f"Batch analyzing {len(frontend_requirements)} frontend requirements", analysis_id=analysis_id)
                    frontend_results = await self._analyze_requirements_batch(
                        code_content, frontend_requirements, gemini_model, 'frontend', template_context
                    )
                
                # Batch analyze admin requirements (1 API call instead of N)
                if admin_requirements:
                    await self.send_progress('analyzing_admin', f"Batch analyzing {len(admin_requirements)} admin requirements", analysis_id=analysis_id)
                    admin_results = await self._analyze_requirements_batch(
                        code_content, admin_requirements, gemini_model, 'admin', template_context
                    )
            
            # ===== GRANULAR MODE: Individual API call per requirement (EXPENSIVE - legacy) =====
            else:
                # ===== BACKEND REQUIREMENTS ANALYSIS =====
                backend_results = []
                if backend_requirements:
                    await self.send_progress('analyzing_backend', f"Analyzing {len(backend_requirements)} backend requirements (granular mode)", analysis_id=analysis_id)
                    
                    for i, req in enumerate(backend_requirements, 1):
                        await self.send_progress('checking_requirement', f"Checking backend requirement {i}/{len(backend_requirements)}", analysis_id=analysis_id)
                        
                        result = await self._analyze_requirement_with_gemini(code_content, req, gemini_model, focus='backend', template_context=template_context)
                        backend_results.append({
                            'requirement': req,
                            'met': result.met,
                            'confidence': result.confidence,
                            'explanation': result.explanation,
                            'category': 'backend'
                        })
                
                # ===== FRONTEND REQUIREMENTS ANALYSIS =====
                frontend_results = []
                if frontend_requirements:
                    await self.send_progress('analyzing_frontend', f"Analyzing {len(frontend_requirements)} frontend requirements (granular mode)", analysis_id=analysis_id)
                    
                    for i, req in enumerate(frontend_requirements, 1):
                        await self.send_progress('checking_requirement', f"Checking frontend requirement {i}/{len(frontend_requirements)}", analysis_id=analysis_id)
                        
                        result = await self._analyze_requirement_with_gemini(code_content, req, gemini_model, focus='frontend', template_context=template_context)
                        frontend_results.append({
                            'requirement': req,
                            'met': result.met,
                            'confidence': result.confidence,
                            'explanation': result.explanation,
                            'category': 'frontend'
                        })
                
                # ===== ADMIN REQUIREMENTS ANALYSIS =====
                admin_results = []
                if admin_requirements:
                    await self.send_progress('analyzing_admin', f"Analyzing {len(admin_requirements)} admin requirements (granular mode)", analysis_id=analysis_id)
                    
                    for i, req in enumerate(admin_requirements, 1):
                        await self.send_progress('checking_requirement', f"Checking admin requirement {i}/{len(admin_requirements)}", analysis_id=analysis_id)
                        
                        result = await self._analyze_requirement_with_gemini(code_content, req, gemini_model, focus='admin', template_context=template_context)
                        admin_results.append({
                            'requirement': req,
                            'met': result.met,
                            'confidence': result.confidence,
                            'explanation': result.explanation,
                            'category': 'admin'
                        })
            
            # Calculate compliance breakdown
            met_backend = sum(1 for r in backend_results if r['met'])
            met_frontend = sum(1 for r in frontend_results if r['met'])
            met_admin = sum(1 for r in admin_results if r['met'])
            
            total_endpoints = len(endpoint_results)
            passed_endpoints = sum(1 for e in endpoint_results if e['passed'])
            
            public_endpoints = [e for e in endpoint_results if not e.get('requires_auth', False)]
            admin_endpoint_results = [e for e in endpoint_results if e.get('requires_auth', False)]
            passed_public = sum(1 for e in public_endpoints if e['passed'])
            passed_admin = sum(1 for e in admin_endpoint_results if e['passed'])
            
            # Combine all requirements for overall compliance
            total_reqs = len(backend_requirements) + len(frontend_requirements) + len(admin_requirements)
            total_met = met_backend + met_frontend + met_admin
            
            overall_compliance = (
                (total_met + passed_endpoints) / (total_reqs + total_endpoints) * 100
                if (total_reqs + total_endpoints) > 0 else 0
            )
            
            # Functional compliance (backend + endpoints only, for backwards compatibility)
            functional_total = len(backend_requirements) + total_endpoints
            functional_met = met_backend + passed_endpoints
            functional_compliance = (functional_met / functional_total * 100) if functional_total > 0 else 0
            
            await self.send_progress('completed', 
                f"Requirements scan completed: Backend {met_backend}/{len(backend_requirements)}, "
                f"Frontend {met_frontend}/{len(frontend_requirements)}, "
                f"Admin {met_admin}/{len(admin_requirements)}, "
                f"Endpoints {passed_endpoints}/{total_endpoints}", 
                analysis_id=analysis_id
            )
            
            # Calculate API calls made
            api_calls_made = 3 if use_batch_mode else (len(backend_requirements) + len(frontend_requirements) + len(admin_requirements))
            
            return {
                'status': 'success',
                'tool_name': 'requirements-scanner',
                'metadata': {
                    'model_slug': model_slug,
                    'app_number': app_number,
                    'ai_model_used': gemini_model,
                    'batch_mode': use_batch_mode,
                    'optimized_mode': use_optimized_mode,
                    'code_chars_analyzed': len(code_content),
                    'api_calls_made': api_calls_made,
                    'template_slug': template_slug,
                    'template_name': template_data.get('name', template_slug),
                    'template_category': template_data.get('category', 'Unknown'),
                    'backend_port': backend_port,
                    'frontend_port': frontend_port,
                    'auth_token_obtained': auth_token is not None,
                    'analysis_time': datetime.now().isoformat()
                },
                'results': {
                    # Unified requirements by category
                    'backend_requirements': backend_results,
                    'frontend_requirements': frontend_results,
                    'admin_requirements': admin_results,
                    # Backwards compatibility: combined functional list
                    'functional_requirements': backend_results,  # For UI compatibility
                    # Endpoint test results
                    'control_endpoint_tests': endpoint_results,
                    'summary': {
                        # Per-category breakdown
                        'backend_total': len(backend_requirements),
                        'backend_met': met_backend,
                        'backend_compliance': (met_backend / len(backend_requirements) * 100) if backend_requirements else 0,
                        
                        'frontend_total': len(frontend_requirements),
                        'frontend_met': met_frontend,
                        'frontend_compliance': (met_frontend / len(frontend_requirements) * 100) if frontend_requirements else 0,
                        
                        'admin_total': len(admin_requirements),
                        'admin_met': met_admin,
                        'admin_compliance': (met_admin / len(admin_requirements) * 100) if admin_requirements else 0,
                        
                        # Endpoint breakdown
                        'total_api_endpoints': total_endpoints,
                        'api_endpoints_passed': passed_endpoints,
                        'public_endpoints_total': len(public_endpoints),
                        'public_endpoints_passed': passed_public,
                        'admin_endpoints_total': len(admin_endpoint_results),
                        'admin_endpoints_passed': passed_admin,
                        
                        # Overall metrics
                        'total_requirements': total_reqs,
                        'requirements_met': total_met,
                        'compliance_percentage': overall_compliance,
                        
                        # Backwards compatibility fields
                        'total_functional_requirements': len(backend_requirements),
                        'functional_requirements_met': met_backend,
                        'functional_compliance': functional_compliance
                    }
                },
                'template_info': {
                    'description': template_data.get('description', ''),
                    'data_model': template_data.get('data_model', {}),
                    'api_endpoints_count': len(api_endpoints),
                    'admin_api_endpoints_count': len(admin_api_endpoints)
                }
            }
            
        except Exception as e:
            self.log.error(f"Requirements scanner failed: {e}")
            import traceback
            traceback.print_exc()
            await self.send_progress('failed', f"Requirements scanner failed: {e}", analysis_id=analysis_id)
            return {
                'status': 'error',
                'error': str(e),
                'tool_name': 'requirements-scanner'
            }
    
    # Backwards compatibility alias
    async def check_requirements_with_curl(self, model_slug: str, app_number: int, backend_port: int, frontend_port: int, config: Optional[Dict[str, Any]] = None, analysis_id: Optional[str] = None) -> Dict[str, Any]:
        """Backwards compatibility wrapper for scan_requirements."""
        return await self.scan_requirements(model_slug, app_number, backend_port, frontend_port, config, analysis_id)
    
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

    async def test_endpoints_only(self, model_slug: str, app_number: int, backend_port: int, frontend_port: int, config: Optional[Dict[str, Any]] = None, analysis_id: Optional[str] = None) -> Dict[str, Any]:
        """
        CURL ENDPOINT TESTER - Pure HTTP endpoint validation without AI analysis.
        
        Tests:
        - Backend API endpoints (GET, POST, PUT, DELETE)
        - Frontend routes accessibility
        - Admin endpoints with authentication
        - Response codes and basic validation
        
        This is a lightweight tool that doesn't require AI/LLM - just functional HTTP tests.
        """
        try:
            self.log.info(f"Starting curl endpoint testing for {model_slug} app {app_number}")
            await self.send_progress('starting', f"Starting endpoint tests for {model_slug} app {app_number}", analysis_id=analysis_id)
            
            # Find application and load template
            app_path = self._resolve_app_path(model_slug, app_number)
            if not app_path or not app_path.exists():
                return {
                    'status': 'error',
                    'error': f'Application path not found: {model_slug} app {app_number}',
                    'tool_name': 'curl-endpoint-tester'
                }
            
            # Load template for endpoints with smart detection
            template_slug = config.get('template_slug') if config else None
            if not template_slug or template_slug == 'crud_todo_list':
                detected_template = self._detect_template_from_app(model_slug, app_number)
                if detected_template:
                    template_slug = detected_template
                else:
                    template_slug = template_slug or 'crud_todo_list'
            
            requirements_file = self._find_requirements_template(template_slug)
            if not requirements_file:
                return {
                    'status': 'error',
                    'error': f'Requirements template not found: {template_slug}',
                    'tool_name': 'curl-endpoint-tester'
                }
            
            with open(requirements_file, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
            
            # Extract endpoints from template
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
            
            await self.send_progress('testing_endpoints', f"Testing {len(all_endpoints)} API endpoints ({len(control_endpoints)} public, {len(admin_endpoints)} admin)", analysis_id=analysis_id)
            
            # Build base URL
            base_url = f"http://host.docker.internal:{backend_port}"
            self.log.info(f"Using base URL for endpoint testing: {base_url}")
            
            # Try to get auth token for admin endpoints
            auth_token = None
            if admin_endpoints:
                auth_token = await self._get_auth_token(base_url)
                if auth_token:
                    self.log.info("Successfully obtained auth token for admin endpoint testing")
                else:
                    self.log.warning("Could not obtain auth token - admin endpoints will be tested without auth")
            
            # Test all endpoints
            endpoint_results = []
            passed = 0
            failed = 0
            
            for i, endpoint in enumerate(all_endpoints, 1):
                method = endpoint.get('method', 'GET').upper()
                path = endpoint.get('path', '/')
                is_admin = endpoint in admin_endpoints
                
                await self.send_progress('testing_endpoint', f"Testing endpoint {i}/{len(all_endpoints)}: {method} {path}", analysis_id=analysis_id)
                
                result = await self._test_single_endpoint(
                    base_url, method, path, 
                    auth_token=auth_token if is_admin else None,
                    expected_status=endpoint.get('expected_status', [200, 201])
                )
                
                result['is_admin'] = is_admin
                result['endpoint_name'] = endpoint.get('name', path)
                endpoint_results.append(result)
                
                if result.get('passed'):
                    passed += 1
                else:
                    failed += 1
            
            # Calculate pass rate
            total = len(endpoint_results)
            pass_rate = (passed / total * 100) if total > 0 else 0
            
            await self.send_progress('completed', f"Endpoint testing complete: {passed}/{total} passed ({pass_rate:.1f}%)", analysis_id=analysis_id)
            
            return {
                'status': 'success',
                'tool_name': 'curl-endpoint-tester',
                'endpoint_tests': {
                    'passed': passed,
                    'failed': failed,
                    'total': total,
                    'pass_rate': pass_rate,
                    'results': endpoint_results
                },
                'summary': {
                    'public_endpoints_tested': len(control_endpoints),
                    'admin_endpoints_tested': len(admin_endpoints),
                    'auth_token_obtained': auth_token is not None,
                    'base_url': base_url
                }
            }
            
        except Exception as e:
            self.log.error(f"Curl endpoint testing failed: {e}")
            import traceback
            traceback.print_exc()
            await self.send_progress('failed', f"Endpoint testing failed: {e}", analysis_id=analysis_id)
            return {
                'status': 'error',
                'error': str(e),
                'tool_name': 'curl-endpoint-tester'
            }

    async def analyze_code_quality(self, model_slug: str, app_number: int, config: Optional[Dict[str, Any]] = None, analysis_id: Optional[str] = None) -> Dict[str, Any]:
        """
        TRUE CODE QUALITY ANALYZER - Measures actual code quality metrics.
        
        Analyzes (inspired by SQ4AI framework and ISO/IEC 25010):
        - Error handling coverage
        - Type safety & annotations
        - Code organization & structure
        - Documentation & comments
        - Anti-pattern detection (console.log, hardcoded secrets, TODOs)
        - Security best practices
        - Performance patterns
        - Testing readiness
        
        Returns both individual metric pass/fail AND aggregate quality score.
        """
        try:
            # Find application path
            app_path = self._resolve_app_path(model_slug, app_number)
            if not app_path or not app_path.exists():
                return {
                    'status': 'error',
                    'error': f'Application path not found: {model_slug} app {app_number}',
                    'tool_name': 'code-quality-analyzer'
                }
            
            self.log.info(f"Code quality analysis for {model_slug} app {app_number}")
            await self.send_progress('starting', f"Starting code quality analysis for {model_slug} app {app_number}", analysis_id=analysis_id)
            
            # Load template for context with smart detection
            template_slug = config.get('template_slug') if config else None
            if not template_slug or template_slug == 'crud_todo_list':
                detected_template = self._detect_template_from_app(model_slug, app_number)
                if detected_template:
                    template_slug = detected_template
                else:
                    template_slug = template_slug or 'crud_todo_list'
            
            template_data = {}
            requirements_file = self._find_requirements_template(template_slug)
            if requirements_file:
                with open(requirements_file, 'r', encoding='utf-8') as f:
                    template_data = json.load(f)
            
            await self.send_progress('reading_code', "Reading LLM-generated code", analysis_id=analysis_id)
            
            # Read code - use optimized mode if enabled (default)
            full_scan = config.get('full_scan', False) if config else False
            use_optimized_mode = config.get('optimized_mode', self.optimized_mode) if config else self.optimized_mode
            
            if full_scan:
                # Legacy: scan ALL files
                code_content = await self._read_app_code(app_path)
                self.log.info(f"Using FULL SCAN mode: all files ({len(code_content)} chars)")
            elif use_optimized_mode:
                # OPTIMIZED: Only scan LLM-generated files (~60-70% token reduction)
                code_content = await self._collect_llm_generated_code(app_path)
                self.log.info(f"Using OPTIMIZED mode: LLM-generated files only ({len(code_content)} chars)")
            else:
                # Default focused: scan backend + frontend directories
                code_content = await self._read_app_code_focused(app_path, focus_dirs=['backend', 'frontend'])
                self.log.info(f"Using FOCUSED mode: backend/frontend directories ({len(code_content)} chars)")
            
            # Detect project type
            project_info = self._detect_project_type(code_content, app_path)
            
            template_context = {
                'name': template_data.get('name', template_slug),
                'category': template_data.get('category', 'Unknown'),
                'description': template_data.get('description', ''),
                'project_type': project_info,
                'optimized_mode': use_optimized_mode
            }
            
            # Get AI model from config or use default
            gemini_model = config.get('gemini_model', self.default_openrouter_model) if config else self.default_openrouter_model
            
            # Get batch mode from config or use instance default
            use_batch_mode = config.get('batch_mode', self.batch_mode) if config else self.batch_mode
            
            self.log.info(f"Quality analysis using model={gemini_model}, batch_mode={use_batch_mode}, optimized_mode={use_optimized_mode}")
            
            # ===== BATCH MODE: Single API call for all metrics (CHEAP - default) =====
            if use_batch_mode:
                await self.send_progress('analyzing_quality', f"Batch analyzing {len(CODE_QUALITY_METRICS)} quality metrics", analysis_id=analysis_id)
                
                quality_results = await self._analyze_quality_metrics_batch(
                    code_content, gemini_model, template_context
                )
                
                # Calculate weighted scores from batch results
                total_weighted_score = sum(r['score'] * r['weight'] for r in quality_results)
                total_weight = sum(r['weight'] for r in quality_results)
            
            # ===== GRANULAR MODE: Individual API call per metric (EXPENSIVE - legacy) =====
            else:
                await self.send_progress('analyzing_quality', f"Analyzing {len(CODE_QUALITY_METRICS)} quality metrics (granular mode)", analysis_id=analysis_id)
                
                # Analyze each quality metric
                quality_results = []
                total_weighted_score = 0.0
                total_weight = 0.0
                
                for metric_id, metric_def in CODE_QUALITY_METRICS.items():
                    await self.send_progress('checking_metric', f"Analyzing: {metric_def['name']}", analysis_id=analysis_id)
                    
                    result = await self._analyze_quality_metric(
                        code_content, 
                        metric_id, 
                        metric_def, 
                        gemini_model, 
                        template_context
                    )
                    
                    quality_results.append(result.to_dict())
                    
                    # Accumulate weighted score
                    total_weighted_score += result.score * result.weight
                    total_weight += result.weight
            
            # Calculate aggregate score (0-100)
            aggregate_score = (total_weighted_score / total_weight) if total_weight > 0 else 0
            
            # Determine quality grade
            quality_grade = self._calculate_quality_grade(aggregate_score)
            
            # Count passed/failed metrics
            passed_metrics = sum(1 for r in quality_results if r['passed'])
            failed_metrics = len(quality_results) - passed_metrics
            
            # Identify critical issues (failed metrics with high weight)
            critical_issues = [
                r for r in quality_results 
                if not r['passed'] and r['weight'] >= 1.3
            ]
            
            await self.send_progress('completed', 
                f"Code quality analysis completed: {aggregate_score:.1f}/100 ({quality_grade}), "
                f"{passed_metrics}/{len(quality_results)} metrics passed", 
                analysis_id=analysis_id
            )
            
            # Calculate API calls made
            api_calls_made = 1 if use_batch_mode else len(CODE_QUALITY_METRICS)
            
            return {
                'status': 'success',
                'tool_name': 'code-quality-analyzer',
                'metadata': {
                    'model_slug': model_slug,
                    'app_number': app_number,
                    'ai_model_used': gemini_model,
                    'batch_mode': use_batch_mode,
                    'optimized_mode': use_optimized_mode,
                    'code_chars_analyzed': len(code_content),
                    'api_calls_made': api_calls_made,
                    'template_slug': template_slug,
                    'template_name': template_data.get('name', template_slug),
                    'template_category': template_data.get('category', 'Unknown'),
                    'project_info': project_info,
                    'full_scan': full_scan,
                    'metrics_analyzed': len(CODE_QUALITY_METRICS),
                    'analysis_time': datetime.now().isoformat()
                },
                'results': {
                    'quality_metrics': quality_results,
                    'summary': {
                        # Aggregate score and grade
                        'aggregate_score': round(aggregate_score, 1),
                        'quality_grade': quality_grade,
                        'grade_description': self._get_grade_description(quality_grade),
                        
                        # Metric counts
                        'total_metrics': len(quality_results),
                        'metrics_passed': passed_metrics,
                        'metrics_failed': failed_metrics,
                        'compliance_percentage': (passed_metrics / len(quality_results) * 100) if quality_results else 0,
                        
                        # Critical issues
                        'critical_issues_count': len(critical_issues),
                        'critical_issues': [
                            {
                                'metric': ci['metric_name'],
                                'findings': ci['findings'][:3]  # Top 3 findings
                            }
                            for ci in critical_issues
                        ],
                        
                        # Score breakdown by category
                        'score_breakdown': {
                            r['metric_id']: {
                                'score': r['score'],
                                'passed': r['passed'],
                                'weight': r['weight']
                            }
                            for r in quality_results
                        },
                        
                        # Backwards compatibility
                        'total_stylistic_requirements': len(quality_results),
                        'stylistic_requirements_met': passed_metrics
                    }
                },
                'recommendations': self._generate_quality_recommendations(quality_results)
            }
            
        except Exception as e:
            self.log.error(f"Code quality analyzer failed: {e}")
            import traceback
            traceback.print_exc()
            await self.send_progress('failed', f"Code quality analyzer failed: {e}", analysis_id=analysis_id)
            return {
                'status': 'error',
                'error': str(e),
                'tool_name': 'code-quality-analyzer'
            }
    
    def _detect_project_type(self, code_content: str, app_path: Path) -> Dict[str, Any]:
        """Detect project technologies and frameworks."""
        project_info = {
            'backend_framework': 'unknown',
            'frontend_framework': 'unknown',
            'languages': [],
            'has_typescript': False,
            'has_tests': False
        }
        
        # Detect backend framework
        if 'from flask import' in code_content or 'import flask' in code_content.lower():
            project_info['backend_framework'] = 'Flask'
        elif 'from fastapi import' in code_content:
            project_info['backend_framework'] = 'FastAPI'
        elif 'from django' in code_content:
            project_info['backend_framework'] = 'Django'
        elif 'express' in code_content.lower() and 'require' in code_content:
            project_info['backend_framework'] = 'Express.js'
        
        # Detect frontend framework
        if 'import React' in code_content or 'from "react"' in code_content:
            project_info['frontend_framework'] = 'React'
        elif 'createApp' in code_content and 'vue' in code_content.lower():
            project_info['frontend_framework'] = 'Vue'
        elif '@angular' in code_content:
            project_info['frontend_framework'] = 'Angular'
        
        # Detect languages
        if '.py' in code_content:
            project_info['languages'].append('Python')
        if '.js' in code_content or '.jsx' in code_content:
            project_info['languages'].append('JavaScript')
        if '.ts' in code_content or '.tsx' in code_content:
            project_info['languages'].append('TypeScript')
            project_info['has_typescript'] = True
        
        # Check for tests
        test_patterns = ['test_', '_test.py', '.test.js', '.spec.ts', 'pytest', 'jest', 'unittest']
        project_info['has_tests'] = any(p in code_content.lower() for p in test_patterns)
        
        return project_info
    
    async def _analyze_quality_metrics_batch(
        self,
        code_content: str,
        model: str,
        template_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Batch analyze ALL quality metrics in a SINGLE API call.
        
        This is ~87% cheaper than individual calls (1 call instead of 8).
        
        Returns:
            List of quality metric results with scores
        """
        if not self.openrouter_api_key:
            self.log.warning("OpenRouter API key not available for batch quality analysis")
            return [
                {
                    'metric_id': metric_id,
                    'metric_name': metric_def['name'],
                    'passed': False,
                    'score': 0,
                    'confidence': 'LOW',
                    'findings': ['OpenRouter API key not available'],
                    'recommendations': [],
                    'evidence': {},
                    'weight': metric_def.get('weight', 1.0)
                }
                for metric_id, metric_def in CODE_QUALITY_METRICS.items()
            ]
        
        try:
            # Build batch prompt for all metrics
            prompt = self._build_batch_quality_prompt(code_content, template_context)
            
            # Truncate if too long
            max_length = self.code_truncation_limit * 2
            if len(prompt) > max_length:
                prompt = prompt[:max_length] + "\n[...truncated...]"
            
            self.log.info(f"Batch analyzing {len(CODE_QUALITY_METRICS)} quality metrics (prompt: {len(prompt)} chars)")
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.openrouter_api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": self.batch_max_response_tokens,
                    "temperature": 0.1
                }
                
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=90)  # Longer timeout for quality analysis
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        ai_response = data['choices'][0]['message']['content']
                        self.log.debug(f"Batch quality response ({len(ai_response)} chars)")
                        
                        # Parse batch response
                        results = self._parse_batch_quality_response(ai_response)
                        self.log.info(f"Parsed {len(results)} quality metrics from batch response")
                        return results
                    else:
                        error_text = await response.text()
                        self.log.warning(f"Batch quality API error: {response.status} - {error_text[:200]}")
                        # Return failed results
                        return [
                            {
                                'metric_id': metric_id,
                                'metric_name': metric_def['name'],
                                'passed': False,
                                'score': 0,
                                'confidence': 'LOW',
                                'findings': [f'API error: {response.status}'],
                                'recommendations': [],
                                'evidence': {},
                                'weight': metric_def.get('weight', 1.0)
                            }
                            for metric_id, metric_def in CODE_QUALITY_METRICS.items()
                        ]
                        
        except Exception as e:
            self.log.error(f"Batch quality analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return [
                {
                    'metric_id': metric_id,
                    'metric_name': metric_def['name'],
                    'passed': False,
                    'score': 0,
                    'confidence': 'LOW',
                    'findings': [f'Analysis error: {str(e)}'],
                    'recommendations': [],
                    'evidence': {},
                    'weight': metric_def.get('weight', 1.0)
                }
                for metric_id, metric_def in CODE_QUALITY_METRICS.items()
            ]
    
    def _build_batch_quality_prompt(self, code_content: str, template_context: Dict[str, Any]) -> str:
        """Build batch prompt for analyzing all quality metrics at once."""
        
        # Truncate code
        if len(code_content) > self.code_truncation_limit:
            code_content = code_content[:self.code_truncation_limit] + "\n[...truncated...]"
        
        # Build metrics list
        metrics_list = []
        for metric_id, metric_def in CODE_QUALITY_METRICS.items():
            metrics_list.append(f"[{metric_id.upper()}] {metric_def['name']}: {metric_def['description']}")
        
        metrics_text = "\n".join(metrics_list)
        
        project_info = template_context.get('project_type', {})
        is_optimized = template_context.get('optimized_mode', False)
        
        # Optimized mode note
        code_note = ""
        if is_optimized:
            code_note = """
NOTE: This is LLM-generated code only (app.py for backend, App.jsx for frontend).
Scaffolding/boilerplate files are excluded as they are identical across all generated apps.
Evaluate quality based on this LLM-generated business logic code.
"""
        
        return f"""Analyze the following LLM-generated web application code for these CODE QUALITY METRICS.
Rate each metric 0-100 and provide brief findings.

PROJECT INFO:
- Backend: {project_info.get('backend_framework', 'Unknown')}
- Frontend: {project_info.get('frontend_framework', 'Unknown')}
{code_note}
METRICS TO EVALUATE:
{metrics_text}

CODE:
{code_content}

Respond with EXACTLY this format for EACH metric (one per line):
[ERROR_HANDLING] SCORE:XX | PASS:YES/NO | Brief finding
[TYPE_SAFETY] SCORE:XX | PASS:YES/NO | Brief finding
[CODE_ORGANIZATION] SCORE:XX | PASS:YES/NO | Brief finding
[DOCUMENTATION] SCORE:XX | PASS:YES/NO | Brief finding
[ANTI_PATTERNS] SCORE:XX | PASS:YES/NO | Brief finding
[SECURITY_PRACTICES] SCORE:XX | PASS:YES/NO | Brief finding
[PERFORMANCE_PATTERNS] SCORE:XX | PASS:YES/NO | Brief finding
[TESTING_READINESS] SCORE:XX | PASS:YES/NO | Brief finding

XX should be a number 0-100. PASS:YES if score >= 60."""
    
    def _parse_batch_quality_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse batch quality metrics response."""
        results = []
        
        for metric_id, metric_def in CODE_QUALITY_METRICS.items():
            # Try to find this metric in response
            pattern = rf'\[{metric_id.upper()}\]\s*SCORE:\s*(\d+)\s*\|\s*PASS:\s*(YES|NO)\s*\|\s*(.+?)(?=\[|$)'
            match = re.search(pattern, response, re.IGNORECASE | re.DOTALL)
            
            if match:
                score = min(100, max(0, int(match.group(1))))
                passed = match.group(2).upper() == 'YES'
                finding = match.group(3).strip()
                # Clean up finding
                finding = ' '.join(finding.split())
                confidence = 'HIGH' if score > 70 else 'MEDIUM' if score > 40 else 'LOW'
            else:
                # Try simpler pattern
                simple_pattern = rf'{metric_id.upper()}[:\s]*(\d+)'
                simple_match = re.search(simple_pattern, response, re.IGNORECASE)
                
                if simple_match:
                    score = min(100, max(0, int(simple_match.group(1))))
                    passed = score >= 60
                    finding = f"Score {score}/100 (parsed from batch)"
                    confidence = 'MEDIUM'
                else:
                    # Default to mid-range score if can't parse
                    self.log.warning(f"Could not parse quality result for {metric_id}")
                    score = 50
                    passed = False
                    finding = "Could not parse from batch response"
                    confidence = 'LOW'
            
            results.append({
                'metric_id': metric_id,
                'metric_name': metric_def['name'],
                'passed': passed,
                'score': score,
                'confidence': confidence,
                'findings': [finding] if finding else [],
                'recommendations': [],
                'evidence': {},
                'weight': metric_def.get('weight', 1.0)
            })
        
        return results
    
    async def _analyze_quality_metric(
        self, 
        code_content: str, 
        metric_id: str, 
        metric_def: Dict[str, Any],
        model: str,
        template_context: Dict[str, Any]
    ) -> QualityMetricResult:
        """Analyze a single code quality metric using AI (legacy/granular mode)."""
        try:
            if not self.openrouter_api_key:
                return QualityMetricResult(
                    metric_id=metric_id,
                    metric_name=metric_def['name'],
                    passed=False,
                    score=0,
                    confidence="LOW",
                    findings=["OpenRouter API key not available"],
                    weight=metric_def.get('weight', 1.0)
                )
            
            # Build quality metric prompt
            prompt = self._build_quality_metric_prompt(code_content, metric_id, metric_def, template_context)
            
            # Truncate if too long
            max_length = 14000
            if len(prompt) > max_length:
                prompt = prompt[:max_length] + "\n[...code truncated...]"
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.openrouter_api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 1000,
                    "temperature": 0.2
                }
                
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=45)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        ai_response = data['choices'][0]['message']['content']
                        return self._parse_quality_metric_response(ai_response, metric_id, metric_def)
                    else:
                        error_text = await response.text()
                        self.log.warning(f"Quality metric API error: {response.status} - {error_text[:200]}")
                        return QualityMetricResult(
                            metric_id=metric_id,
                            metric_name=metric_def['name'],
                            passed=False,
                            score=0,
                            confidence="LOW",
                            findings=[f"API error: {response.status}"],
                            weight=metric_def.get('weight', 1.0)
                        )
                        
        except Exception as e:
            self.log.error(f"Quality metric analysis failed for {metric_id}: {e}")
            return QualityMetricResult(
                metric_id=metric_id,
                metric_name=metric_def['name'],
                passed=False,
                score=0,
                confidence="LOW",
                findings=[f"Analysis error: {str(e)}"],
                weight=metric_def.get('weight', 1.0)
            )
    
    def _build_quality_metric_prompt(
        self, 
        code_content: str, 
        metric_id: str, 
        metric_def: Dict[str, Any],
        template_context: Dict[str, Any]
    ) -> str:
        """Build prompt for analyzing a specific code quality metric."""
        
        checks_list = "\n".join(f"  - {check}" for check in metric_def.get('checks', []))
        
        project_info = template_context.get('project_type', {})
        project_section = ""
        if project_info:
            project_section = f"""
PROJECT CONTEXT:
- Backend: {project_info.get('backend_framework', 'Unknown')}
- Frontend: {project_info.get('frontend_framework', 'Unknown')}
- TypeScript: {'Yes' if project_info.get('has_typescript') else 'No'}
- Has Tests: {'Yes' if project_info.get('has_tests') else 'No'}
"""
        
        return f"""Analyze the following web application code for this CODE QUALITY METRIC:

METRIC: {metric_def['name']}
DESCRIPTION: {metric_def['description']}

SPECIFIC CHECKS TO EVALUATE:
{checks_list}
{project_section}
CODE TO ANALYZE:
{code_content}

Provide your analysis in this EXACT format:

SCORE: [0-100 numeric score based on how well the code meets this metric]
PASSED: [YES if score >= 60, NO otherwise]
CONFIDENCE: [HIGH/MEDIUM/LOW based on how confident you are in the assessment]

FINDINGS:
- [List specific issues found, one per line, starting with -]
- [Be specific: mention file names, line patterns, or code snippets]
- [If no issues, write "No significant issues found"]

RECOMMENDATIONS:
- [List actionable recommendations to improve this metric, one per line]
- [Be specific and actionable]

EVIDENCE:
[Quote 1-3 specific code examples that support your assessment, good or bad]

Focus on practical, real-world code quality concerns. Be specific about what you found in the code."""
    
    def _parse_quality_metric_response(
        self, 
        response: str, 
        metric_id: str, 
        metric_def: Dict[str, Any]
    ) -> QualityMetricResult:
        """Parse AI response for quality metric analysis."""
        result = QualityMetricResult(
            metric_id=metric_id,
            metric_name=metric_def['name'],
            weight=metric_def.get('weight', 1.0)
        )
        
        try:
            # Extract score
            score_match = re.search(r'SCORE:\s*(\d+)', response, re.IGNORECASE)
            if score_match:
                result.score = min(100, max(0, int(score_match.group(1))))
            
            # Extract passed status
            passed_match = re.search(r'PASSED:\s*(YES|NO)', response, re.IGNORECASE)
            if passed_match:
                result.passed = passed_match.group(1).upper() == 'YES'
            else:
                # Fallback: passed if score >= 60
                result.passed = result.score >= 60
            
            # Extract confidence
            confidence_match = re.search(r'CONFIDENCE:\s*(HIGH|MEDIUM|LOW)', response, re.IGNORECASE)
            if confidence_match:
                result.confidence = confidence_match.group(1).upper()
            
            # Extract findings
            findings_match = re.search(r'FINDINGS:\s*\n((?:[-•]\s*.+\n?)+)', response, re.IGNORECASE)
            if findings_match:
                findings_text = findings_match.group(1)
                result.findings = [
                    line.strip().lstrip('-•').strip()
                    for line in findings_text.split('\n')
                    if line.strip() and line.strip().startswith(('-', '•'))
                ]
            
            # Extract recommendations
            recommendations_match = re.search(r'RECOMMENDATIONS:\s*\n((?:[-•]\s*.+\n?)+)', response, re.IGNORECASE)
            if recommendations_match:
                recommendations_text = recommendations_match.group(1)
                result.recommendations = [
                    line.strip().lstrip('-•').strip()
                    for line in recommendations_text.split('\n')
                    if line.strip() and line.strip().startswith(('-', '•'))
                ]
            
            # Extract evidence
            evidence_match = re.search(r'EVIDENCE:\s*\n(.+?)(?=\n\n|\Z)', response, re.IGNORECASE | re.DOTALL)
            if evidence_match:
                result.evidence = {'code_samples': evidence_match.group(1).strip()}
                
        except Exception as e:
            self.log.error(f"Error parsing quality metric response: {e}")
            result.findings.append(f"Parse error: {str(e)}")
        
        return result
    
    def _calculate_quality_grade(self, score: float) -> str:
        """Calculate letter grade from numeric score."""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'
    
    def _get_grade_description(self, grade: str) -> str:
        """Get description for a quality grade."""
        descriptions = {
            'A': 'Excellent - Production ready with high quality standards',
            'B': 'Good - Minor improvements recommended',
            'C': 'Acceptable - Several areas need attention',
            'D': 'Below Standard - Significant improvements needed',
            'F': 'Poor - Major quality issues, refactoring recommended'
        }
        return descriptions.get(grade, 'Unknown grade')
    
    def _generate_quality_recommendations(self, quality_results: List[Dict]) -> List[Dict[str, Any]]:
        """Generate prioritized recommendations from quality results."""
        recommendations = []
        
        # Sort by weight (priority) and failed status
        sorted_results = sorted(
            quality_results,
            key=lambda x: (not x['passed'], -x['weight']),
            reverse=False
        )
        
        for result in sorted_results:
            if not result['passed'] and result.get('recommendations'):
                recommendations.append({
                    'metric': result['metric_name'],
                    'priority': 'HIGH' if result['weight'] >= 1.3 else 'MEDIUM' if result['weight'] >= 1.0 else 'LOW',
                    'score': result['score'],
                    'actions': result['recommendations'][:3]  # Top 3 recommendations
                })
        
        return recommendations[:5]  # Return top 5 priority recommendations
    
    def _detect_template_from_app(self, model_slug: str, app_number: int) -> Optional[str]:
        """Detect the template_slug from app metadata or code analysis.
        
        Detection methods (in order of reliability):
        1. Read from generation payload files (most reliable - contains original prompt)
        2. Analyze code for app-type keywords
        3. Return None to use fallback
        
        Returns:
            template_slug if detected, None otherwise
        """
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
        
        detected_template = None
        
        # Method 1: Read from payload files (most reliable)
        try:
            payload_dirs = [
                Path(f"/app/generated/raw/payloads/{model_slug}/app{app_number}"),
                Path(__file__).parent.parent.parent.parent / "generated" / "raw" / "payloads" / model_slug / f"app{app_number}"
            ]
            
            for payload_dir in payload_dirs:
                if payload_dir.exists():
                    # Read the most recent backend payload (contains requirements prompt)
                    payload_files = sorted(payload_dir.glob("*_backend_*_payload.json"), reverse=True)
                    if not payload_files:
                        payload_files = sorted(payload_dir.glob("*_payload.json"), reverse=True)
                    
                    for payload_file in payload_files[:1]:  # Just the first/most recent
                        try:
                            with open(payload_file, 'r', encoding='utf-8') as f:
                                payload_data = json.load(f)
                            
                            # Extract the prompt content
                            messages = payload_data.get('payload', {}).get('messages', [])
                            prompt_text = ""
                            for msg in messages:
                                content = msg.get('content', '')
                                if isinstance(content, str):
                                    prompt_text += content.lower() + " "
                            
                            # Check patterns against prompt
                            for template_slug, patterns in template_patterns.items():
                                match_count = sum(1 for p in patterns if p in prompt_text)
                                if match_count >= 2:  # At least 2 pattern matches
                                    self.log.info(f"Detected template '{template_slug}' from payload file ({match_count} matches)")
                                    return template_slug
                        except Exception as e:
                            self.log.debug(f"Could not read payload file {payload_file}: {e}")
                    break
        except Exception as e:
            self.log.debug(f"Payload-based template detection failed: {e}")
        
        # Method 2: Analyze app code for keywords
        try:
            app_dirs = [
                Path(f"/app/generated/apps/{model_slug}/app{app_number}"),
                Path(__file__).parent.parent.parent.parent / "generated" / "apps" / model_slug / f"app{app_number}"
            ]
            
            for app_dir in app_dirs:
                if app_dir.exists():
                    code_content = ""
                    # Read backend files (Python)
                    for py_file in (app_dir / "backend").rglob("*.py"):
                        if any(x in str(py_file) for x in ['__pycache__', 'venv']):
                            continue
                        try:
                            code_content += py_file.read_text(encoding='utf-8', errors='ignore').lower() + " "
                        except:
                            pass
                    
                    # Check patterns
                    best_match = None
                    best_score = 0
                    for template_slug, patterns in template_patterns.items():
                        match_count = sum(1 for p in patterns if p in code_content)
                        if match_count > best_score and match_count >= 2:
                            best_score = match_count
                            best_match = template_slug
                    
                    if best_match:
                        self.log.info(f"Detected template '{best_match}' from code analysis ({best_score} matches)")
                        return best_match
                    break
        except Exception as e:
            self.log.debug(f"Code-based template detection failed: {e}")
        
        return None
    
    def _find_requirements_template(self, template_slug: str) -> Optional[Path]:
        """Find requirements template file by slug.
        
        Templates use slug naming convention: {slug}.json
        Examples: crud_todo_list.json, auth_user_management.json, realtime_chat_application.json
        """
        # Normalize slug (allow hyphens and underscores)
        normalized_slug = template_slug.lower().replace('-', '_')
        
        # Try container path first, then development path
        possible_paths = [
            Path(f"/app/misc/requirements/{normalized_slug}.json"),  # Container runtime
            Path(__file__).parent.parent.parent.parent / "misc" / "requirements" / f"{normalized_slug}.json"  # Local dev
        ]
        
        for path in possible_paths:
            if path.exists():
                self.log.info(f"Found template '{template_slug}' at: {path}")
                return path
        
        self.log.warning(f"Template '{template_slug}' not found in any location")
        return None
    
    async def _read_app_code_focused(self, app_path: Path, focus_dirs: List[str]) -> str:
        """Read code files from specific directories only (efficient scanning)."""
        code_content = ""
        
        # Common file extensions to analyze
        extensions = ['.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.vue']
        
        try:
            for focus_dir in focus_dirs:
                target_dir = app_path / focus_dir
                if not target_dir.exists():
                    continue
                
                for ext in extensions:
                    for file_path in target_dir.rglob(f'*{ext}'):
                        # Skip common directories
                        if any(part in str(file_path) for part in ['node_modules', '__pycache__', '.git', 'venv']):
                            continue
                        
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                code_content += f"\n\n=== {file_path.relative_to(app_path)} ===\n{content}"
                        except Exception as e:
                            self.log.debug(f"Could not read file {file_path}: {e}")
                            continue
        except Exception as e:
            self.log.error(f"Error reading focused application code: {e}")
        
        return code_content
    
    async def _collect_llm_generated_code(self, app_path: Path) -> str:
        """
        Collect ONLY LLM-generated code files (not scaffolding/boilerplate).
        
        This is the OPTIMIZED mode that dramatically reduces token usage (~60-70% less)
        by only scanning files where the LLM actually generates app-specific code.
        
        Single-file mode:
        - Backend: app.py (contains all models, auth, routes)
        - Frontend: src/App.jsx (contains all components, pages, API)
        
        Scaffolding files (NOT included - identical across all apps):
        - Backend: requirements.txt, Dockerfile
        - Frontend: main.jsx, App.css, package.json, vite.config.js
        
        Returns:
            Combined code string with file headers
        """
        code_parts = []
        files_collected = []
        total_chars = 0
        
        try:
            # Collect backend LLM-generated files
            for rel_path in self.llm_generated_files.get('backend', []):
                file_path = app_path / 'backend' / rel_path
                if file_path.exists():
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            code_parts.append(f"\n=== backend/{rel_path} ===\n{content}")
                            files_collected.append(f"backend/{rel_path}")
                            total_chars += len(content)
                    except Exception as e:
                        self.log.debug(f"Could not read LLM file {file_path}: {e}")
            
            # Collect frontend LLM-generated files
            for rel_path in self.llm_generated_files.get('frontend', []):
                file_path = app_path / 'frontend' / rel_path
                if file_path.exists():
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            code_parts.append(f"\n=== frontend/{rel_path} ===\n{content}")
                            files_collected.append(f"frontend/{rel_path}")
                            total_chars += len(content)
                    except Exception as e:
                        self.log.debug(f"Could not read LLM file {file_path}: {e}")
            
            self.log.info(f"[OPTIMIZED] Collected {len(files_collected)} LLM-generated files ({total_chars} chars): {files_collected}")
            
        except Exception as e:
            self.log.error(f"Error collecting LLM-generated code: {e}")
        
        return "\n".join(code_parts)

    async def _analyze_requirements_batch(
        self, 
        code_content: str, 
        requirements: List[str], 
        model: str, 
        focus: str, 
        template_context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Batch analyze multiple requirements in a SINGLE API call.
        
        This is ~80-90% cheaper than individual calls since:
        - 1 API call instead of N calls
        - Code content sent once instead of N times
        - Reduces input token count dramatically
        
        Args:
            code_content: The application code to analyze
            requirements: List of requirements to check
            model: OpenRouter model to use
            focus: 'backend', 'frontend', or 'admin'
            template_context: Optional template metadata
            
        Returns:
            List of requirement results [{requirement, met, confidence, explanation, category}]
        """
        if not requirements:
            return []
            
        if not self.openrouter_api_key:
            self.log.warning("OpenRouter API key not available for batch analysis")
            return [
                {
                    'requirement': req,
                    'met': False,
                    'confidence': 'LOW',
                    'explanation': 'OpenRouter API key not available',
                    'category': focus
                }
                for req in requirements
            ]
        
        try:
            # Build batch prompt
            prompt = self._build_batch_requirements_prompt(code_content, requirements, focus, template_context)
            
            # Truncate if too long
            max_length = self.code_truncation_limit * 2  # Allow more for batch
            if len(prompt) > max_length:
                prompt = prompt[:max_length] + "\n[...truncated...]"
            
            self.log.info(f"Batch analyzing {len(requirements)} {focus} requirements (prompt: {len(prompt)} chars)")
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.openrouter_api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": self.batch_max_response_tokens,
                    "temperature": 0.1  # Lower temperature for more consistent parsing
                }
                
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)  # Longer timeout for batch
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        ai_response = data['choices'][0]['message']['content']
                        self.log.debug(f"Batch response ({len(ai_response)} chars): {ai_response[:200]}...")
                        
                        # Parse batch response
                        results = self._parse_batch_requirements_response(ai_response, requirements, focus)
                        self.log.info(f"Parsed {len(results)} results from batch response")
                        return results
                    else:
                        error_text = await response.text()
                        self.log.warning(f"Batch API error: {response.status} - {error_text[:200]}")
                        # Return failed results for all requirements
                        return [
                            {
                                'requirement': req,
                                'met': False,
                                'confidence': 'LOW',
                                'explanation': f'API error: {response.status}',
                                'category': focus
                            }
                            for req in requirements
                        ]
                        
        except Exception as e:
            self.log.error(f"Batch analysis failed: {e}")
            import traceback
            traceback.print_exc()
            # Return failed results for all requirements
            return [
                {
                    'requirement': req,
                    'met': False,
                    'confidence': 'LOW',
                    'explanation': f'Analysis error: {str(e)}',
                    'category': focus
                }
                for req in requirements
            ]
    
    def _build_batch_requirements_prompt(
        self, 
        code_content: str, 
        requirements: List[str], 
        focus: str,
        template_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build a batch prompt for analyzing multiple requirements at once."""
        
        # Truncate code to configured limit
        if len(code_content) > self.code_truncation_limit:
            code_content = code_content[:self.code_truncation_limit] + "\n[...truncated...]"
        
        # Build context section
        is_optimized = template_context.get('optimized_mode', False) if template_context else False
        context_section = ""
        if template_context:
            context_section = f"""
APPLICATION CONTEXT:
- Template: {template_context.get('name', 'Unknown')} ({template_context.get('category', 'Unknown')})
- Description: {template_context.get('description', 'N/A')}
"""
        
        # Optimized mode note
        code_note = ""
        if is_optimized:
            code_note = """
NOTE: This is LLM-generated code only (app.py for backend, App.jsx for frontend).
Scaffolding/boilerplate files are excluded - they are identical across all apps.
"""
        
        # Build numbered requirements list
        requirements_list = "\n".join([f"[REQ{i+1}] {req}" for i, req in enumerate(requirements)])
        
        # Focus-specific guidance
        focus_guidance = {
            'backend': "Focus on: Backend Python code (Flask/FastAPI routes, models, database operations), API endpoints, data models, business logic, server-side validation.",
            'frontend': "Focus on: React/Vue/Angular components, UI elements (buttons, forms, lists), user interactions, visual feedback, accessibility.",
            'admin': "Focus on: Admin dashboard components, statistics/metrics display, data management tables, bulk operations, authentication for admin routes."
        }
        
        return f"""Analyze the following LLM-generated web application code and determine if each requirement is MET or NOT MET.
{context_section}{code_note}
{focus_guidance.get(focus, '')}

REQUIREMENTS TO CHECK:
{requirements_list}

CODE:
{code_content}

Respond with EXACTLY this format for EACH requirement (one per line):
[REQ1] MET:YES/NO | CONF:HIGH/MEDIUM/LOW
[REQ2] MET:YES/NO | CONF:HIGH/MEDIUM/LOW
...and so on for all {len(requirements)} requirements.
"""
    
    def _parse_batch_requirements_response(
        self, 
        response: str, 
        requirements: List[str], 
        focus: str
    ) -> List[Dict[str, Any]]:
        """Parse batch AI response into individual requirement results.
        
        Supports multiple response formats:
        1. [REQ1] MET:YES | CONF:HIGH | explanation
        2. [REQ1] MET: YES | CONF: HIGH | explanation
        3. **[REQ1]** MET:YES | CONF:HIGH | explanation (markdown)
        4. [REQ1] MET:PARTIAL | CONF:MEDIUM | explanation (partial treated as NO)
        5. REQ1: YES - explanation
        6. 1. MET:YES | explanation
        """
        results = []
        
        # Log raw response for debugging (first 500 chars)
        self.log.info(f"Parsing batch response ({len(response)} chars). Preview: {response[:500]}...")
        
        # Helper to interpret met status (handles PARTIAL/PARTIALLY as partial compliance)
        def interpret_met_status(status_text: str) -> tuple:
            """Returns (met: bool, is_partial: bool)"""
            status = status_text.upper().replace(' ', '').replace('_', '')
            if status in ['YES', 'TRUE', 'MET', 'IMPLEMENTED', 'PRESENT', 'FOUND']:
                return (True, False)
            elif status in ['PARTIAL', 'PARTIALLY', 'PARTIALLYMET']:
                return (False, True)  # Partial = not fully met
            else:  # NO, FALSE, NOTMET, MISSING, etc.
                return (False, False)
        
        # Try to parse structured response
        for i, req in enumerate(requirements):
            req_num = i + 1
            met = None
            is_partial = False
            confidence = 'MEDIUM'
            explanation = ''
            
            # Pattern 1: Standard format with optional markdown, flexible spacing
            # [REQ1] MET:YES | CONF:HIGH | explanation  OR  **[REQ1]** MET: YES | CONF: HIGH
            # Also handles MET:PARTIAL, MET:PARTIALLY
            pattern1 = rf'\*?\*?\[REQ{req_num}\]\*?\*?\s*MET:\s*([A-Z]+)\s*\|\s*CONF:\s*(HIGH|MEDIUM|LOW)(?:\s*\|\s*(.+?))?(?=\*?\*?\[REQ|\Z)'
            match = re.search(pattern1, response, re.IGNORECASE | re.DOTALL)
            
            if match:
                met, is_partial = interpret_met_status(match.group(1))
                confidence = match.group(2).upper()
                explanation = (match.group(3) or '').strip()
            else:
                # Pattern 2: Numbered list format (1. MET:YES ...)
                pattern2 = rf'^{req_num}\.\s*MET:\s*([A-Z]+)\s*\|?\s*(?:CONF:\s*(HIGH|MEDIUM|LOW)\s*\|?)?\s*(.+?)(?=^\d+\.|\Z)'
                match = re.search(pattern2, response, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                
                if match:
                    met, is_partial = interpret_met_status(match.group(1))
                    confidence = (match.group(2) or 'MEDIUM').upper()
                    explanation = match.group(3).strip() if match.group(3) else ''
                else:
                    # Pattern 3: REQ format without brackets
                    pattern3 = rf'REQ\s*{req_num}[:\s]+(?:MET[:\s]*)?([A-Z]+)(?:\s*\|?\s*CONF[:\s]*(HIGH|MEDIUM|LOW))?(?:\s*\|?\s*(.+?))?(?=REQ\s*\d|\Z)'
                    match = re.search(pattern3, response, re.IGNORECASE | re.DOTALL)
                    
                    if match:
                        met, is_partial = interpret_met_status(match.group(1))
                        confidence = (match.group(2) or 'MEDIUM').upper()
                        explanation = match.group(3).strip() if match.group(3) else ''
                    else:
                        # Pattern 4: Simple numbered with YES/NO/PARTIAL anywhere on line
                        pattern4 = rf'(?:^|\n)\s*(?:\[?REQ\]?)?{req_num}[.:\)]\s*(.+?)(?=\n\s*(?:\[?REQ\]?)?\d+[.:\)]|\Z)'
                        match = re.search(pattern4, response, re.IGNORECASE | re.DOTALL)
                        
                        if match:
                            line_content = match.group(1)
                            # Look for YES/NO/PARTIAL or MET/NOT MET in the line
                            if re.search(r'\bPARTIAL(LY)?\b', line_content, re.IGNORECASE):
                                met = False
                                is_partial = True
                            elif re.search(r'\b(YES|MET)\b', line_content, re.IGNORECASE) and not re.search(r'\bNOT\s*MET\b', line_content, re.IGNORECASE):
                                met = True
                            elif re.search(r'\b(NO|NOT\s*MET)\b', line_content, re.IGNORECASE):
                                met = False
                            
                            # Extract confidence if present
                            conf_match = re.search(r'CONF[:\s]*(HIGH|MEDIUM|LOW)', line_content, re.IGNORECASE)
                            if conf_match:
                                confidence = conf_match.group(1).upper()
                            
                            # Clean up explanation
                            explanation = re.sub(r'MET:\s*[A-Z]+|CONF:\s*(HIGH|MEDIUM|LOW)|\|', '', line_content, flags=re.IGNORECASE).strip()
            
            # Final fallback: search entire response for requirement keywords
            if met is None:
                # Look for specific mention of the requirement being met/not met
                req_text_short = req[:50].lower()
                # Try to find this requirement being discussed
                context_pattern = rf'(?:requirement\s*{req_num}|req\s*{req_num}|{req_num}[.:\)])[^.]*?(?:\b(is\s+met|implemented|present|exists|has\s+been\s+implemented|not\s+met|missing|not\s+implemented|absent|partial)\b)'
                context_match = re.search(context_pattern, response, re.IGNORECASE)
                
                if context_match:
                    indicator = context_match.group(1).lower()
                    if 'partial' in indicator:
                        met = False
                        is_partial = True
                    else:
                        met = indicator in ['is met', 'implemented', 'present', 'exists', 'has been implemented']
                    confidence = 'LOW'
                    explanation = f"Inferred from context: {context_match.group(0)[:100]}"
                else:
                    # Absolute last resort: not met
                    self.log.warning(f"Could not parse result for REQ{req_num} from batch response")
                    met = False
                    confidence = 'LOW'
                    explanation = 'Could not parse result from batch response'
            
            # Clean up explanation (remove newlines, extra whitespace, markdown)
            explanation = ' '.join(explanation.split())
            explanation = re.sub(r'\*+', '', explanation)  # Remove markdown bold/italic
            explanation = explanation[:500]  # Limit length
            
            # Add partial status to explanation if applicable
            if is_partial and not explanation.lower().startswith('partial'):
                explanation = f"[PARTIAL] {explanation}"
            
            results.append({
                'requirement': req,
                'met': met,
                'confidence': confidence,
                'explanation': explanation if explanation else f"Requirement {req_num} {'met' if met else ('partially met' if is_partial else 'not met')}",
                'category': focus,
                'partial': is_partial  # Include partial flag for further analysis
            })
        
        return results
    
    async def _analyze_requirement_with_gemini(self, code_content: str, requirement: str, model: str, focus: str = 'functional', template_context: Optional[Dict[str, Any]] = None) -> RequirementResult:
        """Analyze requirement using AI via OpenRouter (single requirement - legacy/granular mode)."""
        try:
            if not self.openrouter_api_key:
                return RequirementResult(
                    met=False,
                    confidence="LOW",
                    explanation="OpenRouter API key not available",
                    error="OPENROUTER_API_KEY not set"
                )
            
            # Build focused prompt based on requirement type
            if focus == 'backend':
                prompt = self._build_backend_requirement_prompt(code_content, requirement, template_context)
            elif focus == 'frontend':
                prompt = self._build_frontend_requirement_prompt(code_content, requirement, template_context)
            elif focus == 'admin':
                prompt = self._build_admin_requirement_prompt(code_content, requirement, template_context)
            else:
                # Default functional analysis
                prompt = self._build_analysis_prompt(code_content, requirement, template_context)
            
            # Truncate code if too long (use configurable limit)
            max_code_length = self.code_truncation_limit * 2
            if len(prompt) > max_code_length:
                prompt = prompt[:max_code_length] + "\n[...truncated...]"
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.openrouter_api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": self.max_response_tokens,
                    "temperature": 0.2
                }
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        ai_response = data['choices'][0]['message']['content']
                        return self._parse_ai_response(ai_response)
                    else:
                        error_text = await response.text()
                        self.log.warning(f"AI API error: {response.status} - {error_text}")
                        return RequirementResult(
                            met=False,
                            confidence="LOW",
                            explanation=f"API error: {response.status}",
                            error=error_text
                        )
        except Exception as e:
            self.log.error(f"AI analysis failed: {e}")
            return RequirementResult(
                met=False,
                confidence="LOW",
                explanation=f"Analysis failed: {str(e)}",
                error=str(e)
            )
    
    def _build_backend_requirement_prompt(self, code_content: str, requirement: str, template_context: Optional[Dict[str, Any]] = None) -> str:
        """Build prompt for backend/API requirement analysis."""
        context_section = ""
        if template_context:
            context_section = f"""
APPLICATION CONTEXT:
- Template: {template_context.get('name', 'Unknown')} ({template_context.get('category', 'Unknown')})
- Description: {template_context.get('description', 'N/A')}
- Data Model: {json.dumps(template_context.get('data_model', {}), indent=2) if template_context.get('data_model') else 'N/A'}

"""
        
        return f"""Analyze the following web application BACKEND code to determine if it meets this BACKEND/API requirement:

REQUIREMENT: {requirement}
{context_section}
CODE:
{code_content}

Focus on:
- Backend Python code (Flask/FastAPI routes, models, database operations)
- API endpoint implementations
- Data model definitions and database schema
- Business logic implementation
- Server-side validation

Please analyze the code and respond in this exact format:
MET: [YES/NO]
CONFIDENCE: [HIGH/MEDIUM/LOW]
EXPLANATION: [Brief explanation with specific evidence from the backend code]

Focus on whether the backend functionality described in the requirement is actually implemented."""
    
    def _build_frontend_requirement_prompt(self, code_content: str, requirement: str, template_context: Optional[Dict[str, Any]] = None) -> str:
        """Build prompt for frontend/UI requirement analysis."""
        context_section = ""
        if template_context:
            context_section = f"""
APPLICATION CONTEXT:
- Template: {template_context.get('name', 'Unknown')} ({template_context.get('category', 'Unknown')})
- Description: {template_context.get('description', 'N/A')}

"""
        
        return f"""Analyze the following web application FRONTEND code to determine if it meets this UI/UX requirement:

REQUIREMENT: {requirement}
{context_section}
CODE:
{code_content}

Focus on:
- React/Vue/Angular components and JSX/TSX
- UI elements (buttons, forms, inputs, lists, tables)
- User interaction handlers (onClick, onChange, onSubmit)
- Visual feedback (loading states, error messages, success indicators)
- Accessibility features (aria labels, semantic HTML)
- Responsive design patterns

Please analyze the code and respond in this exact format:
MET: [YES/NO]
CONFIDENCE: [HIGH/MEDIUM/LOW]
EXPLANATION: [Brief explanation with specific UI elements or components found]

Focus on whether the frontend/UI functionality described in the requirement is actually implemented."""
    
    def _build_admin_requirement_prompt(self, code_content: str, requirement: str, template_context: Optional[Dict[str, Any]] = None) -> str:
        """Build prompt for admin panel requirement analysis."""
        context_section = ""
        if template_context:
            context_section = f"""
APPLICATION CONTEXT:
- Template: {template_context.get('name', 'Unknown')} ({template_context.get('category', 'Unknown')})
- Description: {template_context.get('description', 'N/A')}
- Data Model: {json.dumps(template_context.get('data_model', {}), indent=2) if template_context.get('data_model') else 'N/A'}

"""
        
        return f"""Analyze the following web application code to determine if it meets this ADMIN PANEL requirement:

REQUIREMENT: {requirement}
{context_section}
CODE:
{code_content}

Focus on:
- Admin dashboard components and pages
- Statistics/metrics display
- Data management tables (listing all items)
- Bulk operations (select multiple, bulk delete)
- Status toggle functionality (activate/deactivate)
- Admin-specific API endpoints (/api/admin/*)
- Search and filter functionality
- Authentication/authorization for admin routes

Please analyze the code and respond in this exact format:
MET: [YES/NO]
CONFIDENCE: [HIGH/MEDIUM/LOW]
EXPLANATION: [Brief explanation with specific admin features or components found]

Focus on whether the admin panel functionality described in the requirement is actually implemented."""
    
    def _calculate_aggregate_summary(self, tools_results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate aggregate summary from multiple tool results."""
        summary = {
            'tools_run': len(tools_results),
            'tools_successful': 0,
            'overall_compliance': 0.0,
            'requirements_summary': {
                'total_backend': 0,
                'backend_met': 0,
                'total_frontend': 0,
                'frontend_met': 0,
                'total_admin': 0,
                'admin_met': 0,
                'total_endpoints': 0,
                'endpoints_passed': 0,
                'public_endpoints_total': 0,
                'public_endpoints_passed': 0,
                'admin_endpoints_total': 0,
                'admin_endpoints_passed': 0,
                # Backwards compatibility
                'total_functional': 0,
                'functional_met': 0,
                'total_stylistic': 0,
                'stylistic_met': 0
            },
            'quality_summary': {
                'aggregate_score': 0,
                'quality_grade': 'N/A',
                'metrics_passed': 0,
                'metrics_total': 0
            }
        }
        
        compliance_values = []
        
        for tool_name, result in tools_results.items():
            if not isinstance(result, dict):
                continue
                
            if result.get('status') == 'success':
                summary['tools_successful'] += 1
            
            # Extract from requirements-scanner results (new unified tool)
            if tool_name in ['requirements-scanner', 'requirements-checker'] and result.get('status') == 'success':
                results_data = result.get('results', {})
                tool_summary = results_data.get('summary', {})
                
                # New breakdown fields
                summary['requirements_summary']['total_backend'] = tool_summary.get('backend_total', tool_summary.get('total_functional_requirements', 0))
                summary['requirements_summary']['backend_met'] = tool_summary.get('backend_met', tool_summary.get('functional_requirements_met', 0))
                summary['requirements_summary']['total_frontend'] = tool_summary.get('frontend_total', 0)
                summary['requirements_summary']['frontend_met'] = tool_summary.get('frontend_met', 0)
                summary['requirements_summary']['total_admin'] = tool_summary.get('admin_total', 0)
                summary['requirements_summary']['admin_met'] = tool_summary.get('admin_met', 0)
                
                # Endpoint data
                summary['requirements_summary']['total_endpoints'] = tool_summary.get('total_api_endpoints', tool_summary.get('total_control_endpoints', 0))
                summary['requirements_summary']['endpoints_passed'] = tool_summary.get('api_endpoints_passed', tool_summary.get('control_endpoints_passed', 0))
                summary['requirements_summary']['public_endpoints_total'] = tool_summary.get('public_endpoints_total', 0)
                summary['requirements_summary']['public_endpoints_passed'] = tool_summary.get('public_endpoints_passed', 0)
                summary['requirements_summary']['admin_endpoints_total'] = tool_summary.get('admin_endpoints_total', 0)
                summary['requirements_summary']['admin_endpoints_passed'] = tool_summary.get('admin_endpoints_passed', 0)
                
                # Backwards compatibility
                summary['requirements_summary']['total_functional'] = tool_summary.get('total_functional_requirements', summary['requirements_summary']['total_backend'])
                summary['requirements_summary']['functional_met'] = tool_summary.get('functional_requirements_met', summary['requirements_summary']['backend_met'])
                
                if tool_summary.get('compliance_percentage') is not None:
                    compliance_values.append(tool_summary['compliance_percentage'])
            
            # Extract from code-quality-analyzer results (new true quality metrics)
            elif tool_name == 'code-quality-analyzer' and result.get('status') == 'success':
                results_data = result.get('results', {})
                tool_summary = results_data.get('summary', {})
                
                # New quality metrics
                summary['quality_summary']['aggregate_score'] = tool_summary.get('aggregate_score', 0)
                summary['quality_summary']['quality_grade'] = tool_summary.get('quality_grade', 'N/A')
                summary['quality_summary']['metrics_passed'] = tool_summary.get('metrics_passed', 0)
                summary['quality_summary']['metrics_total'] = tool_summary.get('total_metrics', 0)
                
                # Backwards compatibility (stylistic = quality metrics)
                summary['requirements_summary']['total_stylistic'] = tool_summary.get('total_metrics', tool_summary.get('total_stylistic_requirements', 0))
                summary['requirements_summary']['stylistic_met'] = tool_summary.get('metrics_passed', tool_summary.get('stylistic_requirements_met', 0))
                
                if tool_summary.get('compliance_percentage') is not None:
                    compliance_values.append(tool_summary['compliance_percentage'])
        
        # Calculate overall compliance as average of individual tool compliances
        if compliance_values:
            summary['overall_compliance'] = sum(compliance_values) / len(compliance_values)
        
        # Calculate total requirements met ratio (requirements scanner only, not quality metrics)
        total_reqs = (
            summary['requirements_summary']['total_backend'] +
            summary['requirements_summary']['total_frontend'] +
            summary['requirements_summary']['total_admin'] +
            summary['requirements_summary']['total_endpoints']
        )
        total_met = (
            summary['requirements_summary']['backend_met'] +
            summary['requirements_summary']['frontend_met'] +
            summary['requirements_summary']['admin_met'] +
            summary['requirements_summary']['endpoints_passed']
        )
        
        if total_reqs > 0:
            summary['total_requirements'] = total_reqs
            summary['total_met'] = total_met
            summary['total_compliance_percentage'] = (total_met / total_reqs) * 100
        
        return summary
    
    async def handle_message(self, websocket, message_data):
        """Handle incoming WebSocket messages."""
        try:
            self.log.debug(f"Received message type: {message_data.get('type', 'unknown')}")
            msg_type = message_data.get("type", "unknown")
            
            if msg_type == "ai_analyze":
                model_slug = message_data.get("model_slug", "unknown")
                app_number = message_data.get("app_number", 1)
                config = message_data.get("config", None)
                analysis_id = message_data.get("id")
                # Tool selection - support both old and new names, default to requirements only
                requested_tools = list(self.extract_selected_tools(message_data) or ["requirements-scanner"])
                
                # Map old/legacy tool names to new ones for backwards compatibility
                tool_mapping = {
                    "requirements-checker": "requirements-scanner",
                    "openrouter-requirements": "requirements-scanner",  # Legacy
                    "ai_requirements_compliance": "requirements-scanner",  # Legacy API name
                }
                
                tools = []
                for tool in requested_tools:
                    mapped_tool = tool_mapping.get(tool, tool)
                    if mapped_tool not in tools:  # Avoid duplicates
                        tools.append(mapped_tool)
                    if tool != mapped_tool:
                        self.log.info(f"[TOOL-ROUTING] Mapped legacy tool '{tool}' → '{mapped_tool}'")

                if not self.quality_analyzer_enabled and "code-quality-analyzer" in tools:
                    tools.remove("code-quality-analyzer")
                    self.log.info("[TOOL-ROUTING] code-quality-analyzer disabled via AI_QUALITY_ANALYZER_ENABLED=false")
                
                # Validate template_slug is provided in config
                if not config or not config.get('template_slug'):
                    error_msg = "template_slug is required in config for AI analysis"
                    self.log.error(f"[TOOL-EXEC] {error_msg}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": error_msg,
                        "service": self.info.name
                    }))
                    return
                
                self.log.info(f"[TOOL-EXEC] Starting AI analysis for {model_slug} app {app_number} with tools: {tools}")
                print(f"[ai-analyzer] Tool execution started: model={model_slug}, app={app_number}, tools={tools}")
                if config:
                    self.log.info(f"[TOOL-EXEC] Using template: {config.get('template_slug')}, config keys: {list(config.keys())}")
                    print(f"[ai-analyzer] Template: {config.get('template_slug')}, config keys: {list(config.keys())}")
                
                # Run all requested tools and aggregate results
                self.log.debug(f"[TOOL-ROUTING] Routing analysis based on tools: {tools}")
                
                # Aggregate results from multiple tools
                aggregated_results = {
                    'status': 'success',
                    'tools': {},
                    'metadata': {
                        'model_slug': model_slug,
                        'app_number': app_number,
                        'template_slug': config.get('template_slug'),
                        'requested_tools': tools,
                        'analysis_time': datetime.now().isoformat()
                    }
                }
                
                tools_run = 0
                errors = []
                
                # Run requirements-scanner if requested
                if "requirements-scanner" in tools:
                    backend_port = config.get('backend_port', 5000) if config else 5000
                    frontend_port = config.get('frontend_port', 8000) if config else 8000
                    
                    req_result = await self.scan_requirements(
                        model_slug, app_number, backend_port, frontend_port, config, analysis_id=analysis_id
                    )
                    aggregated_results['tools']['requirements-scanner'] = req_result
                    tools_run += 1
                    if req_result.get('status') == 'error':
                        errors.append(f"requirements-scanner: {req_result.get('error', 'Unknown error')}")
                
                # Run curl-endpoint-tester if requested (endpoint testing without AI analysis)
                if "curl-endpoint-tester" in tools:
                    backend_port = config.get('backend_port', 5000) if config else 5000
                    frontend_port = config.get('frontend_port', 8000) if config else 8000
                    
                    curl_result = await self.test_endpoints_only(
                        model_slug, app_number, backend_port, frontend_port, config, analysis_id=analysis_id
                    )
                    aggregated_results['tools']['curl-endpoint-tester'] = curl_result
                    tools_run += 1
                    if curl_result.get('status') == 'error':
                        errors.append(f"curl-endpoint-tester: {curl_result.get('error', 'Unknown error')}")
                
                # Run code-quality-analyzer if requested
                if "code-quality-analyzer" in tools:
                    quality_result = await self.analyze_code_quality(
                        model_slug, app_number, config, analysis_id=analysis_id
                    )
                    aggregated_results['tools']['code-quality-analyzer'] = quality_result
                    tools_run += 1
                    if quality_result.get('status') == 'error':
                        errors.append(f"code-quality-analyzer: {quality_result.get('error', 'Unknown error')}")
                
                # Handle case where no valid tools were specified
                if tools_run == 0:
                    error_msg = f"No valid analysis tool selected. Available: {self._detect_available_tools()}"
                    self.log.error(f"[TOOL-ROUTING] {error_msg}")
                    aggregated_results = {
                        'status': 'error',
                        'error': error_msg
                    }
                else:
                    # Calculate overall summary
                    aggregated_results['summary'] = self._calculate_aggregate_summary(aggregated_results['tools'])
                    
                    # Set overall status based on tool results
                    if errors:
                        aggregated_results['status'] = 'partial_success' if tools_run > len(errors) else 'error'
                        aggregated_results['errors'] = errors
                
                response = {
                    "type": "ai_analysis_result",
                    "status": aggregated_results.get('status', 'success'),
                    "service": self.info.name,
                    "analysis": aggregated_results,
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send(json.dumps(response))
                self.log.info(f"AI analysis completed for {model_slug} app {app_number} ({tools_run} tools run)")
                # Give client time to receive the message before connection closes
                await asyncio.sleep(0.1)
            
            elif msg_type == "server_status":
                response = {
                    "type": "server_status",
                    "service": self.info.name,
                    "version": self.info.version,
                    "status": "healthy",
                    "available_tools": self._detect_available_tools(),
                    "requirements_system": "template-based",
                    "quality_metrics": list(CODE_QUALITY_METRICS.keys()),
                    "configuration": {
                        "default_model": self.default_openrouter_model,
                        "batch_mode": self.batch_mode,
                        "optimized_mode": self.optimized_mode,
                        "llm_generated_files": self.llm_generated_files,
                        "code_truncation_limit": self.code_truncation_limit,
                        "max_response_tokens": self.max_response_tokens,
                        "batch_max_response_tokens": self.batch_max_response_tokens,
                        "quality_analyzer_enabled": self.quality_analyzer_enabled,
                        "configurable_via_env": [
                            "AI_MODEL - Default model (google/gemini-2.5-flash, anthropic/claude-3.5-haiku, etc.)",
                            "AI_BATCH_MODE - true/false (true = cheap batch mode, false = granular mode)",
                            "AI_OPTIMIZED_MODE - true/false (true = only LLM-generated files, ~60-70% token reduction)",
                            "AI_CODE_TRUNCATION_LIMIT - Max code chars per request (default: 4000)",
                            "AI_MAX_RESPONSE_TOKENS - Max tokens per response (default: 300)",
                            "AI_BATCH_MAX_TOKENS - Max tokens for batch responses (default: 1500)",
                            "AI_QUALITY_ANALYZER_ENABLED - Enable code quality tool (default: true)"
                        ],
                        "configurable_via_request": [
                            "config.gemini_model - Override model per request",
                            "config.batch_mode - Override batch mode per request",
                            "config.optimized_mode - Override optimized mode per request"
                        ]
                    },
                    "timestamp": datetime.now().isoformat()
                }
                print(f"[ai-analyzer] Sending server_status response: {response}")
                await websocket.send(json.dumps(response))
                await asyncio.sleep(0.1)
                
            else:
                print(f"[ai-analyzer] Unknown message type: {msg_type}")
                response = {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                    "service": self.info.name
                }
                await websocket.send(json.dumps(response))
                await asyncio.sleep(0.1)
                
        except Exception as e:
            print(f"[ai-analyzer] Error handling message: {e}")
            import traceback
            traceback.print_exc()
            self.log.error(f"Error handling message: {e}")
            error_response = {
                "type": "error",
                "message": f"Internal error: {str(e)}",
                "service": self.info.name
            }
            try:
                await websocket.send(json.dumps(error_response))
            except Exception:
                pass


async def main():
    """Main entry point for the AI analyzer service."""
    try:
        print("[ai-analyzer] Starting AI Analyzer Service...")
        print("[ai-analyzer] ============================================")
        print("[ai-analyzer] COST-OPTIMIZED MODE (Dec 2025)")
        print("[ai-analyzer] - Default model: google/gemini-2.5-flash (cheaper than Haiku)")
        print("[ai-analyzer] - Batch mode: ON (3-4 API calls instead of 20+)")
        print("[ai-analyzer] - Optimized mode: ON (only LLM-generated files, ~60-70% token reduction)")
        print("[ai-analyzer] - Code limit: 30000 chars (reduced tokens)")
        print("[ai-analyzer] ============================================")
        
        # Log API key presence for visibility
        if not os.getenv('OPENROUTER_API_KEY'):
            print("[ai-analyzer] WARNING: OPENROUTER_API_KEY not set - OpenRouter analysis will be limited")
        
        # Log configuration
        print(f"[ai-analyzer] AI_MODEL={os.getenv('AI_MODEL', 'google/gemini-2.5-flash')} (env or default)")
        print(f"[ai-analyzer] AI_BATCH_MODE={os.getenv('AI_BATCH_MODE', 'true')} (env or default)")
        print(f"[ai-analyzer] AI_OPTIMIZED_MODE={os.getenv('AI_OPTIMIZED_MODE', 'true')} (env or default)")
        print(f"[ai-analyzer] AI_CODE_TRUNCATION_LIMIT={os.getenv('AI_CODE_TRUNCATION_LIMIT', '30000')} (env or default)")
        
        print("[ai-analyzer] Initializing service...")
        service = AIAnalyzer()
        print("[ai-analyzer] Service initialized, starting server...")
        await service.run()
        
    except Exception as e:
        print(f"[ai-analyzer] FATAL ERROR: Failed to start service: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    print("[ai-analyzer] Entry point reached")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[ai-analyzer] Service stopped by user")
    except Exception as e:
        print(f"[ai-analyzer] Service crashed: {e}")
        import traceback
        traceback.print_exc()