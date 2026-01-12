"""Generation V2 - Simplified Generation System
==============================================

A clean, minimal implementation of app generation focused on:
1. Simplicity - No complex retry loops, trust modern LLMs
2. Single circuit breaker - One implementation used everywhere  
3. Direct execution - No queue workers, no complex orchestration
4. Database as truth - No application-level coordination layers

Components:
- config.py: GenerationConfig dataclass
- scaffolding.py: ScaffoldingManager (~100 lines)
- api_client.py: Clean OpenRouter API client (~150 lines)
- code_generator.py: LLM query orchestration (~200 lines)
- code_merger.py: AST-based model merging (~150 lines)
- service.py: GenerationService orchestration (~200 lines)
- job_executor.py: Unified job executor for pipelines (~300 lines)
"""

from .config import GenerationConfig, GenerationMode, GenerationResult
from .service import GenerationService, get_generation_service, generate_app
from .scaffolding import ScaffoldingManager, get_scaffolding_manager
from .code_generator import CodeGenerator, get_code_generator
from .code_merger import CodeMerger
from .api_client import OpenRouterClient, get_api_client
from .job_executor import JobExecutor, get_job_executor, start_job_executor, stop_job_executor

__all__ = [
    # Config
    'GenerationConfig',
    'GenerationMode',
    'GenerationResult',
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
    'OpenRouterClient',
    'get_api_client',
    # Executor
    'JobExecutor',
    'get_job_executor',
    'start_job_executor',
    'stop_job_executor',
]
