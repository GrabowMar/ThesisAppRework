"""
JsonResultsManager - Unified Results Storage
==========================================

Standardized file handling for analysis results inspired by the attached files.
Provides consistent JSON storage and retrieval for all analysis tools.

Key Features:
- Consistent file naming and directory structure
- Atomic write operations with backup
- Standardized metadata handling
- Path resolution with fallback strategies
- Thread-safe operations
"""

import json
import logging
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

class JsonResultsManager:
    """Manages JSON results storage with consistent structure and error handling."""
    
    def __init__(self, base_path: Union[str, Path], module_name: str):
        """
        Initialize JsonResultsManager.
        
        Args:
            base_path: Base directory for results storage
            module_name: Module identifier (e.g., 'backend_security', 'performance')
        """
        self.base_path = Path(base_path).resolve()
        self.module_name = module_name.lower().replace('-', '_')
        self._lock = threading.Lock()
        
        # Ensure base directory exists
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"JsonResultsManager initialized: base={self.base_path}, module={self.module_name}")
    
    def save_results(
        self, 
        model: str, 
        app_num: int, 
        results: Any, 
        file_name: Optional[str] = None,
        **kwargs
    ) -> Path:
        """
        Save analysis results to JSON file with standardized structure.
        
        Args:
            model: Model slug/identifier
            app_num: Application number
            results: Results data to save
            file_name: Custom filename (optional)
            **kwargs: Additional metadata
            
        Returns:
            Path to saved file
        """
        with self._lock:
            try:
                # Normalize model name for filesystem
                model_safe = self._normalize_model_name(model)
                
                # Determine file path
                if file_name:
                    file_path = self._get_custom_file_path(model_safe, app_num, file_name)
                else:
                    file_path = self._get_default_file_path(model_safe, app_num)
                
                # Ensure directory exists
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Prepare data with metadata
                data_to_save = self._prepare_data_for_save(results, model, app_num, **kwargs)
                
                # Atomic write operation
                self._atomic_write(file_path, data_to_save)
                
                logger.info(f"Results saved successfully: {file_path}")
                return file_path
                
            except Exception as e:
                logger.error(f"Failed to save results for {model}/app{app_num}: {e}")
                raise
    
    def load_results(
        self, 
        model: str, 
        app_num: int, 
        file_name: Optional[str] = None,
        **kwargs
    ) -> Optional[Any]:
        """
        Load analysis results from JSON file.
        
        Args:
            model: Model slug/identifier
            app_num: Application number
            file_name: Custom filename (optional)
            **kwargs: Additional search parameters
            
        Returns:
            Loaded results data or None if not found
        """
        try:
            model_safe = self._normalize_model_name(model)
            
            # Try multiple file path strategies
            file_paths = self._get_candidate_file_paths(model_safe, app_num, file_name)
            
            for file_path in file_paths:
                if file_path.exists():
                    logger.debug(f"Loading results from: {file_path}")
                    return self._load_from_file(file_path)
            
            logger.debug(f"No results found for {model}/app{app_num}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to load results for {model}/app{app_num}: {e}")
            return None
    
    def list_available_results(self, model: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all available result files.
        
        Args:
            model: Optional model filter
            
        Returns:
            List of result file information
        """
        results = []
        try:
            pattern = f"*{self.module_name}*.json"
            if model:
                model_safe = self._normalize_model_name(model)
                search_path = self.base_path / model_safe
                if not search_path.exists():
                    return results
            else:
                search_path = self.base_path
            
            for file_path in search_path.rglob(pattern):
                try:
                    info = self._extract_file_info(file_path)
                    if info:
                        results.append(info)
                except Exception as e:
                    logger.warning(f"Failed to process file {file_path}: {e}")
            
            return sorted(results, key=lambda x: x.get('modified_at', ''), reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to list results: {e}")
            return results
    
    def delete_results(self, model: str, app_num: int, file_name: Optional[str] = None) -> bool:
        """
        Delete result files for given model and app.
        
        Args:
            model: Model slug/identifier
            app_num: Application number
            file_name: Specific file to delete (optional)
            
        Returns:
            True if deletion was successful
        """
        try:
            model_safe = self._normalize_model_name(model)
            file_paths = self._get_candidate_file_paths(model_safe, app_num, file_name)
            
            deleted_any = False
            for file_path in file_paths:
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted result file: {file_path}")
                    deleted_any = True
            
            return deleted_any
            
        except Exception as e:
            logger.error(f"Failed to delete results for {model}/app{app_num}: {e}")
            return False
    
    def get_result_path(self, model: str, app_num: int, file_name: Optional[str] = None) -> Path:
        """
        Get the expected path for result file without creating it.
        
        Args:
            model: Model slug/identifier
            app_num: Application number
            file_name: Custom filename (optional)
            
        Returns:
            Expected file path
        """
        model_safe = self._normalize_model_name(model)
        if file_name:
            return self._get_custom_file_path(model_safe, app_num, file_name)
        else:
            return self._get_default_file_path(model_safe, app_num)
    
    # Private methods
    
    def _normalize_model_name(self, model: str) -> str:
        """Normalize model name for filesystem safety."""
        return model.replace('/', '_').replace('\\', '_').replace(':', '_')
    
    def _get_default_file_path(self, model_safe: str, app_num: int) -> Path:
        """Get default file path for results."""
        filename = f".{self.module_name}_results.json"
        return self.base_path / model_safe / f"app{app_num}" / filename
    
    def _get_custom_file_path(self, model_safe: str, app_num: int, file_name: str) -> Path:
        """Get custom file path for results."""
        if not file_name.endswith('.json'):
            file_name += '.json'
        return self.base_path / model_safe / f"app{app_num}" / file_name
    
    def _get_candidate_file_paths(self, model_safe: str, app_num: int, file_name: Optional[str] = None) -> List[Path]:
        """Get list of candidate file paths to try."""
        paths = []
        
        if file_name:
            paths.append(self._get_custom_file_path(model_safe, app_num, file_name))
        else:
            # Try default naming patterns
            app_dir = self.base_path / model_safe / f"app{app_num}"
            patterns = [
                f".{self.module_name}_results.json",
                f"{self.module_name}_results.json",
                f"{self.module_name}.json",
                "results.json"
            ]
            
            for pattern in patterns:
                paths.append(app_dir / pattern)
        
        return paths
    
    def _prepare_data_for_save(self, results: Any, model: str, app_num: int, **kwargs) -> Dict[str, Any]:
        """Prepare data with metadata for saving."""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        data = {
            "metadata": {
                "module": self.module_name,
                "model": model,
                "app_number": app_num,
                "timestamp": timestamp,
                "version": "1.0",
                **kwargs
            },
            "results": results
        }
        
        return data
    
    def _atomic_write(self, file_path: Path, data: Dict[str, Any]) -> None:
        """Atomically write data to file."""
        # Create backup if file exists
        backup_path = None
        if file_path.exists():
            backup_path = file_path.with_suffix('.json.bak')
            shutil.copy2(file_path, backup_path)
        
        try:
            # Write to temporary file first
            with tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.json.tmp',
                dir=file_path.parent,
                delete=False,
                encoding='utf-8'
            ) as tmp_file:
                json.dump(data, tmp_file, indent=2, ensure_ascii=False)
                tmp_path = Path(tmp_file.name)
            
            # Atomic move
            shutil.move(str(tmp_path), str(file_path))
            
            # Remove backup if write was successful
            if backup_path and backup_path.exists():
                backup_path.unlink()
                
        except Exception as e:
            # Restore from backup if it exists
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, file_path)
                backup_path.unlink()
            raise e
    
    def _load_from_file(self, file_path: Path) -> Any:
        """Load data from JSON file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Return just results if it's our standardized format
        if isinstance(data, dict) and 'results' in data:
            return data['results']
        
        # Return raw data for other formats
        return data
    
    def _extract_file_info(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Extract information about a result file."""
        try:
            stat = file_path.stat()
            
            # Try to extract model/app info from path
            parts = file_path.parts
            model = None
            app_num = None
            
            # Look for model and app patterns in path
            for i, part in enumerate(parts):
                if part.startswith('app') and part[3:].isdigit():
                    app_num = int(part[3:])
                    if i > 0:
                        model = parts[i-1]
                    break
            
            return {
                'file_path': str(file_path),
                'file_name': file_path.name,
                'model': model,
                'app_number': app_num,
                'size_bytes': stat.st_size,
                'modified_at': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                'module': self.module_name
            }
            
        except Exception as e:
            logger.warning(f"Failed to extract info from {file_path}: {e}")
            return None