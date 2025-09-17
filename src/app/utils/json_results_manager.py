"""
JsonResultsManager - Unified Results Storage
==========================================

Standardized file handling for analysis results.

Key Features:
- Consistent file naming and directory structure
- Atomic write operations with backup
- Standardized metadata handling
- Backward-compatible loading of legacy paths
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
        self.base_path = Path(base_path).resolve()
        self.module_name = module_name.lower().replace('-', '_')
        self._lock = threading.Lock()
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"JsonResultsManager initialized: base={self.base_path}, module={self.module_name}")

    def save_results(
        self,
        model: str,
        app_num: int,
        results: Any,
        file_name: Optional[str] = None,
        **kwargs,
    ) -> Path:
        with self._lock:
            # Normalize model name
            model_safe = self._normalize_model_name(model)
            # Determine directory name: prefer explicit analysis_type (static/dynamic/performance/ai)
            dir_name = (kwargs.get('analysis_type') or self.module_name or 'analysis').lower()
            # Determine path
            actual_file = file_name if file_name else f".{self.module_name}_results.json"
            if actual_file and not actual_file.endswith('.json'):
                actual_file += '.json'
            file_path = self._compose_path(model_safe, app_num, dir_name, actual_file)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            # Prepare data
            data_to_save = self._prepare_data_for_save(results, model, app_num, **kwargs)
            # Atomic write
            self._atomic_write(file_path, data_to_save)
            logger.info(f"Results saved successfully: {file_path}")
            return file_path

    def load_results(
        self,
        model: str,
        app_num: int,
        file_name: Optional[str] = None,
        **kwargs,
    ) -> Optional[Any]:
        try:
            model_safe = self._normalize_model_name(model)
            for file_path in self._get_candidate_file_paths(model_safe, app_num, file_name):
                if file_path.exists():
                    logger.debug(f"Loading results from: {file_path}")
                    return self._load_from_file(file_path)
            logger.debug(f"No results found for {model}/app{app_num}")
            return None
        except Exception as e:
            logger.error(f"Failed to load results for {model}/app{app_num}: {e}")
            return None

    def list_available_results(self, model: Optional[str] = None) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        try:
            search_path = self.base_path / self._normalize_model_name(model) if model else self.base_path
            if not search_path.exists():
                return results
            # Prefer standardized module subfolders
            for file_path in search_path.rglob(f"**/{self.module_name}/*.json"):
                info = self._extract_file_info(file_path)
                if info:
                    results.append(info)
            # Also include legacy patterns under app folders
            legacy_globs = [
                f"**/app*/.{self.module_name}_results.json",
                f"**/app*/{self.module_name}_results.json",
                f"**/app*/{self.module_name}.json",
            ]
            for glob in legacy_globs:
                for file_path in search_path.rglob(glob):
                    info = self._extract_file_info(file_path)
                    if info:
                        results.append(info)
            # Sort newest first
            return sorted(results, key=lambda x: x.get('modified_at', ''), reverse=True)
        except Exception as e:
            logger.error(f"Failed to list results: {e}")
            return results

    def delete_results(self, model: str, app_num: int, file_name: Optional[str] = None) -> bool:
        try:
            model_safe = self._normalize_model_name(model)
            deleted_any = False
            for file_path in self._get_candidate_file_paths(model_safe, app_num, file_name):
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"Deleted result file: {file_path}")
                    deleted_any = True
            return deleted_any
        except Exception as e:
            logger.error(f"Failed to delete results for {model}/app{app_num}: {e}")
            return False

    def get_result_path(self, model: str, app_num: int, file_name: Optional[str] = None) -> Path:
        model_safe = self._normalize_model_name(model)
        dir_name = self.module_name or 'analysis'
        actual_file = file_name if file_name else f".{self.module_name}_results.json"
        if actual_file and not actual_file.endswith('.json'):
            actual_file += '.json'
        return self._compose_path(model_safe, app_num, dir_name, actual_file)

    # ------------------------- Private helpers -------------------------

    def _normalize_model_name(self, model: Optional[str]) -> str:
        if not model:
            return ''
        return model.replace('/', '_').replace('\\', '_').replace(':', '_')

    def _compose_path(self, model_safe: str, app_num: int, dir_name: str, file_name: str) -> Path:
        return self.base_path / model_safe / f"app{app_num}" / dir_name / file_name

    def _get_candidate_file_paths(self, model_safe: str, app_num: int, file_name: Optional[str]) -> List[Path]:
        candidates: List[Path] = []
        app_dir = self.base_path / model_safe / f"app{app_num}"
        # Consider any analyzer-type subfolder (static/dynamic/performance/ai) plus our module_name
        subdirs = set([self.module_name, 'static', 'dynamic', 'performance', 'ai', 'security', 'analysis'])
        if file_name:
            for d in subdirs:
                candidates.append(app_dir / d / file_name)
        else:
            # Standard filenames under each known subdir
            filenames = [
                f".{self.module_name}_results.json",
                f"{self.module_name}_results.json",
                f"{self.module_name}.json",
            ]
            for d in subdirs:
                for fn in filenames:
                    candidates.append(app_dir / d / fn)
            # Legacy locations
            candidates.extend([
                app_dir / f".{self.module_name}_results.json",
                app_dir / f"{self.module_name}_results.json",
                app_dir / f"{self.module_name}.json",
                app_dir / "results.json",
            ])
        return candidates

    def _prepare_data_for_save(self, results: Any, model: str, app_num: int, **kwargs) -> Dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        return {
            "metadata": {
                "module": self.module_name,
                "model": model,
                "app_number": app_num,
                "timestamp": timestamp,
                "version": "1.0",
                **kwargs,
            },
            "results": results,
        }

    def _atomic_write(self, file_path: Path, data: Dict[str, Any]) -> None:
        backup_path: Optional[Path] = None
        if file_path.exists():
            backup_path = file_path.with_suffix('.json.bak')
            shutil.copy2(file_path, backup_path)
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.json.tmp', dir=file_path.parent, delete=False, encoding='utf-8'
            ) as tmp_file:
                json.dump(data, tmp_file, indent=2, ensure_ascii=False)
                tmp_path = Path(tmp_file.name)
            shutil.move(str(tmp_path), str(file_path))
            if backup_path and backup_path.exists():
                backup_path.unlink()
        except Exception:
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, file_path)
                backup_path.unlink()
            raise

    def _load_from_file(self, file_path: Path) -> Any:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data['results'] if isinstance(data, dict) and 'results' in data else data

    def _extract_file_info(self, file_path: Path) -> Optional[Dict[str, Any]]:
        try:
            stat = file_path.stat()
            parts = file_path.parts
            model = None
            app_num = None
            for i, part in enumerate(parts):
                if part.startswith('app') and part[3:].isdigit():
                    app_num = int(part[3:])
                    if i > 0:
                        model = parts[i - 1]
                    break
            return {
                'file_path': str(file_path),
                'file_name': file_path.name,
                'model': model,
                'app_number': app_num,
                'size_bytes': stat.st_size,
                'modified_at': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                'module': self.module_name,
            }
        except Exception as e:
            logger.warning(f"Failed to extract info from {file_path}: {e}")
            return None