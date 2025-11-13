"""
Base Report Generator

Abstract base class for all report generators. Defines the interface and common functionality.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class BaseReportGenerator(ABC):
    """Base class for all report generators."""
    
    def __init__(self, config: Dict[str, Any], reports_dir: Path):
        """
        Initialize the generator.
        
        Args:
            config: Report-specific configuration dictionary
            reports_dir: Base directory for saving report files
        """
        self.config = config
        self.reports_dir = reports_dir
        self.data: Optional[Dict[str, Any]] = None
    
    @abstractmethod
    def collect_data(self) -> Dict[str, Any]:
        """
        Collect and aggregate data for the report.
        
        This method should:
        1. Query the database for task metadata and filtering
        2. Load detailed results from consolidated JSON files
        3. Aggregate and compute statistics
        4. Return a structured data dictionary
        
        Returns:
            Dictionary containing all data needed for rendering
        """
        pass
    
    @abstractmethod
    def get_template_name(self) -> str:
        """
        Get the Jinja2 template filename for this report type.
        
        Returns:
            Template filename (e.g., 'model_analysis.html')
        """
        pass
    
    def validate_config(self) -> None:
        """
        Validate the configuration for this report type.
        
        Raises:
            ValidationError: If configuration is invalid
        """
        # Default implementation - override in subclasses for specific validation
        pass
    
    def generate_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a summary of the report data for quick display.
        
        Args:
            data: The full report data
            
        Returns:
            Dictionary with summary statistics
        """
        # Default implementation - override in subclasses for specific summaries
        return {
            'total_items': len(data.get('items', [])),
            'generated_at': data.get('timestamp')
        }
