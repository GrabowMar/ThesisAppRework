"""
Analysis Container Utilities
============================

Utility functions for the analysis container.
"""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any

def setup_logging() -> logging.Logger:
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('/app/logs/analysis.log')
        ]
    )
    
    # Create logs directory
    Path('/app/logs').mkdir(exist_ok=True)
    
    return logging.getLogger('analysis_container')


def create_workspace(job_id: str) -> Path:
    """Create a temporary workspace for analysis."""
    workspace_path = Path(f"/temp/workspace_{job_id}")
    workspace_path.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories
    (workspace_path / "input").mkdir(exist_ok=True)
    (workspace_path / "output").mkdir(exist_ok=True)
    (workspace_path / "temp").mkdir(exist_ok=True)
    
    return workspace_path


def cleanup_workspace(job_id: str) -> None:
    """Clean up workspace after analysis."""
    workspace_path = Path(f"/temp/workspace_{job_id}")
    if workspace_path.exists():
        shutil.rmtree(workspace_path)


def save_results(job_id: str, results: Dict[str, Any]) -> Path:
    """Save analysis results to file."""
    import json
    
    results_dir = Path(f"/results/{job_id}")
    results_dir.mkdir(parents=True, exist_ok=True)
    
    results_file = results_dir / "analysis_results.json"
    
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    return results_file


def load_tool_config(tool_name: str) -> Dict[str, Any]:
    """Load configuration for a specific tool."""
    config_file = Path(f"/app/config/{tool_name}.json")
    
    if config_file.exists():
        import json
        with open(config_file, 'r') as f:
            return json.load(f)
    
    # Return default configuration
    return {
        "enabled": True,
        "timeout": 300,
        "max_memory": "1G",
        "parallel": False
    }
