#!/usr/bin/env python3
"""
OpenRouter Analysis System
==========================

A robust system for analyzing code against app requirements using OpenRouter API.
Built in the style of combined.py with enhanced error handling and logging.

IMPORTANT: This module includes special handling for SSL monkey-patching issues
that can occur when used alongside libraries like locust, gevent, or eventlet.
If RecursionError occurs during HTTPS requests, the module will automatically
disable SSL verification as a workaround.
"""

import json
import os
import re
import sys
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from datetime import datetime
from dotenv import load_dotenv

# Import requests after any potential monkey patching
try:
    import requests
    # Suppress SSL warnings when we need to disable verification
    import urllib3
    from urllib3.exceptions import InsecureRequestWarning
    urllib3.disable_warnings(InsecureRequestWarning)
except ImportError:
    # If requests fails to import due to SSL issues, try to fix it
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    import requests
    import urllib3
    from urllib3.exceptions import InsecureRequestWarning
    urllib3.disable_warnings(InsecureRequestWarning)

# Load environment variables
load_dotenv()

# =============================================================================
# Constants
# =============================================================================

DEFAULT_TIMEOUT = 30
DEFAULT_TEMPERATURE = 0.1
DEFAULT_MAX_TOKENS = 1500
MAX_CODE_LENGTH = 15000
MIN_API_KEY_LENGTH = 20
RATE_LIMIT_DELAY = 0.5
MAX_RETRIES = 3
RETRY_DELAY = 2.0
EXPONENTIAL_BACKOFF = True

# =============================================================================
# Logging Setup
# =============================================================================

def setup_logging() -> logging.Logger:
    """Setup application logging in combined.py style"""
    logger = logging.getLogger("OpenRouterAnalyzer")
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s]: %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger

# Initialize logger
logger = setup_logging()

# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class RequirementResult:
    """Result of analyzing a single requirement."""
    met: bool = False
    confidence: str = "LOW"  # HIGH, MEDIUM, LOW
    explanation: str = ""
    code_evidence: str = ""
    recommendations: str = ""
    error: Optional[str] = None
    analysis_time: float = 0.0
    tokens_used: int = 0

@dataclass
class RequirementCheck:
    """A requirement and its analysis result."""
    requirement: str
    result: RequirementResult
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ModelInfo:
    """Information about an OpenRouter model with enhanced capabilities."""
    id: str
    name: str
    context_length: int = 32000
    free: bool = False
    capabilities: Set[str] = field(default_factory=set)
    description: str = ""
    provider: str = "openrouter"

# =============================================================================
# OpenRouter API Integration
# =============================================================================

class OpenRouterAnalyzer:
    """Analyzes code against requirements using OpenRouter API in combined.py style."""
    
    # Available models (same as combined.py)
    AVAILABLE_MODELS = {
        "mistralai/mistral-small-3.2-24b-instruct:free": ModelInfo(
            id="mistralai/mistral-small-3.2-24b-instruct:free",
            name="Mistral Small 3.2 24B (Free)",
            context_length=96000,
            free=True,
            capabilities={"code_analysis", "requirements_checking"},
            description="Free tier Mistral model for code analysis"
        ),
        "mistralai/mistral-small-3.2-24b-instruct": ModelInfo(
            id="mistralai/mistral-small-3.2-24b-instruct",
            name="Mistral Small 3.2 24B",
            context_length=96000,
            free=False,
            capabilities={"code_analysis", "requirements_checking"},
            description="Premium Mistral model for code analysis"
        ),
    }
    
    def __init__(self, base_path: Optional[str] = None):
        """Initialize the analyzer with enhanced error handling."""
        self.base_path = Path(base_path) if base_path else Path.cwd()
        
        # Check for monkey patching issues
        self._check_monkey_patching()
        
        # Ensure we're using the project root directory
        self._find_project_root()
        
        # Load environment variables from the project root
        self._load_environment()
        
        # Initialize API configuration (following combined.py pattern)
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.site_url = os.getenv("OPENROUTER_SITE_URL", "https://thesis-research-app.local")
        self.site_name = os.getenv("OPENROUTER_SITE_NAME", "Thesis Research App")
        self.preferred_model = "mistralai/mistral-small-3.2-24b-instruct:free"
        
        # Flag to track SSL issues
        self.ssl_verify = True
        
        # Statistics tracking
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_analysis_time': 0.0,
            'total_tokens_used': 0
        }
        
        # Validate setup
        self._validate_setup()
    
    def _check_monkey_patching(self) -> None:
        """Check if SSL has been monkey patched and warn."""
        try:
            # Check if gevent or similar has monkey patched
            if 'gevent' in sys.modules or 'eventlet' in sys.modules:
                logger.warning("Detected gevent/eventlet - SSL module may be monkey-patched.")
                logger.warning("Will use SSL verification workarounds for HTTPS requests.")
                self.ssl_verify = False
            # Check for locust specifically
            elif 'locust' in sys.modules:
                logger.warning("Detected locust import - SSL module is likely monkey-patched.")
                logger.warning("Will disable SSL verification to avoid RecursionError.")
                self.ssl_verify = False
        except Exception:
            pass
    
    def _get_session(self) -> requests.Session:
        """Get a properly configured requests session."""
        session = requests.Session()
        # If we're in a monkey-patched environment, configure accordingly
        if not self.ssl_verify:
            session.verify = False
        return session
    
    def _find_project_root(self) -> None:
        """Find the project root directory containing src folder."""
        if not (self.base_path / "src").exists():
            current = Path.cwd()
            while current != current.parent:
                if (current / "src").exists():
                    self.base_path = current
                    logger.info(f"Found project root: {self.base_path}")
                    return
                current = current.parent
            
            # If we can't find src, use current directory
            self.base_path = Path.cwd()
            logger.warning(f"Could not find project root with src/, using: {self.base_path}")
    
    def _load_environment(self) -> None:
        """Load environment variables from project root."""
        env_file = self.base_path / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            logger.info(f"Loaded environment from: {env_file}")
        else:
            logger.warning(f"No .env file found at: {env_file}")
    
    def _validate_setup(self) -> None:
        """Validate the analyzer setup."""
        logger.info(f"Initializing OpenRouterAnalyzer - base_path: {self.base_path}")
        
        # Validate API key
        if not self.api_key:
            logger.error("No OpenRouter API key found. Set OPENROUTER_API_KEY in .env file")
            # Don't raise exception here - let the app handle it
            return
        
        if len(self.api_key) < MIN_API_KEY_LENGTH:
            logger.error(f"API key seems too short: {len(self.api_key)} characters")
            return
        
        logger.info(f"API key loaded: {self.api_key[:20]}...")
        logger.info(f"Using model: {self.preferred_model}")
        logger.info(f"SSL verification: {self.ssl_verify}")
    
    def get_headers(self) -> Dict[str, str]:
        """Get API headers for requests (matching combined.py pattern)."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Add site headers (important for OpenRouter)
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.site_name:
            headers["X-Title"] = self.site_name
        
        return headers
    
    def is_api_available(self) -> bool:
        """Check if OpenRouter API is available with enhanced error handling."""
        if not self.api_key:
            logger.error("API key not available")
            return False
        
        try:
            logger.info("Testing OpenRouter API connection...")
            
            # Create a session with SSL workaround for monkey-patching issues
            session = requests.Session()
            
            # Use ssl_verify flag set during initialization
            verify = self.ssl_verify
            
            try:
                # Try with current SSL verification setting
                response = session.get(
                    f"{self.api_url.replace('/chat/completions', '/models')}",
                    headers=self.get_headers(),
                    timeout=15,
                    verify=verify
                )
            except (requests.exceptions.SSLError, RecursionError) as e:
                if verify:
                    logger.warning(f"SSL verification failed ({type(e).__name__}), retrying without verification...")
                    logger.warning("This is likely due to locust/gevent monkey-patching SSL. Disabling SSL verification for this session.")
                    # Retry without SSL verification and remember this for future requests
                    self.ssl_verify = False
                    response = session.get(
                        f"{self.api_url.replace('/chat/completions', '/models')}",
                        headers=self.get_headers(),
                        timeout=15,
                        verify=False
                    )
                else:
                    raise
            
            if response.status_code == 200:
                logger.info(f"OpenRouter API connection successful (SSL verify: {self.ssl_verify})")
                return True
            else:
                logger.error(f"API test failed: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("API connection timeout")
            return False
        except requests.exceptions.ConnectionError:
            logger.error("API connection error - check internet connection")
            return False
        except RecursionError as e:
            logger.error(f"RecursionError in API check - SSL monkey patching issue detected")
            # Set flag for future requests
            self.ssl_verify = False
            
            # Try one more time without SSL verification
            try:
                response = requests.get(
                    f"{self.api_url.replace('/chat/completions', '/models')}",
                    headers=self.get_headers(),
                    timeout=15,
                    verify=False
                )
                if response.status_code == 200:
                    logger.info("OpenRouter API connection successful (SSL disabled due to monkey patching)")
                    return True
                else:
                    logger.error(f"API test failed even without SSL: {response.status_code}")
                    return False
            except Exception as retry_error:
                logger.error(f"Retry without SSL also failed: {retry_error}")
                return False
        except Exception as e:
            logger.error(f"API availability check failed: {e}")
            return False
    
    def load_app_requirements(self, app_num: int) -> Tuple[List[str], str]:
        """Load requirements for a specific app from requirements.json."""
        # Load from src/requirements.json
        requirements_file = self.base_path / "src" / "requirements.json"
        if requirements_file.exists():
            try:
                with open(requirements_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Look for app in applications array
                app_key = f"app_{app_num}"
                if "applications" in data:
                    for app in data["applications"]:
                        if app.get("id") == app_key:
                            # Combine all requirement types
                            requirements = []
                            requirements.extend(app.get("specific_features", []))
                            requirements.extend(app.get("general_features", []))
                            requirements.extend(app.get("requirements", []))
                            
                            # Remove duplicates while preserving order
                            unique_requirements = []
                            seen = set()
                            for req in requirements:
                                req_lower = req.lower()
                                if req_lower not in seen:
                                    seen.add(req_lower)
                                    unique_requirements.append(req)
                            
                            return unique_requirements, app.get("name", f"App {app_num}")
                
                logger.warning(f"App {app_key} not found in requirements.json")
                
            except Exception as e:
                logger.error(f"Error loading requirements from {requirements_file}: {e}")
        else:
            logger.error(f"Requirements file not found at {requirements_file}")
        
        # Default requirements if loading fails
        default_requirements = [
            "Complete user authentication system with registration and login",
            "Secure password handling with proper hashing",
            "Session management for user state",
            "Protected routes requiring authentication",
            "Clean, responsive user interface",
            "Proper error handling and validation",
            "RESTful API endpoints with proper HTTP methods",
            "Database integration with proper schema"
        ]
        
        return default_requirements, f"App {app_num}"
    
    def _clean_requirement(self, text: str) -> str:
        """Clean and format a requirement text."""
        # Remove markdown formatting
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*([^*]+)\*', r'\1', text)      # Italic
        text = re.sub(r'`([^`]+)`', r'\1', text)        # Code
        text = re.sub(r'^\d+\.\s*', '', text)            # Numbered lists
        text = re.sub(r'^\*\s*', '', text)               # Bullet points
        text = re.sub(r'^-\s*', '', text)                # Dashes
        
        # Clean up whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    def collect_app_code(self, model: str, app_num: int) -> Tuple[str, str]:
        """Collect frontend and backend code for an app."""
        app_dir = self.base_path / "models" / model / f"app{app_num}"
        
        if not app_dir.exists():
            logger.warning(f"App directory not found: {app_dir}")
            return "", ""
        
        frontend_code = ""
        backend_code = ""
        
        # Collect frontend code
        frontend_dir = app_dir / "frontend"
        if frontend_dir.exists():
            frontend_files = list(frontend_dir.glob("**/*.js")) + list(frontend_dir.glob("**/*.jsx"))
            for file in frontend_files[:5]:  # Limit files
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        frontend_code += f"\n\n--- {file.name} ---\n{content}"
                except Exception as e:
                    logger.error(f"Error reading {file}: {e}")
        
        # Collect backend code
        backend_dir = app_dir / "backend"
        if backend_dir.exists():
            backend_files = list(backend_dir.glob("**/*.py"))
            for file in backend_files[:5]:  # Limit files
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        backend_code += f"\n\n--- {file.name} ---\n{content}"
                except Exception as e:
                    logger.error(f"Error reading {file}: {e}")
        
        return frontend_code.strip(), backend_code.strip()
    
    def analyze_requirement(self, requirement: str, code: str, is_frontend: bool = True) -> RequirementResult:
        """Analyze a single requirement against code (following combined.py pattern)."""
        start_time = time.time()
        
        if not self.api_key:
            return RequirementResult(
                met=False,
                confidence="LOW",
                explanation="OpenRouter API key not available",
                error="No API key",
                analysis_time=time.time() - start_time
            )
        
        if not code.strip():
            return RequirementResult(
                met=False,
                confidence="HIGH",
                explanation="No code provided for analysis",
                error="No code",
                analysis_time=time.time() - start_time
            )
        
        # Truncate code if too long
        if len(code) > MAX_CODE_LENGTH:
            code = code[:MAX_CODE_LENGTH] + "\n... [truncated]"
        
        # Create prompt (matching combined.py style)
        code_type = "frontend" if is_frontend else "backend"
        
        user_prompt = f"""Analyze if the following requirement is met in the provided {code_type} code.

Requirement: {requirement}

Code:
```
{code}
```

Return your analysis as a JSON object with these fields:
- "met": boolean (true if requirement is satisfied)
- "confidence": "HIGH", "MEDIUM", or "LOW"
- "explanation": detailed explanation with code references
- "code_evidence": specific code snippets supporting your conclusion
- "recommendations": suggestions for improvement (if needed)

Be thorough and provide specific evidence. Return ONLY the JSON object."""

        payload = {
            "model": self.preferred_model,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "temperature": DEFAULT_TEMPERATURE,
            "max_tokens": DEFAULT_MAX_TOKENS
        }

        try:
            # Update stats
            self.stats['total_requests'] += 1
            
            logger.info(f"Analyzing requirement with {self.preferred_model}...")
            
            # Create session
            session = requests.Session()
            
            try:
                # Use the ssl_verify flag determined during initialization or API check
                response = session.post(
                    self.api_url,
                    json=payload,
                    headers=self.get_headers(),
                    timeout=DEFAULT_TIMEOUT,
                    verify=self.ssl_verify
                )
            except (requests.exceptions.SSLError, RecursionError) as e:
                if self.ssl_verify:
                    logger.warning(f"SSL verification failed ({type(e).__name__}), retrying without verification...")
                    logger.warning("This is likely due to locust/gevent monkey-patching SSL.")
                    # Retry without SSL verification
                    self.ssl_verify = False
                    response = session.post(
                        self.api_url,
                        json=payload,
                        headers=self.get_headers(),
                        timeout=DEFAULT_TIMEOUT,
                        verify=False
                    )
                else:
                    raise
            
            analysis_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # Extract token usage if available
                tokens_used = data.get("usage", {}).get("total_tokens", 0)
                self.stats['total_tokens_used'] += tokens_used
                
                # Try to parse JSON response
                try:
                    # Clean the response to extract JSON
                    content = content.strip()
                    # Remove markdown code blocks if present
                    if content.startswith("```json"):
                        content = content[7:]
                    if content.startswith("```"):
                        content = content[3:]
                    if content.endswith("```"):
                        content = content[:-3]
                    content = content.strip()
                    
                    result = json.loads(content)
                    self.stats['successful_requests'] += 1
                    return RequirementResult(
                        met=result.get("met", False),
                        confidence=result.get("confidence", "LOW"),
                        explanation=result.get("explanation", ""),
                        code_evidence=result.get("code_evidence", ""),
                        recommendations=result.get("recommendations", ""),
                        analysis_time=analysis_time,
                        tokens_used=tokens_used
                    )
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse JSON response: {e}")
                    # Try to extract JSON from response
                    json_match = re.search(r'\{.*?"met".*?\}', content, re.DOTALL)
                    if json_match:
                        try:
                            result = json.loads(json_match.group(0))
                            self.stats['successful_requests'] += 1
                            return RequirementResult(
                                met=result.get("met", False),
                                confidence=result.get("confidence", "LOW"),
                                explanation=result.get("explanation", ""),
                                code_evidence=result.get("code_evidence", ""),
                                recommendations=result.get("recommendations", ""),
                                analysis_time=analysis_time,
                                tokens_used=tokens_used
                            )
                        except json.JSONDecodeError:
                            pass
                    
                    # Fallback to text analysis
                    met = any(word in content.lower() for word in ["true", "yes", "satisfied", "met", "implemented"])
                    self.stats['successful_requests'] += 1
                    return RequirementResult(
                        met=met,
                        confidence="LOW",
                        explanation=content[:500] + "..." if len(content) > 500 else content,
                        code_evidence="Analysis based on text parsing",
                        recommendations="Manual review recommended",
                        analysis_time=analysis_time,
                        tokens_used=tokens_used
                    )
            else:
                self.stats['failed_requests'] += 1
                logger.error(f"API Error: {response.status_code} - {response.text}")
                return RequirementResult(
                    met=False,
                    confidence="LOW",
                    explanation=f"API error: {response.status_code}",
                    error=f"HTTP {response.status_code}",
                    analysis_time=analysis_time
                )
                
        except requests.exceptions.Timeout:
            self.stats['failed_requests'] += 1
            logger.error("Request timeout")
            return RequirementResult(
                met=False,
                confidence="LOW",
                explanation="Request timeout",
                error="Timeout",
                analysis_time=time.time() - start_time
            )
        except requests.exceptions.ConnectionError:
            self.stats['failed_requests'] += 1
            logger.error("Connection error")
            return RequirementResult(
                met=False,
                confidence="LOW",
                explanation="Connection error",
                error="Connection failed",
                analysis_time=time.time() - start_time
            )
        except RecursionError as e:
            self.stats['failed_requests'] += 1
            logger.error(f"RecursionError during analysis - SSL monkey patching issue")
            logger.error("Please restart the application or disable locust imports")
            return RequirementResult(
                met=False,
                confidence="LOW",
                explanation="SSL recursion error - monkey patching conflict",
                error="RecursionError",
                analysis_time=time.time() - start_time
            )
        except Exception as e:
            self.stats['failed_requests'] += 1
            logger.error(f"Analysis error: {e}")
            return RequirementResult(
                met=False,
                confidence="LOW",
                explanation=f"Analysis error: {str(e)}",
                error=str(e),
                analysis_time=time.time() - start_time
            )
    
    def analyze_app(self, model: str, app_num: int) -> List[RequirementCheck]:
        """Analyze all requirements for a specific app."""
        logger.info(f"Analyzing {model}/app{app_num}...")
        
        # Check API availability
        if not self.is_api_available():
            logger.error("OpenRouter API not available")
            return []
        
        # Load requirements
        requirements, app_name = self.load_app_requirements(app_num)
        logger.info(f"Found {len(requirements)} requirements for {app_name}")
        
        # Collect code
        frontend_code, backend_code = self.collect_app_code(model, app_num)
        
        if not frontend_code and not backend_code:
            logger.error("No code found for analysis")
            return []
        
        results = []
        
        for i, req in enumerate(requirements):
            logger.info(f"  Analyzing requirement {i+1}/{len(requirements)}: {req[:50]}...")
            
            # Analyze frontend
            frontend_result = None
            if frontend_code:
                frontend_result = self.analyze_requirement(req, frontend_code, is_frontend=True)
            
            # Analyze backend
            backend_result = None
            if backend_code:
                backend_result = self.analyze_requirement(req, backend_code, is_frontend=False)
            
            # Combine results
            combined_result = self._combine_results(req, frontend_result, backend_result)
            results.append(RequirementCheck(req, combined_result))
            
            time.sleep(RATE_LIMIT_DELAY)  # Rate limiting
        
        # Save results
        self._save_results(model, app_num, results)
        
        met_count = sum(1 for check in results if check.result.met)
        logger.info(f"Analysis complete: {met_count}/{len(results)} requirements met")
        
        return results
    
    def _combine_results(self, requirement: str, frontend_result: Optional[RequirementResult], 
                        backend_result: Optional[RequirementResult]) -> RequirementResult:
        """Combine frontend and backend analysis results."""
        
        if not frontend_result and not backend_result:
            return RequirementResult(
                met=False,
                confidence="LOW",
                explanation="No analysis results available",
                error="No results"
            )
        
        if not frontend_result:
            if backend_result:
                return backend_result
            else:
                return RequirementResult(met=False, confidence="LOW", explanation="No results", error="No analysis")
        
        if not backend_result:
            return frontend_result
        
        # Both results available - combine intelligently
        req_lower = requirement.lower()
        
        # UI/Frontend focused
        if any(term in req_lower for term in ['ui', 'interface', 'frontend', 'user', 'view', 'component', 'responsive']):
            primary = frontend_result
            secondary = backend_result
        # Backend focused
        elif any(term in req_lower for term in ['api', 'database', 'server', 'backend', 'auth', 'security', 'endpoint']):
            primary = backend_result
            secondary = frontend_result
        # Full-stack - both must be met
        else:
            met = frontend_result.met and backend_result.met
            conf_scores = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
            max_conf = max(conf_scores.get(frontend_result.confidence, 1), 
                          conf_scores.get(backend_result.confidence, 1))
            confidence = "HIGH" if max_conf == 3 else "MEDIUM" if max_conf == 2 else "LOW"
            
            return RequirementResult(
                met=met,
                confidence=confidence,
                explanation=f"Frontend: {frontend_result.explanation}\n\nBackend: {backend_result.explanation}",
                code_evidence=f"Frontend: {frontend_result.code_evidence}\n\nBackend: {backend_result.code_evidence}",
                recommendations=f"Frontend: {frontend_result.recommendations}\n\nBackend: {backend_result.recommendations}"
            )
        
        return RequirementResult(
            met=primary.met,
            confidence=primary.confidence,
            explanation=f"Primary: {primary.explanation}\n\nSecondary: {secondary.explanation}",
            code_evidence=f"Primary: {primary.code_evidence}\n\nSecondary: {secondary.code_evidence}",
            recommendations=f"Primary: {primary.recommendations}\n\nSecondary: {secondary.recommendations}"
        )
    
    def _save_results_to_database(self, model: str, app_num: int, results: List[RequirementCheck]) -> bool:
        """Save analysis results to database instead of files."""
        try:
            from models import GeneratedApplication, OpenRouterAnalysis, AnalysisStatus
            from extensions import db
            from datetime import datetime
            
            # Find the application
            app = GeneratedApplication.query.filter_by(model_slug=model, app_number=app_num).first()
            if not app:
                logger.warning(f"GeneratedApplication not found for {model}/app{app_num}")
                return False
            
            # Create or update OpenRouterAnalysis record
            or_analysis = OpenRouterAnalysis.query.filter_by(application_id=app.id).first()
            if not or_analysis:
                or_analysis = OpenRouterAnalysis()
                or_analysis.application_id = app.id
                db.session.add(or_analysis)
            
            # Update analysis fields
            or_analysis.status = AnalysisStatus.COMPLETED
            or_analysis.completed_at = datetime.utcnow()
            
            if not or_analysis.started_at:
                or_analysis.started_at = datetime.utcnow()
            
            # Extract counts from results
            or_analysis.total_requirements = len(results)
            or_analysis.met_requirements = sum(1 for check in results if check.result.met)
            or_analysis.unmet_requirements = or_analysis.total_requirements - or_analysis.met_requirements
            or_analysis.high_confidence_count = sum(1 for check in results if check.result.confidence == "HIGH")
            or_analysis.medium_confidence_count = sum(1 for check in results if check.result.confidence == "MEDIUM")
            or_analysis.low_confidence_count = sum(1 for check in results if check.result.confidence == "LOW")
            
            # Prepare results data
            results_data = {
                "model": model,
                "app_num": app_num,
                "timestamp": time.time(),
                "requirements": [
                    {
                        "requirement": check.requirement,
                        "met": check.result.met,
                        "confidence": check.result.confidence,
                        "explanation": check.result.explanation,
                        "code_evidence": check.result.code_evidence,
                        "recommendations": check.result.recommendations,
                        "error": check.result.error
                    }
                    for check in results
                ],
                "summary": {
                    "total": len(results),
                    "met": sum(1 for check in results if check.result.met),
                    "high_confidence": sum(1 for check in results if check.result.confidence == "HIGH"),
                    "medium_confidence": sum(1 for check in results if check.result.confidence == "MEDIUM"),
                    "low_confidence": sum(1 for check in results if check.result.confidence == "LOW")
                }
            }
            
            # Store full results
            or_analysis.set_results(results_data)
            
            # Store metadata
            metadata = {
                'model': model,
                'app_num': app_num,
                'timestamp': datetime.utcnow().isoformat(),
                'analysis_type': 'openrouter_analysis'
            }
            or_analysis.set_metadata(metadata)
            
            db.session.commit()
            logger.info(f"Saved OpenRouter analysis results to database for {model}/app{app_num}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save OpenRouter results to database: {e}")
            try:
                from extensions import db
                db.session.rollback()
            except:
                pass
            return False

    def _save_results(self, model: str, app_num: int, results: List[RequirementCheck]):
        """DEPRECATED: Save analysis results to reports directory. Now saves to database."""
        logger.warning("File-based saving is deprecated. Saving to database instead.")
        self._save_results_to_database(model, app_num, results)
    
    def load_results(self, model: str, app_num: int) -> Optional[List[RequirementCheck]]:
        """Load saved analysis results."""
        try:
            reports_dir = self.base_path / "reports" / model / f"app{app_num}"
            results_file = reports_dir / "openrouter_analysis.json"
            
            if not results_file.exists():
                return None
            
            with open(results_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            results = []
            for item in data.get("requirements", []):
                result = RequirementResult(
                    met=item.get("met", False),
                    confidence=item.get("confidence", "LOW"),
                    explanation=item.get("explanation", ""),
                    code_evidence=item.get("code_evidence", ""),
                    recommendations=item.get("recommendations", ""),
                    error=item.get("error")
                )
                results.append(RequirementCheck(item.get("requirement", ""), result))
            
            return results
            
        except Exception as e:
            logger.error(f"Error loading results: {e}")
            return None
    
    def get_available_models(self) -> List[ModelInfo]:
        """Get list of available models."""
        return list(self.AVAILABLE_MODELS.values())
    
    def set_preferred_model(self, model_id: str) -> bool:
        """Set the preferred model."""
        if model_id in self.AVAILABLE_MODELS:
            self.preferred_model = model_id
            return True
        return False
    
    def get_requirements_for_app(self, app_num: int) -> Tuple[List[str], str]:
        """Get requirements for an app (alias for load_app_requirements)."""
        return self.load_app_requirements(app_num)
    
    def check_requirements(self, model: str, app_num: int, requirements: Optional[List[str]] = None, selected_model: Optional[str] = None) -> List[RequirementCheck]:
        """Check requirements against app code (enhanced analyze_app method)."""
        # Set preferred model if provided
        if selected_model:
            self.set_preferred_model(selected_model)
        
        # If no requirements provided, load them
        if not requirements:
            requirements, _ = self.load_app_requirements(app_num)
        
        # Check API availability
        api_available = self.is_api_available()
        logger.info(f"[DEBUG] check_requirements - API available: {api_available}")
        if not api_available:
            logger.error("OpenRouter API not available")
            return [RequirementCheck(req, RequirementResult(
                met=False,
                confidence="HIGH",
                explanation="OpenRouter API is not available. Check your API key and internet connection.",
                error="API unavailable"
            )) for req in requirements]
        
        # Collect code
        frontend_code, backend_code = self.collect_app_code(model, app_num)
        
        if not frontend_code and not backend_code:
            return [RequirementCheck(req, RequirementResult(
                met=False,
                confidence="HIGH",
                explanation="No code files found in the app directory",
                error="No code found"
            )) for req in requirements]
        
        results = []
        
        for i, req in enumerate(requirements):
            logger.info(f"  Analyzing requirement {i+1}/{len(requirements)}: {req[:50]}...")
            
            # Analyze frontend
            frontend_result = None
            if frontend_code:
                frontend_result = self.analyze_requirement(req, frontend_code, is_frontend=True)
            
            # Analyze backend
            backend_result = None
            if backend_code:
                backend_result = self.analyze_requirement(req, backend_code, is_frontend=False)
            
            # Combine results
            combined_result = self._combine_results(req, frontend_result, backend_result)
            results.append(RequirementCheck(req, combined_result))
            
            time.sleep(RATE_LIMIT_DELAY)  # Rate limiting
        
        # Save results
        self._save_results(model, app_num, results)
        
        met_count = sum(1 for check in results if check.result.met)
        logger.info(f"Analysis complete: {met_count}/{len(results)} requirements met")
        
        return results
    
    def check_server_status(self) -> bool:
        """Check if the OpenRouter server is available."""
        return self.is_api_available()

# Example usage
if __name__ == "__main__":
    try:
        analyzer = OpenRouterAnalyzer()
        
        # Test with a specific app
        if len(sys.argv) >= 3:
            model = sys.argv[1]
            app_num = int(sys.argv[2])
            results = analyzer.analyze_app(model, app_num)
            
            if results:
                print(f"\nAnalysis Results for {model}/app{app_num}:")
                for check in results:
                    status = "✅" if check.result.met else "❌"
                    print(f"{status} {check.requirement[:60]}... ({check.result.confidence})")
        else:
            print("Usage: python openrouter_analyzer.py <model> <app_num>")
            print("Example: python openrouter_analyzer.py mistralai_mistral-small-3.2-24b-instruct 1")
    except Exception as e:
        logger.error(f"Failed to run analyzer: {e}")
        sys.exit(1)

# Note: If you encounter SSL RecursionError when using this module alongside locust or similar
# libraries that monkey-patch SSL, the module will automatically disable SSL verification.
# This is a known issue with gevent/eventlet monkey-patching. See:
# https://github.com/gevent/gevent/issues/1016