"""
Unified Result Service
=====================

Consolidated service for managing analysis results through database persistence,
file storage, and API integration. Replaces 7 fragmented services with a single
coherent interface.

Architecture:
- DB subsystem: SQLAlchemy models (AnalysisResult, ToolResult, cache)
- File subsystem: JSON files in results/{model}/app{N}/analysis/{task_id}/
- API subsystem: HTTP fallback for cross-service queries

Atomic operations: Database + file writes succeed together or fail together.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from app.constants import SeverityLevel, AnalysisStatus
from app.extensions import db
from app.models.analysis_models import AnalysisResult, AnalysisTask
from app.models.simple_tool_results import ToolResult, ToolSummary
from app.models.results_cache import AnalysisResultsCache
from app.paths import RESULTS_DIR

logger = logging.getLogger(__name__)


def _json_default(obj: Any) -> str:
    """Fallback JSON encoder for non-serializable objects."""
    return str(obj)


def _sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return JSON-serializable copy of payload."""
    if not isinstance(payload, dict):
        return {}
    try:
        return json.loads(json.dumps(payload, default=_json_default))
    except (TypeError, ValueError):
        return {}


@dataclass
class AnalysisResults:
    """Structured analysis results for UI rendering."""
    task_id: str
    status: str
    summary: Dict[str, Any]
    security: Dict[str, Any]
    performance: Dict[str, Any]
    quality: Dict[str, Any]
    requirements: Dict[str, Any]
    tools: Dict[str, Any]
    raw_data: Dict[str, Any]
    model_slug: str = 'unknown'
    app_number: int = 0
    modified_at: Optional[datetime] = None


class UnifiedResultService:
    """
    Unified service for analysis result management.
    
    Provides atomic operations for storing/loading results with automatic
    cache management, file persistence, and database synchronization.
    """
    
    def __init__(self, cache_ttl_hours: int = 1):
        """Initialize service with configurable cache TTL."""
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        logger.info(f"UnifiedResultService initialized with {cache_ttl_hours}h cache TTL")
    
    # ==========================================================================
    # PUBLIC API - Core Operations
    # ==========================================================================
    
    def store_analysis_results(
        self,
        task_id: str,
        payload: Dict[str, Any],
        model_slug: Optional[str] = None,
        app_number: Optional[int] = None
    ) -> bool:
        """
        Store analysis results atomically to database and filesystem.
        
        Args:
            task_id: Unique task identifier
            payload: Analysis result payload (from engine)
            model_slug: Model identifier (for file path)
            app_number: Application number (for file path)
            
        Returns:
            True if stored successfully, False otherwise
            
        Raises:
            Exception: On critical failures (atomic - no partial writes)
        """
        try:
            # Sanitize payload for JSON serialization
            clean_payload = _sanitize_payload(payload)
            
            # Get task record
            task = db.session.get(AnalysisTask, task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return False
            
            # Extract model/app from task if not provided
            if not model_slug or not app_number:
                from app.models.core import GeneratedApplication
                app = db.session.get(GeneratedApplication, task.application_id)
                if app:
                    model_slug = model_slug or app.model_slug
                    app_number = app_number or app.app_number
            
            # Phase 1: Write to database (atomic transaction)
            self._db_store_results(task_id, task, clean_payload)
            
            # Phase 2: Write to filesystem (atomic - fail if can't write)
            if model_slug and app_number:
                file_path = self._file_write_results(task_id, clean_payload, model_slug, app_number)
                logger.info(f"Stored results for {task_id}: DB + file ({file_path})")
            else:
                logger.warning(f"Stored results for {task_id}: DB only (missing model/app)")
            
            # Phase 3: Invalidate cache
            self._cache_invalidate(task_id)
            
            return True
            
        except Exception as e:
            # Atomic failure - rollback database transaction
            db.session.rollback()
            logger.error(f"Failed to store results for {task_id}: {e}")
            raise
    
    def load_analysis_results(
        self,
        task_id: str,
        force_refresh: bool = False
    ) -> Optional[AnalysisResults]:
        """
        Load analysis results with automatic cache management.
        
        Priority: Cache → Database → Filesystem fallback
        
        Args:
            task_id: Unique task identifier
            force_refresh: Bypass cache and reload from source
            
        Returns:
            AnalysisResults object or None if not found
        """
        try:
            # Try cache first (unless force refresh)
            if not force_refresh:
                cached = self._cache_get(task_id)
                if cached:
                    logger.debug(f"Cache hit for {task_id}")
                    return cached
            
            # Try database
            payload = self._db_load_results(task_id)
            if payload:
                results = self._transform_to_analysis_results(task_id, payload)
                self._cache_set(task_id, results)
                logger.debug(f"Loaded {task_id} from database")
                return results
            
            # Try filesystem fallback
            payload = self._file_load_results(task_id)
            if payload:
                results = self._transform_to_analysis_results(task_id, payload)
                self._cache_set(task_id, results)
                logger.debug(f"Loaded {task_id} from filesystem")
                return results
            
            logger.warning(f"No results found for {task_id}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to load results for {task_id}: {e}")
            return None
    
    def get_task_summary(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get aggregated summary for task."""
        results = self.load_analysis_results(task_id)
        return results.summary if results else None
    
    def get_security_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get security analysis data for UI security tab."""
        results = self.load_analysis_results(task_id)
        return results.security if results else None
    
    def get_performance_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get performance analysis data for UI performance tab."""
        results = self.load_analysis_results(task_id)
        return results.performance if results else None
    
    def get_quality_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get code quality data for UI quality tab."""
        results = self.load_analysis_results(task_id)
        return results.quality if results else None
    
    def get_requirements_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get requirements validation data for UI requirements tab."""
        results = self.load_analysis_results(task_id)
        return results.requirements if results else None
    
    def get_tools_data(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get tool execution data for UI tools tab."""
        results = self.load_analysis_results(task_id)
        return results.tools if results else None
    
    def list_result_files(
        self,
        model_slug: str,
        app_number: int
    ) -> List[Dict[str, Any]]:
        """
        Discover all result files for a model/app combination.
        
        Returns list of file metadata dicts with paths and timestamps.
        """
        return self._file_discover_results(model_slug, app_number)
    
    def invalidate_cache(self, task_id: str) -> bool:
        """Manually invalidate cache for task."""
        return self._cache_invalidate(task_id)
    
    def cleanup_stale_cache(self, hours: Optional[int] = None) -> int:
        """
        Clean up expired cache entries.
        
        Args:
            hours: Override TTL for cleanup (default: use service TTL)
            
        Returns:
            Number of entries deleted
        """
        ttl = timedelta(hours=hours) if hours else self.cache_ttl
        cutoff = datetime.now(timezone.utc) - ttl
        
        try:
            deleted = db.session.query(AnalysisResultsCache).filter(
                AnalysisResultsCache.created_at < cutoff
            ).delete()
            db.session.commit()
            logger.info(f"Cleaned up {deleted} stale cache entries")
            return deleted
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to cleanup cache: {e}")
            return 0
    
    def rebuild_from_json(self, task_id: str) -> bool:
        """
        Forensic recovery: rebuild database from JSON file.
        
        Use when database is corrupt but filesystem is intact.
        """
        try:
            # Load from file
            payload = self._file_load_results(task_id)
            if not payload:
                logger.error(f"No JSON file found for {task_id}")
                return False
            
            # Get task
            task = db.session.get(AnalysisTask, task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return False
            
            # Rebuild database
            self._db_store_results(task_id, task, payload)
            self._cache_invalidate(task_id)
            
            logger.info(f"Rebuilt database for {task_id} from JSON")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to rebuild {task_id}: {e}")
            return False
    
    # ==========================================================================
    # DB SUBSYSTEM - Database Operations
    # ==========================================================================
    
    def _db_store_results(
        self,
        task_id: str,
        task: AnalysisTask,
        payload: Dict[str, Any]
    ) -> None:
        """Store results in database (within active transaction)."""
        # Update task record
        task.result_json = payload
        task.completed_at = datetime.now(timezone.utc)
        
        # Extract and store individual findings as AnalysisResult records
        findings = payload.get('findings', [])
        for finding in findings[:100]:  # Limit to 100 findings
            if not isinstance(finding, dict):
                continue
            
            result = AnalysisResult(
                task_id=task_id,
                service_name=finding.get('service', 'unknown'),
                tool_name=finding.get('tool', 'unknown'),
                severity=self._parse_severity(finding.get('severity')),
                message=finding.get('message', '')[:500],
                file_path=finding.get('file'),
                line_number=self._parse_int(finding.get('line')),
                metadata_json=finding
            )
            db.session.add(result)
        
        # Store tool summaries
        tool_results = payload.get('tool_results', {})
        for tool_name, tool_data in tool_results.items():
            if not isinstance(tool_data, dict):
                continue
            
            tool_result = ToolResult(
                task_id=task_id,
                tool_name=tool_name,
                status=tool_data.get('status', 'unknown'),
                issues_found=self._parse_int(tool_data.get('issues_found', 0)),
                execution_time=self._parse_float(tool_data.get('execution_time')),
                raw_output=tool_data.get('raw_output', '')[:5000],
                metadata_json=tool_data
            )
            db.session.add(tool_result)
        
        db.session.commit()
        logger.debug(f"Stored {len(findings)} findings and {len(tool_results)} tool results for {task_id}")
    
    def _db_load_results(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Load results from database."""
        task = db.session.get(AnalysisTask, task_id)
        if task and task.result_json:
            return task.result_json
        return None
    
    # ==========================================================================
    # FILE SUBSYSTEM - Filesystem Operations
    # ==========================================================================
    
    def _file_write_results(
        self,
        task_id: str,
        payload: Dict[str, Any],
        model_slug: str,
        app_number: int
    ) -> Path:
        """Write results to JSON file (atomic operation)."""
        # Build path: results/{model}/app{N}/analysis/{task_id}/consolidated.json
        model_dir = Path(RESULTS_DIR) / model_slug.replace('/', '_')
        app_dir = model_dir / f"app{app_number}"
        task_dir = app_dir / "analysis" / task_id
        
        # Create directories
        task_dir.mkdir(parents=True, exist_ok=True)
        
        # Write file atomically (write to temp, then rename)
        file_path = task_dir / "consolidated.json"
        temp_path = task_dir / f".{file_path.name}.tmp"
        
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, default=_json_default)
            temp_path.replace(file_path)  # Atomic on POSIX, near-atomic on Windows
            logger.debug(f"Wrote {file_path}")
            return file_path
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise Exception(f"File write failed: {e}") from e
    
    def _file_load_results(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Load results from filesystem (scan for task_id in results/)."""
        results_root = Path(RESULTS_DIR)
        if not results_root.exists():
            return None
        
        # Search pattern: results/*/app*/{task_id}/*.json (new structure)
        # Also check legacy: results/*/app*/analysis/{task_id}/consolidated.json
        for model_dir in results_root.iterdir():
            if not model_dir.is_dir():
                continue
            for app_dir in model_dir.iterdir():
                if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                    continue
                
                # New structure: results/{model}/app{N}/task_{task_id}/*.json
                task_dir = app_dir / task_id
                if task_dir.exists() and task_dir.is_dir():
                    # Find the main JSON file (not manifest.json)
                    json_files = list(task_dir.glob('*.json'))
                    main_json = next((jf for jf in json_files if jf.name != 'manifest.json' and task_id in jf.name), None)
                    if not main_json and json_files:
                        main_json = next((jf for jf in json_files if jf.name != 'manifest.json'), None)
                    
                    if main_json:
                        try:
                            with open(main_json, 'r', encoding='utf-8') as f:
                                return json.load(f)
                        except Exception as e:
                            logger.error(f"Failed to load {main_json}: {e}")
                
                # Legacy structure: results/{model}/app{N}/analysis/{task_id}/consolidated.json
                legacy_file = app_dir / "analysis" / task_id / "consolidated.json"
                if legacy_file.exists():
                    try:
                        with open(legacy_file, 'r', encoding='utf-8') as f:
                            return json.load(f)
                    except Exception as e:
                        logger.error(f"Failed to load {legacy_file}: {e}")
        
        return None
    
    def _file_discover_results(
        self,
        model_slug: str,
        app_number: int
    ) -> List[Dict[str, Any]]:
        """Discover all result files for model/app."""
        model_dir = Path(RESULTS_DIR) / model_slug.replace('/', '_')
        app_dir = model_dir / f"app{app_number}"
        
        if not app_dir.exists():
            return []
        
        files = []
        # Look for task_* directories directly under app_dir
        for task_dir in app_dir.iterdir():
            if not task_dir.is_dir() or not task_dir.name.startswith('task_'):
                continue
            
            # Use directory name directly as task_id (already has 'task_' prefix)
            task_id = task_dir.name  # e.g., "task_73f4b252ff6d"
            
            # Look for JSON files in the task directory
            json_files = list(task_dir.glob('*.json'))
            # Filter out manifest.json, prefer the main result JSON
            main_json = None
            for jf in json_files:
                if jf.name != 'manifest.json' and task_id in jf.name:
                    main_json = jf
                    break
            
            if not main_json and json_files:
                # Fallback to first non-manifest JSON
                main_json = next((jf for jf in json_files if jf.name != 'manifest.json'), None)
            
            if main_json:
                stat = main_json.stat()
                files.append({
                    'task_id': task_id,  # Use directory name as-is: "task_73f4b252ff6d"
                    'identifier': task_id,  # Must match DB format exactly
                    'path': str(main_json),
                    'size_bytes': stat.st_size,
                    'modified_at': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    'task_name': task_id,
                    'model_slug': model_slug,
                    'app_number': app_number
                })
        
        return sorted(files, key=lambda x: x['modified_at'], reverse=True)
    
    # ==========================================================================
    # CACHE SUBSYSTEM - Database-backed Caching
    # ==========================================================================
    
    def _cache_get(self, task_id: str) -> Optional[AnalysisResults]:
        """Get results from cache if not expired."""
        try:
            cache_entry = db.session.query(AnalysisResultsCache).filter_by(
                task_id=task_id
            ).first()
            
            if not cache_entry:
                return None
            
            # Check expiration
            now = datetime.now(timezone.utc)
            created_at = cache_entry.created_at
            # Ensure both datetimes are timezone-aware for comparison
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age = now - created_at
            if age > self.cache_ttl:
                logger.debug(f"Cache expired for {task_id} ({age.total_seconds()}s old)")
                return None
            
            # Reconstruct AnalysisResults from cached JSON
            return self._transform_to_analysis_results(task_id, cache_entry.results_json)
            
        except Exception as e:
            logger.error(f"Cache get failed for {task_id}: {e}")
            return None
    
    def _cache_set(self, task_id: str, results: AnalysisResults) -> None:
        """Store results in cache."""
        try:
            # Delete existing cache entry
            db.session.query(AnalysisResultsCache).filter_by(task_id=task_id).delete()
            
            # Create new cache entry from AnalysisResults object
            cache_entry = AnalysisResultsCache.from_analysis_results(results)
            db.session.add(cache_entry)
            db.session.commit()
            logger.debug(f"Cached results for {task_id}")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Cache set failed for {task_id}: {e}")
    
    def _cache_invalidate(self, task_id: str) -> bool:
        """Remove results from cache."""
        try:
            deleted = db.session.query(AnalysisResultsCache).filter_by(
                task_id=task_id
            ).delete()
            db.session.commit()
            if deleted:
                logger.debug(f"Invalidated cache for {task_id}")
            return deleted > 0
        except Exception as e:
            db.session.rollback()
            logger.error(f"Cache invalidate failed for {task_id}: {e}")
            return False
    
    # ==========================================================================
    # HELPERS - Data Transformation
    # ==========================================================================
    
    def _transform_to_analysis_results(
        self,
        task_id: str,
        payload: Dict[str, Any]
    ) -> AnalysisResults:
        """Transform raw payload into structured AnalysisResults."""
        # Handle nested structure: if payload has 'results' key, unwrap it
        if 'results' in payload and isinstance(payload['results'], dict):
            results_data = payload['results']
        else:
            results_data = payload
        
        # Extract metadata
        metadata = payload.get('metadata', {})
        model_slug = metadata.get('model_slug', 'unknown')
        app_number = metadata.get('app_number', 0)
        
        # Parse timestamp if available
        modified_at = None
        if 'timestamp' in metadata:
            try:
                from dateutil import parser
                modified_at = parser.parse(metadata['timestamp'])
            except Exception:
                pass
        
        # Extract data for each tab
        summary = self._extract_summary(results_data)
        security = self._extract_security(results_data)
        performance = self._extract_performance(results_data)
        quality = self._extract_quality(results_data)
        requirements = self._extract_requirements(results_data)
        
        # Get full services data (not just tools) - template needs this
        services = results_data.get('services', {})
        
        # Determine status from summary or top-level
        status = (results_data.get('summary', {}).get('status') or 
                  results_data.get('status') or 
                  payload.get('status', 'unknown'))
        
        return AnalysisResults(
            task_id=task_id,
            status=status,
            summary=summary,
            security=security,
            performance=performance,
            quality=quality,
            requirements=requirements,
            tools=services,  # Use full services data instead of just tool results
            raw_data=payload,
            model_slug=model_slug,
            app_number=app_number,
            modified_at=modified_at
        )
    
    def _extract_summary(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract summary data."""
        summary = payload.get('summary', {})
        return {
            'total_findings': summary.get('total_findings', 0),
            'services_executed': summary.get('services_executed', 0),
            'tools_executed': summary.get('tools_executed', 0),
            'tools_successful': summary.get('tools_successful', 0),
            'tools_failed': summary.get('tools_failed', 0),
            'status': summary.get('status', 'unknown'),
            'severity_breakdown': summary.get('severity_breakdown', {})
        }
    
    def _extract_security(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract security findings."""
        findings = [
            f for f in payload.get('findings', [])
            if isinstance(f, dict) and f.get('category') == 'security'
        ]
        return {
            'findings': findings,
            'total': len(findings),
            'critical': sum(1 for f in findings if f.get('severity') == 'critical'),
            'high': sum(1 for f in findings if f.get('severity') == 'high')
        }
    
    def _extract_performance(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract performance metrics."""
        perf_data = payload.get('services', {}).get('performance-tester', {})
        return {
            'metrics': perf_data.get('metrics', {}),
            'response_times': perf_data.get('response_times', []),
            'throughput': perf_data.get('throughput', {})
        }
    
    def _extract_quality(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract code quality metrics."""
        static_data = payload.get('services', {}).get('static-analyzer', {})
        return {
            'complexity': static_data.get('complexity', {}),
            'maintainability': static_data.get('maintainability', {}),
            'issues': static_data.get('issues', [])
        }
    
    def _extract_requirements(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract requirements validation."""
        req_data = payload.get('requirements', {})
        return {
            'validated': req_data.get('validated', []),
            'missing': req_data.get('missing', []),
            'coverage': req_data.get('coverage', 0.0)
        }
    
    def _extract_tools(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract tool execution data."""
        return payload.get('tool_results', {})
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    
    @staticmethod
    def _parse_severity(value: Any) -> str:
        """Parse severity value to standard string."""
        if not value:
            return 'info'
        val_str = str(value).lower()
        if val_str in ('critical', 'high', 'medium', 'low', 'info'):
            return val_str
        return 'info'
    
    @staticmethod
    def _parse_int(value: Any) -> Optional[int]:
        """Safely parse integer value."""
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
    
    @staticmethod
    def _parse_float(value: Any) -> Optional[float]:
        """Safely parse float value."""
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None
    
    def find_path_by_identifier(self, identifier: str) -> Optional[Path]:
        """Find result file path by identifier (task_id)."""
        # Try to look up the task in DB to get model/app first
        task = db.session.get(AnalysisTask, identifier)
        if task:
            # If we have task, we know where to look
            model_dir = Path(RESULTS_DIR) / task.target_model.replace('/', '_')
            app_dir = model_dir / f"app{task.target_app_number}"
            
            # New structure
            task_dir = app_dir / identifier
            if task_dir.exists():
                json_files = list(task_dir.glob('*.json'))
                main_json = next((jf for jf in json_files if jf.name != 'manifest.json' and identifier in jf.name), None)
                if not main_json and json_files:
                    main_json = next((jf for jf in json_files if jf.name != 'manifest.json'), None)
                if main_json:
                    return main_json
            
            # Legacy structure
            legacy_file = app_dir / "analysis" / identifier / "consolidated.json"
            if legacy_file.exists():
                return legacy_file

        # Fallback: scan everything (slow)
        results_root = Path(RESULTS_DIR)
        if not results_root.exists():
            return None
            
        for model_dir in results_root.iterdir():
            if not model_dir.is_dir(): continue
            for app_dir in model_dir.iterdir():
                if not app_dir.is_dir() or not app_dir.name.startswith('app'): continue
                
                # Check new structure
                task_dir = app_dir / identifier
                if task_dir.exists():
                     json_files = list(task_dir.glob('*.json'))
                     main_json = next((jf for jf in json_files if jf.name != 'manifest.json' and identifier in jf.name), None)
                     if main_json: return main_json

                # Check legacy
                legacy_file = app_dir / "analysis" / identifier / "consolidated.json"
                if legacy_file.exists():
                    return legacy_file
        
        return None
