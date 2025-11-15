#!/usr/bin/env python3
"""
AI Analyzer Service - Requirement-Based Code Analysis
=====================================================

AI-powered analyzer that checks if applications meet specific functional requirements
using GPT4All or OpenRouter APIs. Based on gpt4all_analysis.py logic with static-analyzer structure.
"""

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add the analyzer directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from analyzer.shared.service_base import BaseWSService
from analyzer.shared.path_utils import resolve_app_source_path
import aiohttp


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
        print("[ai-analyzer] Initializing AIAnalyzer...")
        try:
            super().__init__(service_name="ai-analyzer", default_port=2004, version="1.0.0")
            print("[ai-analyzer] BaseWSService initialized")
            
            # API configuration
            self.openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
            self.gpt4all_api_url = os.getenv('GPT4ALL_API_URL', 'http://localhost:4891/v1')
            self.gpt4all_timeout = int(os.getenv('GPT4ALL_TIMEOUT', '30'))
            
            # Default models
            self.default_openrouter_model = os.getenv('AI_MODEL', 'anthropic/claude-3.5-haiku')
            self.preferred_gpt4all_model = os.getenv('GPT4ALL_MODEL', 'Llama 3 8B Instruct')
            
            # GPT4All available models cache
            self.gpt4all_available_models = []
            self.last_check_time = 0
            self.gpt4all_is_available = False
            
            self.log.info("AI Analyzer initialized (template-based requirements system)")
            print("[ai-analyzer] AIAnalyzer initialization complete")
            if not self.openrouter_api_key:
                self.log.warning("OPENROUTER_API_KEY not set - OpenRouter analysis will be unavailable")
                
        except Exception as e:
            print(f"[ai-analyzer] ERROR during initialization: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _detect_available_tools(self) -> List[str]:
        """Detect available AI analysis tools (template-based only)."""
        tools = [
            "requirements-checker",      # Functional requirements + curl endpoint tests
            "code-quality-analyzer"      # Stylistic requirements + code patterns
        ]
        
        # Check GPT4All availability
        try:
            import importlib.util
            if importlib.util.find_spec("aiohttp"):
                tools.append("gpt4all-requirements")
        except ImportError:
            pass
        
        # Check OpenRouter availability
        if self.openrouter_api_key:
            tools.append("openrouter-requirements")
        
        print(f"[ai-analyzer] Available tools: {tools}")
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
        # Try GPT4All first, then fallback to OpenRouter
        result = await self._try_gpt4all_analysis(code_content, requirement, config)
        if result is None and self.openrouter_api_key:
            result = await self._try_openrouter_analysis(code_content, requirement, config)
        
        if result is None:
            return RequirementResult(
                met=False,
                confidence="LOW",
                explanation="No AI service available for analysis",
                error="Both GPT4All and OpenRouter unavailable"
            )
        
        return result
    
    async def _try_gpt4all_analysis(self, code_content: str, requirement: str, config: Optional[Dict[str, Any]] = None) -> Optional[RequirementResult]:
        """Try analysis using GPT4All API."""
        try:
            prompt = self._build_analysis_prompt(code_content, requirement)
            
            async with aiohttp.ClientSession() as session:
                import aiohttp as _aiohttp
                _timeout = _aiohttp.ClientTimeout(total=self.gpt4all_timeout)
                payload = {
                    "model": self.preferred_gpt4all_model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 500,
                    "temperature": 0.1
                }
                async with session.post(
                    f"{self.gpt4all_api_url}/chat/completions",
                    json=payload,
                    timeout=_timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        ai_response = data['choices'][0]['message']['content']
                        return self._parse_ai_response(ai_response)
                    else:
                        self.log.warning(f"GPT4All API error: {response.status}")
                        return None
        except Exception as e:
            self.log.debug(f"GPT4All analysis failed: {e}")
            return None
    
    async def _try_openrouter_analysis(self, code_content: str, requirement: str, config: Optional[Dict[str, Any]] = None) -> Optional[RequirementResult]:
        """Try analysis using OpenRouter API."""
        try:
            if not self.openrouter_api_key:
                self.log.warning("[API] OpenRouter API key not available")
                return None
            
            prompt = self._build_analysis_prompt(code_content, requirement)
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
    
    def _build_analysis_prompt(self, code_content: str, requirement: str) -> str:
        """Build analysis prompt for AI."""
        # Truncate code if too long
        max_code_length = 8000
        if len(code_content) > max_code_length:
            code_content = code_content[:max_code_length] + "\n[...truncated...]"
        
        return f"""Analyze the following web application code to determine if it meets this specific requirement:

REQUIREMENT: {requirement}

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
    
    async def check_requirements_with_curl(self, model_slug: str, app_number: int, backend_port: int, frontend_port: int, config: Optional[Dict[str, Any]] = None, analysis_id: Optional[str] = None) -> Dict[str, Any]:
        """
        NEW TOOL: Check functional requirements with curl endpoint testing + Gemini Flash analysis.
        
        Analyzes:
        1. Control endpoints (/health, /api/status) via curl
        2. Functional requirements via Gemini Flash code analysis
        
        Scans only backend/ and frontend/ directories for efficiency.
        """
        try:
            # Find application path
            app_path = self._resolve_app_path(model_slug, app_number)
            if not app_path or not app_path.exists():
                return {
                    'status': 'error',
                    'error': f'Application path not found: {model_slug} app {app_number}',
                    'tool_name': 'requirements-checker'
                }
            
            self.log.info(f"Requirements checker for {model_slug} app {app_number}")
            await self.send_progress('starting', f"Starting requirements checker for {model_slug} app {app_number}", analysis_id=analysis_id)
            
            # Load requirements template
            template_slug = config.get('template_slug', 'crud_todo_list') if config else 'crud_todo_list'
            requirements_file = self._find_requirements_template(template_slug)
            if not requirements_file:
                return {
                    'status': 'error',
                    'error': f'Requirements template {template_slug} not found',
                    'tool_name': 'requirements-checker'
                }
            
            with open(requirements_file, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
            
            # Support both new and legacy field names with fallback
            functional_requirements = template_data.get('functional_requirements') or template_data.get('backend_requirements', [])
            control_endpoints = template_data.get('control_endpoints', [])
            
            if not functional_requirements and not control_endpoints:
                return {
                    'status': 'warning',
                    'message': 'No functional requirements or control endpoints found in template',
                    'tool_name': 'requirements-checker'
                }
            
            await self.send_progress('testing_endpoints', f"Testing {len(control_endpoints)} control endpoints", analysis_id=analysis_id)
            
            # Test control endpoints
            endpoint_results = []
            for endpoint in control_endpoints:
                path = endpoint.get('path', '/')
                method = endpoint.get('method', 'GET')
                expected_status = endpoint.get('expected_status', 200)
                description = endpoint.get('description', 'Control endpoint')
                
                # Determine base URL (try backend first, then frontend)
                base_url = f"http://localhost:{backend_port}"
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.request(method, f"{base_url}{path}", timeout=aiohttp.ClientTimeout(total=5)) as response:
                            passed = (response.status == expected_status or response.status == 200)  # Flexible: any 200 OK passes
                            endpoint_results.append({
                                'endpoint': path,
                                'method': method,
                                'expected_status': expected_status,
                                'actual_status': response.status,
                                'passed': passed,
                                'description': description,
                                'base_url': base_url
                            })
                except Exception as e:
                    endpoint_results.append({
                        'endpoint': path,
                        'method': method,
                        'expected_status': expected_status,
                        'actual_status': None,
                        'passed': False,
                        'error': str(e),
                        'description': description,
                        'base_url': base_url
                    })
            
            await self.send_progress('analyzing_functional_requirements', f"Analyzing {len(functional_requirements)} functional requirements", analysis_id=analysis_id)
            
            # Read backend and frontend code only (efficient scope)
            code_content = await self._read_app_code_focused(app_path, focus_dirs=['backend', 'frontend'])
            
            # Analyze functional requirements with AI
            functional_results = []
            gemini_model = config.get('gemini_model', 'anthropic/claude-3-5-haiku') if config else 'anthropic/claude-3-5-haiku'
            
            for i, req in enumerate(functional_requirements, 1):
                await self.send_progress('checking_requirement', f"Checking functional requirement {i}/{len(functional_requirements)}", analysis_id=analysis_id)
                
                result = await self._analyze_requirement_with_gemini(code_content, req, gemini_model)
                functional_results.append({
                    'requirement': req,
                    'met': result.met,
                    'confidence': result.confidence,
                    'explanation': result.explanation,
                    'evidence': result.backend_analysis or result.frontend_analysis or {}
                })
            
            # Calculate compliance
            total_functional = len(functional_results)
            met_functional = sum(1 for r in functional_results if r['met'])
            total_endpoints = len(endpoint_results)
            passed_endpoints = sum(1 for e in endpoint_results if e['passed'])
            
            overall_compliance = (
                (met_functional + passed_endpoints) / (total_functional + total_endpoints) * 100
                if (total_functional + total_endpoints) > 0 else 0
            )
            
            await self.send_progress('completed', f"Requirements check completed: {met_functional}/{total_functional} functional, {passed_endpoints}/{total_endpoints} endpoints", analysis_id=analysis_id)
            
            return {
                'status': 'success',
                'tool_name': 'requirements-checker',
                'metadata': {
                    'model_slug': model_slug,
                    'app_number': app_number,
                    'ai_model_used': gemini_model,
                    'template_slug': template_slug,
                    'analysis_time': datetime.now().isoformat()
                },
                'results': {
                    'functional_requirements': functional_results,
                    'control_endpoint_tests': endpoint_results,
                    'summary': {
                        'total_functional_requirements': total_functional,
                        'functional_requirements_met': met_functional,
                        'total_control_endpoints': total_endpoints,
                        'control_endpoints_passed': passed_endpoints,
                        'compliance_percentage': overall_compliance
                    }
                }
            }
            
        except Exception as e:
            self.log.error(f"Requirements checker failed: {e}")
            import traceback
            traceback.print_exc()
            await self.send_progress('failed', f"Requirements checker failed: {e}", analysis_id=analysis_id)
            return {
                'status': 'error',
                'error': str(e),
                'tool_name': 'requirements-checker'
            }
    
    async def analyze_code_quality(self, model_slug: str, app_number: int, config: Optional[Dict[str, Any]] = None, analysis_id: Optional[str] = None) -> Dict[str, Any]:
        """
        NEW TOOL: Analyze code quality against stylistic requirements using Gemini Flash.
        
        Analyzes:
        - Stylistic requirements (React hooks, error handling, loading states, accessibility)
        - Code patterns and quality indicators
        
        Scans only backend/ and frontend/ directories for efficiency.
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
            
            # Load requirements template
            template_slug = config.get('template_slug', 'crud_todo_list') if config else 'crud_todo_list'
            requirements_file = self._find_requirements_template(template_slug)
            if not requirements_file:
                return {
                    'status': 'error',
                    'error': f'Requirements template {template_slug} not found',
                    'tool_name': 'code-quality-analyzer'
                }
            
            with open(requirements_file, 'r', encoding='utf-8') as f:
                template_data = json.load(f)
            
            # Support both new and legacy field names with fallback
            stylistic_requirements = template_data.get('stylistic_requirements') or template_data.get('frontend_requirements', [])
            
            if not stylistic_requirements:
                return {
                    'status': 'warning',
                    'message': 'No stylistic requirements found in template',
                    'tool_name': 'code-quality-analyzer'
                }
            
            await self.send_progress('reading_code', f"Reading backend and frontend code", analysis_id=analysis_id)
            
            # Read backend and frontend code only (efficient scope)
            full_scan = config.get('full_scan', False) if config else False
            if full_scan:
                code_content = await self._read_app_code(app_path)  # Full scan
            else:
                code_content = await self._read_app_code_focused(app_path, focus_dirs=['backend', 'frontend'])  # Focused scan
            
            await self.send_progress('analyzing_stylistic_requirements', f"Analyzing {len(stylistic_requirements)} stylistic requirements", analysis_id=analysis_id)
            
            # Analyze stylistic requirements with AI
            stylistic_results = []
            gemini_model = config.get('gemini_model', 'anthropic/claude-3-5-haiku') if config else 'anthropic/claude-3-5-haiku'
            
            for i, req in enumerate(stylistic_requirements, 1):
                await self.send_progress('checking_requirement', f"Checking stylistic requirement {i}/{len(stylistic_requirements)}", analysis_id=analysis_id)
                
                result = await self._analyze_requirement_with_gemini(code_content, req, gemini_model, focus='quality')
                stylistic_results.append({
                    'requirement': req,
                    'met': result.met,
                    'confidence': result.confidence,
                    'explanation': result.explanation,
                    'patterns_detected': result.frontend_analysis or result.backend_analysis or {}
                })
            
            # Calculate compliance
            total_stylistic = len(stylistic_results)
            met_stylistic = sum(1 for r in stylistic_results if r['met'])
            compliance = (met_stylistic / total_stylistic * 100) if total_stylistic > 0 else 0
            
            await self.send_progress('completed', f"Code quality analysis completed: {met_stylistic}/{total_stylistic} stylistic requirements met", analysis_id=analysis_id)
            
            return {
                'status': 'success',
                'tool_name': 'code-quality-analyzer',
                'metadata': {
                    'model_slug': model_slug,
                    'app_number': app_number,
                    'ai_model_used': gemini_model,
                    'template_slug': template_slug,
                    'full_scan': full_scan,
                    'analysis_time': datetime.now().isoformat()
                },
                'results': {
                    'stylistic_requirements': stylistic_results,
                    'summary': {
                        'total_stylistic_requirements': total_stylistic,
                        'stylistic_requirements_met': met_stylistic,
                        'compliance_percentage': compliance
                    }
                }
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
    
    async def _analyze_requirement_with_gemini(self, code_content: str, requirement: str, model: str, focus: str = 'functional') -> RequirementResult:
        """Analyze requirement using Gemini Flash via OpenRouter."""
        try:
            if not self.openrouter_api_key:
                return RequirementResult(
                    met=False,
                    confidence="LOW",
                    explanation="OpenRouter API key not available",
                    error="OPENROUTER_API_KEY not set"
                )
            
            # Build focused prompt
            if focus == 'quality':
                prompt = self._build_quality_analysis_prompt(code_content, requirement)
            else:
                prompt = self._build_analysis_prompt(code_content, requirement)
            
            # Truncate code if too long
            max_code_length = 12000
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
                    "max_tokens": 800,
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
                        self.log.warning(f"Gemini API error: {response.status} - {error_text}")
                        return RequirementResult(
                            met=False,
                            confidence="LOW",
                            explanation=f"API error: {response.status}",
                            error=error_text
                        )
        except Exception as e:
            self.log.error(f"Gemini analysis failed: {e}")
            return RequirementResult(
                met=False,
                confidence="LOW",
                explanation=f"Analysis failed: {str(e)}",
                error=str(e)
            )
    
    def _build_quality_analysis_prompt(self, code_content: str, requirement: str) -> str:
        """Build quality-focused analysis prompt for stylistic requirements."""
        return f"""Analyze the following web application code to determine if it meets this CODE QUALITY requirement:

REQUIREMENT: {requirement}

CODE:
{code_content}

Focus on:
- Code patterns and best practices
- Implementation quality and consistency
- Presence of required patterns (e.g., React hooks, error handling, loading states)
- Accessibility and user experience considerations

Respond in this exact format:
MET: [YES/NO]
CONFIDENCE: [HIGH/MEDIUM/LOW]
EXPLANATION: [Detailed explanation with specific code examples or patterns found]

Provide concrete evidence from the code to support your assessment."""
    
    async def handle_message(self, websocket, message_data):
        """Handle incoming WebSocket messages."""
        try:
            print(f"[ai-analyzer] Received message: {message_data}")
            msg_type = message_data.get("type", "unknown")
            
            if msg_type == "ai_analyze":
                model_slug = message_data.get("model_slug", "unknown")
                app_number = message_data.get("app_number", 1)
                config = message_data.get("config", None)
                analysis_id = message_data.get("id")
                # Tool selection normalized
                tools = list(self.extract_selected_tools(message_data) or ["requirements-checker"])
                
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
                
                # Route to appropriate analysis method based on selected tools
                self.log.debug(f"[TOOL-ROUTING] Routing analysis based on tools: {tools}")
                if "requirements-checker" in tools:
                    # Get port information
                    backend_port = config.get('backend_port', 5000) if config else 5000
                    frontend_port = config.get('frontend_port', 8000) if config else 8000
                    
                    analysis_results = await self.check_requirements_with_curl(
                        model_slug, app_number, backend_port, frontend_port, config, analysis_id=analysis_id
                    )
                elif "code-quality-analyzer" in tools:
                    analysis_results = await self.analyze_code_quality(
                        model_slug, app_number, config, analysis_id=analysis_id
                    )
                else:
                    # No valid tool specified
                    error_msg = f"No valid analysis tool selected. Available: {self._detect_available_tools()}"
                    self.log.error(f"[TOOL-ROUTING] {error_msg}")
                    analysis_results = {
                        'status': 'error',
                        'error': error_msg
                    }
                
                response = {
                    "type": "ai_analysis_result",
                    "status": "success",
                    "service": self.info.name,
                    "analysis": analysis_results,
                    "timestamp": datetime.now().isoformat()
                }
                
                await websocket.send(json.dumps(response))
                self.log.info(f"AI analysis completed for {model_slug} app {app_number}")
            
            elif msg_type == "server_status":
                response = {
                    "type": "server_status",
                    "service": self.info.name,
                    "version": self.info.version,
                    "status": "healthy",
                    "available_tools": self._detect_available_tools(),
                    "requirements_system": "template-based",
                    "timestamp": datetime.now().isoformat()
                }
                print(f"[ai-analyzer] Sending server_status response: {response}")
                await websocket.send(json.dumps(response))
                
            else:
                print(f"[ai-analyzer] Unknown message type: {msg_type}")
                response = {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                    "service": self.info.name
                }
                await websocket.send(json.dumps(response))
                
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
        
        # Log API key presence for visibility
        if not os.getenv('OPENROUTER_API_KEY'):
            print("[ai-analyzer] WARNING: OPENROUTER_API_KEY not set - OpenRouter analysis will be limited")
        
        if not os.getenv('GPT4ALL_API_URL'):
            print("[ai-analyzer] INFO: GPT4ALL_API_URL not set - using default http://localhost:4891/v1")
        
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