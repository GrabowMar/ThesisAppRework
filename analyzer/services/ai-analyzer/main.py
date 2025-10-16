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
            self.default_openrouter_model = os.getenv('AI_MODEL', 'anthropic/claude-3-haiku')
            self.preferred_gpt4all_model = os.getenv('GPT4ALL_MODEL', 'Llama 3 8B Instruct')
            
            # GPT4All available models cache
            self.gpt4all_available_models = []
            self.last_check_time = 0
            self.gpt4all_is_available = False
            
            print("[ai-analyzer] Loading application requirements...")
            # Load application requirements
            self.requirements_cache = {}
            self._load_app_requirements()
            
            self.log.info("AI Analyzer initialized")
            print("[ai-analyzer] AIAnalyzer initialization complete")
            if not self.openrouter_api_key:
                self.log.warning("OPENROUTER_API_KEY not set - OpenRouter analysis will be unavailable")
                
        except Exception as e:
            print(f"[ai-analyzer] ERROR during initialization: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _load_app_requirements(self):
        """Load application requirements from all_app_requirements.json."""
        print("[ai-analyzer] Looking for application requirements...")
        try:
            # Look for requirements file in various locations
            possible_paths = [
                Path("/app/all_app_requirements.json"),
                Path("/app/misc/all_app_requirements.json"),
                Path(__file__).parent / "all_app_requirements.json"
            ]
            
            print(f"[ai-analyzer] Checking paths: {[str(p) for p in possible_paths]}")
            
            requirements_data = None
            found_path = None
            for path in possible_paths:
                print(f"[ai-analyzer] Checking {path}: exists={path.exists()}")
                if path.exists():
                    print(f"[ai-analyzer] Loading requirements from: {path}")
                    found_path = path
                    with open(path, 'r', encoding='utf-8') as f:
                        requirements_data = json.load(f)
                    break
            
            if requirements_data:
                print(f"[ai-analyzer] Successfully loaded requirements data from {found_path}")
                # Parse and cache requirements by app number
                for app_key, app_data in requirements_data.items():
                    if app_key.startswith('APP_'):
                        try:
                            app_num = int(app_key.split('_')[1])
                            backend_reqs = app_data.get('BACKEND', [])
                            frontend_reqs = app_data.get('FRONTEND', [])
                            all_reqs = backend_reqs + frontend_reqs
                            self.requirements_cache[app_num] = (all_reqs, f"App {app_num}")
                            print(f"[ai-analyzer] Loaded {len(all_reqs)} requirements for App {app_num}")
                        except (ValueError, IndexError) as e:
                            print(f"[ai-analyzer] Could not parse app key {app_key}: {e}")
                
                print(f"[ai-analyzer] Loaded requirements for {len(self.requirements_cache)} applications")
                if hasattr(self, 'log'):
                    self.log.info(f"Loaded requirements for {len(self.requirements_cache)} applications")
            else:
                print("[ai-analyzer] WARNING: Could not find all_app_requirements.json file")
                if hasattr(self, 'log'):
                    self.log.warning("Could not find all_app_requirements.json file")
                
        except Exception as e:
            print(f"[ai-analyzer] ERROR: Failed to load application requirements: {e}")
            import traceback
            traceback.print_exc()
            if hasattr(self, 'log'):
                self.log.error(f"Failed to load application requirements: {e}")
    
    def _detect_available_tools(self) -> List[str]:
        """Detect available AI analysis tools."""
        tools = ["requirements-scanner", "requirements-analyzer"]  # Core requirements analysis tools
        
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
    
    async def analyze_app_requirements(self, model_slug: str, app_number: int, config: Optional[Dict[str, Any]] = None, analysis_id: Optional[str] = None, selected_tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """Analyze application against requirements using AI."""
        try:
            # Find application path
            app_path = self._resolve_app_path(model_slug, app_number)
            if not app_path or not app_path.exists():
                return {
                    'status': 'error',
                    'error': f'Application path not found: {model_slug} app {app_number}',
                    'model_slug': model_slug,
                    'app_number': app_number
                }
            
            self.log.info(f"AI analysis of {model_slug} app {app_number}")
            await self.send_progress('starting', f"Starting AI analysis for {model_slug} app {app_number}", analysis_id=analysis_id,
                                 model_slug=model_slug, app_number=app_number)
            
            # Get requirements for this app
            requirements, app_name = self.requirements_cache.get(app_number, ([], f"App {app_number}"))
            if not requirements:
                return {
                    'status': 'error',
                    'error': f'No requirements found for app {app_number}',
                    'model_slug': model_slug,
                    'app_number': app_number
                }
            
            await self.send_progress('loading_requirements', f"Loaded {len(requirements)} requirements", analysis_id=analysis_id)
            
            # Read application code
            code_content = await self._read_app_code(app_path)
            if not code_content:
                return {
                    'status': 'error',
                    'error': f'Could not read application code from {app_path}',
                    'model_slug': model_slug,
                    'app_number': app_number
                }
            
            await self.send_progress('analyzing_code', f"Analyzing {len(code_content)} characters of code", analysis_id=analysis_id)
            
            # Analyze each requirement
            results = {
                'model_slug': model_slug,
                'app_number': app_number,
                'app_name': app_name,
                'analysis_time': datetime.now().isoformat(),
                'tools_used': selected_tools or ['ai-requirements'],
                'configuration_applied': config is not None,
                'results': {
                    'requirement_checks': [],
                    'summary': {}
                }
            }
            
            requirement_checks = []
            total_met = 0
            total_requirements = len(requirements)
            
            for i, requirement in enumerate(requirements, 1):
                await self.send_progress('checking_requirement', f"Checking requirement {i}/{total_requirements}", analysis_id=analysis_id)
                
                check = RequirementCheck(requirement=requirement)
                try:
                    # Analyze requirement using AI
                    check.result = await self._analyze_requirement(code_content, requirement, config)
                    if check.result.met:
                        total_met += 1
                except Exception as e:
                    check.result.error = str(e)
                    self.log.error(f"Error analyzing requirement '{requirement}': {e}")
                
                requirement_checks.append(check.to_dict())
            
            results['results']['requirement_checks'] = requirement_checks
            results['results']['summary'] = {
                'total_requirements': total_requirements,
                'requirements_met': total_met,
                'requirements_not_met': total_requirements - total_met,
                'compliance_percentage': (total_met / total_requirements * 100) if total_requirements > 0 else 0,
                'analysis_status': 'completed'
            }
            
            await self.send_progress('completed', f"Analysis completed: {total_met}/{total_requirements} requirements met", 
                                 analysis_id=analysis_id, total_issues=total_requirements - total_met)
            
            return results
            
        except Exception as e:
            self.log.error(f"AI analysis failed: {e}")
            await self.send_progress('failed', f"AI analysis failed: {e}", analysis_id=analysis_id)
            return {
                'status': 'error',
                'error': str(e),
                'model_slug': model_slug,
                'app_number': app_number
            }
    
    def _resolve_app_path(self, model_slug: str, app_number: int) -> Optional[Path]:
        """Resolve application path for analysis."""
        # Try multiple possible locations
        possible_paths = [
            Path('/app/sources') / model_slug / f'app{app_number}',
            Path('/app/generated/apps') / model_slug / f'app{app_number}',
            Path('/app/misc/models') / model_slug / f'app{app_number}',
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
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
                return None
            
            prompt = self._build_analysis_prompt(code_content, requirement)
            
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
                async with session.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=_timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        ai_response = data['choices'][0]['message']['content']
                        return self._parse_ai_response(ai_response)
                    else:
                        self.log.warning(f"OpenRouter API error: {response.status}")
                        return None
        except Exception as e:
            self.log.debug(f"OpenRouter analysis failed: {e}")
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
        
        try:
            # Extract structured information from response
            met_match = re.search(r'MET:\s*(YES|NO)', response, re.IGNORECASE)
            if met_match:
                result.met = met_match.group(1).upper() == 'YES'
            
            confidence_match = re.search(r'CONFIDENCE:\s*(HIGH|MEDIUM|LOW)', response, re.IGNORECASE)
            if confidence_match:
                result.confidence = confidence_match.group(1).upper()
            
            explanation_match = re.search(r'EXPLANATION:\s*(.+)', response, re.IGNORECASE | re.DOTALL)
            if explanation_match:
                result.explanation = explanation_match.group(1).strip()
            else:
                result.explanation = response  # Fallback to full response
        
        except Exception as e:
            result.explanation = f"Error parsing AI response: {e}"
            result.error = str(e)
        
        return result
    
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
                tools = list(self.extract_selected_tools(message_data) or ["requirements-scanner"])
                
                self.log.info(f"Starting AI analysis for {model_slug} app {app_number}")
                if config:
                    self.log.info(f"Using custom configuration: {list(config.keys())}")
                
                analysis_results = await self.analyze_app_requirements(
                    model_slug, app_number, config, analysis_id=analysis_id, selected_tools=tools
                )
                
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
                    "requirements_loaded": len(self.requirements_cache),
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