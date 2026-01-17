"""Generation V2 - Simplified Generation System
==============================================

A clean, minimal implementation of app generation using a 2-prompt strategy:
1. Generate backend (models, auth, routes)
2. Scan backend for API context
3. Generate frontend with backend context

Components:
- config.py: GenerationConfig dataclass
- scaffolding.py: ScaffoldingManager
- api_client.py: Clean OpenRouter API client
- code_generator.py: LLM query orchestration (2-prompt)
- backend_scanner.py: Extracts API info from generated backend
- code_merger.py: File writing and merging
- service.py: GenerationService orchestration
- job_executor.py: Unified job executor for pipelines
"""

from .config import GenerationConfig, GenerationResult
from .service import GenerationService, get_generation_service, generate_app
from .scaffolding import ScaffoldingManager, get_scaffolding_manager
from .code_generator import CodeGenerator, get_code_generator
from .code_merger import CodeMerger
from .backend_scanner import BackendScanner, get_backend_scanner, scan_backend_response
from .api_client import OpenRouterClient, get_api_client
from .job_executor import JobExecutor, get_job_executor, start_job_executor, stop_job_executor

# Re-export GenerationMode from constants for convenience
from app.constants import GenerationMode

__all__ = [
    # Config
    'GenerationConfig',
    'GenerationResult',
    'GenerationMode',
    # Service
    'GenerationService',
    'get_generation_service',
    'generate_app',
    # Components
    'ScaffoldingManager',
    'get_scaffolding_manager',
    'CodeGenerator',
    'get_code_generator',
    'CodeMerger',
    'BackendScanner',
    'get_backend_scanner',
    'scan_backend_response',
    'OpenRouterClient',
    'get_api_client',
    # Executor
    'JobExecutor',
    'get_job_executor',
    'start_job_executor',
    'stop_job_executor',
]
