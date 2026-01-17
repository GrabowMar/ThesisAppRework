"""Generation Configuration
===========================

Simple dataclass configuration for app generation.
Single 2-prompt mode: backend → frontend with API context scanning.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from pathlib import Path


@dataclass
class GenerationConfig:
    """Configuration for a single app generation.
    
    Attributes:
        model_slug: Normalized model identifier (e.g., 'anthropic_claude-3-5-haiku')
        template_slug: Template identifier (e.g., 'crud_todo_list')
        app_num: App number (1, 2, 3, ...)
        max_tokens: Maximum tokens per API call
        temperature: Sampling temperature
        timeout: API call timeout in seconds
        save_artifacts: Whether to save request/response JSON files
    """
    model_slug: str
    template_slug: str
    app_num: int
    max_tokens: int = 32000
    temperature: float = 0.3
    timeout: int = 300
    save_artifacts: bool = True
    
    # Optional port overrides
    backend_port: Optional[int] = None
    frontend_port: Optional[int] = None
    
    # Metadata
    extra: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def safe_model_slug(self) -> str:
        """Get filesystem-safe model slug."""
        import re
        return re.sub(r'[^\w\-.]', '_', self.model_slug)
    
    def get_app_dir(self, base_dir: Path) -> Path:
        """Get the app directory path."""
        return base_dir / self.safe_model_slug / f"app{self.app_num}"


@dataclass
class GenerationResult:
    """Result from app generation.
    
    Attributes:
        success: Whether generation completed successfully
        app_dir: Path to generated app directory
        errors: List of error messages (empty if success)
        metrics: Generation metrics (timing, token usage, etc.)
        artifacts: Paths to saved request/response files
    """
    success: bool
    app_dir: Optional[Path] = None
    errors: list = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, Path] = field(default_factory=dict)
    
    @property
    def error_message(self) -> str:
        """Get combined error message."""
        return "; ".join(self.errors) if self.errors else ""
    
    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'success': self.success,
            'app_dir': str(self.app_dir) if self.app_dir else None,
            'errors': self.errors,
            'metrics': self.metrics,
            'artifacts': {k: str(v) for k, v in self.artifacts.items()},
        }
