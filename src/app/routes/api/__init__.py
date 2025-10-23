"""
API Routes Package
==================

Refactored API routes organized by domain:
- core: Basic health, status, and core endpoints
- models: Model management and metadata
- system: System monitoring and status
- dashboard: Dashboard stats and fragments
- applications: Application lifecycle and container management
- analysis: Analysis operations and statistics
- generation: Scaffolding-first AI code generation (ACTIVE)
- tasks_realtime: Real-time task updates
- tool_registry: Tool registry and profiles
- container_tools: Container management tools

REMOVED:
- sample_generation: OLD deprecated system (3700+ lines)
- simple_generation: Merged into generation.py
- app_scaffolding: Unused legacy route (no frontend calls)
- template_store: Unused template CRUD (no frontend calls)

Legacy api.py has been broken down into focused modules to reduce bloat
and improve maintainability.
"""

from .api import api_bp
from .core import core_bp
from .models import models_bp
from .system import system_bp
from .dashboard import dashboard_bp
from .applications import applications_bp
from .analysis import analysis_bp
from .generation import gen_bp
from .tasks_realtime import tasks_rt_bp
from .tool_registry import tool_registry_bp
from .container_tools import container_tools_bp
from .export import export_bp

__all__ = [
    'api_bp',
    'core_bp',
    'models_bp', 
    'system_bp',
    'dashboard_bp',
    'applications_bp',
    'analysis_bp',
    'gen_bp',
    'tasks_rt_bp',
    'tool_registry_bp',
    'container_tools_bp',
    'export_bp'
]