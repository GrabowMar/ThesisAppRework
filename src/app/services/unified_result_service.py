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
from app.utils.analysis_utils import resolve_task_directory, extract_issues_from_sarif

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
    
    # Cache compatibility properties
    @property
    def analysis_type(self) -> str:
        return self.raw_data.get('analysis_type', 'unified')
        
    @property
    def timestamp(self) -> Optional[datetime]:
        return self.modified_at
        
    @property
    def duration(self) -> float:
        return float(self.summary.get('duration', 0.0))
        
    @property
    def total_findings(self) -> int:
        return int(self.summary.get('total_findings', 0))
        
    @property
    def tools_executed(self) -> List[str]:
        # Extract tool names from tools dict
        return list(self.tools.keys())
        
    @property
    def tools_failed(self) -> List[str]:
        # Identify failed tools
        failed = []
        for name, data in self.tools.items():
            if isinstance(data, dict) and data.get('status') == 'failed':
                failed.append(name)
        return failed


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
            
            # Hydrate findings from SARIF if needed (before DB store)
            self._hydrate_tools_with_sarif(clean_payload, task_id)
            
            # Get task record by task_id field (not primary key)
            task = AnalysisTask.query.filter_by(task_id=task_id).first()
            if not task:
                logger.error(f"Task {task_id} not found")
                return False
            
            # Extract model/app from task if not provided
            if not model_slug or not app_number:
                model_slug = model_slug or task.target_model
                app_number = app_number or task.target_app_number
            
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
            
            # Get task by task_id field (not primary key)
            task = AnalysisTask.query.filter_by(task_id=task_id).first()
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
        task.set_result_summary(payload)
        task.completed_at = datetime.now(timezone.utc)
        
        # Update summary fields for list view performance
        summary = payload.get('summary', {})
        task.issues_found = summary.get('total_findings', len(payload.get('findings', [])))
        task.set_severity_breakdown(summary.get('severity_breakdown', {}))
        
        # Extract and store individual findings as AnalysisResult records
        findings = payload.get('findings', [])
        for finding in findings[:100]:  # Limit to 100 findings
            if not isinstance(finding, dict):
                continue
            
            result = AnalysisResult(
                task_id=task_id,
                tool_name=finding.get('tool', 'unknown'),
                title=finding.get('message', 'No title')[:500],
                description=finding.get('message', ''),
                severity=self._parse_severity(finding.get('severity')),
                file_path=finding.get('file'),
                line_number=self._parse_int(finding.get('line')),
                result_type='finding'
            )
            
            # Enhanced mapping
            result.tool_version = finding.get('tool_version')
            result.confidence = finding.get('confidence')
            result.code_snippet = finding.get('code_snippet')
            result.category = finding.get('category')
            result.rule_id = finding.get('rule_id')
            
            # Optional scoring
            if finding.get('impact_score'):
                result.impact_score = self._parse_float(finding.get('impact_score'))
            result.business_impact = finding.get('business_impact')
            result.remediation_effort = finding.get('remediation_effort')
            
            # JSON helpers
            if finding.get('tags'):
                result.set_tags(finding.get('tags'))
            if finding.get('recommendations'):
                result.set_recommendations(finding.get('recommendations'))
            
            result.set_structured_data(finding)
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
                total_issues=self._parse_int(tool_data.get('issues_found', 0)),
                duration_seconds=self._parse_float(tool_data.get('execution_time')),
            )
            tool_result.set_raw_data(tool_data)
            db.session.add(tool_result)
        
        db.session.commit()
        logger.debug(f"Stored {len(findings)} findings and {len(tool_results)} tool results for {task_id}")
    
    def _db_load_results(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Load results from database."""
        # Use filter_by for task_id string field (not primary key)
        task = AnalysisTask.query.filter_by(task_id=task_id).first()
        if task:
            return task.get_result_summary()
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
        # Build path: results/{model}/app{N}/task_{task_id}/
        model_dir = Path(RESULTS_DIR) / model_slug.replace('/', '_')
        app_dir = model_dir / f"app{app_number}"
        task_dir = app_dir / f"task_{task_id}"
        
        # Create directories
        task_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Extract SARIF files to reduce main JSON size
        # This modifies the payload in-place to reference the extracted files
        self._extract_sarif_to_files(payload, task_dir)
        
        # 2. Write per-service snapshots
        self._write_service_snapshots(payload, task_dir)
        
        # 3. Write manifest
        try:
            manifest = {
                "task_id": task_id,
                "model_slug": model_slug,
                "app_number": app_number,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "files": [f.name for f in task_dir.glob("*") if f.is_file()]
            }
            with open(task_dir / "manifest.json", "w") as f:
                json.dump(manifest, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write manifest for {task_id}: {e}")

        # 4. Write main consolidated file
        file_path = task_dir / f"{model_slug}_app{app_number}_task_{task_id}.json"
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

    def _extract_sarif_to_files(self, payload: Dict[str, Any], task_dir: Path) -> None:
        """
        Extract SARIF data from payload to separate files to reduce JSON size.
        Modifies payload in-place to replace SARIF data with file references.
        """
        sarif_dir = task_dir / "sarif"
        sarif_dir.mkdir(exist_ok=True)
        
        services = payload.get('services', {})
        for service_name, service_data in services.items():
            if not isinstance(service_data, dict):
                continue
                
            # Check for tools with SARIF
            analysis = service_data.get('analysis', {})
            
            # Handle static analyzer structure (grouped by language)
            if service_name in ['static-analyzer', 'static']:
                results = analysis.get('results', {})
                for lang, lang_tools in results.items():
                    if isinstance(lang_tools, dict):
                        for tool_name, tool_data in lang_tools.items():
                            self._process_sarif_extraction(tool_name, tool_data, sarif_dir)
            
            # Handle flat structure (other analyzers)
            else:
                # Check 'results'
                results = analysis.get('results', {})
                if isinstance(results, dict):
                    for tool_name, tool_data in results.items():
                        self._process_sarif_extraction(tool_name, tool_data, sarif_dir)
                
                # Check 'tool_results'
                tool_results = analysis.get('tool_results', {})
                if isinstance(tool_results, dict):
                    for tool_name, tool_data in tool_results.items():
                        self._process_sarif_extraction(tool_name, tool_data, sarif_dir)

    def _process_sarif_extraction(self, tool_name: str, tool_data: Dict[str, Any], sarif_dir: Path) -> None:
        """Helper to extract SARIF from a single tool entry."""
        if not isinstance(tool_data, dict):
            return
            
        sarif_data = tool_data.get('sarif')
        if sarif_data and isinstance(sarif_data, dict):
            # Generate filename
            safe_tool = tool_name.replace('/', '_').replace('\\', '_')
            filename = f"{safe_tool}.sarif.json"
            file_path = sarif_dir / filename
            
            try:
                # Write SARIF to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(sarif_data, f, indent=2)
                
                # Replace in payload with reference
                tool_data['sarif'] = {
                    "sarif_file": f"sarif/{filename}",
                    "extracted_at": datetime.now(timezone.utc).isoformat()
                }
                logger.debug(f"Extracted SARIF for {tool_name} to {filename}")
            except Exception as e:
                logger.warning(f"Failed to extract SARIF for {tool_name}: {e}")

    def _write_service_snapshots(self, payload: Dict[str, Any], task_dir: Path) -> None:
        """Write individual service results to separate files for debugging."""
        services_dir = task_dir / "services"
        services_dir.mkdir(exist_ok=True)
        
        services = payload.get('services', {})
        for service_name, service_data in services.items():
            try:
                safe_name = service_name.replace('/', '_')
                file_path = services_dir / f"{safe_name}.json"
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(service_data, f, indent=2, default=_json_default)
            except Exception as e:
                logger.warning(f"Failed to write snapshot for {service_name}: {e}")
    
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
            raw_data = cache_entry.get_raw_data()
            if not raw_data:
                return None
            return self._transform_to_analysis_results(task_id, raw_data)
            
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
        model_slug = metadata.get('model_slug')
        app_number = metadata.get('app_number')
        
        # Fallback: look up from database task if not in metadata
        if not model_slug or not app_number:
            task = AnalysisTask.query.filter_by(task_id=task_id).first()
            if task:
                model_slug = model_slug or task.target_model
                app_number = app_number or task.target_app_number
        
        # Final fallback to defaults
        model_slug = model_slug or 'unknown'
        app_number = app_number if app_number is not None else 0
        
        # Parse timestamp if available
        modified_at = None
        if 'timestamp' in metadata:
            try:
                from dateutil import parser
                modified_at = parser.parse(metadata['timestamp'])
            except Exception:
                pass
        
        # Extract data for each tab
        # Hydrate tools with SARIF data if needed
        self._hydrate_tools_with_sarif(results_data, task_id)

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
        # Try to look up the task in DB to get model/app first (by task_id field, not primary key)
        task = AnalysisTask.query.filter_by(task_id=identifier).first()
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

    def get_sarif_files(self, task_id: str) -> List[Path]:
        """
        Discover all SARIF files for a task.
        
        Args:
            task_id: Unique task identifier
            
        Returns:
            List of Path objects for found SARIF files
        """
        try:
            # Load main result to resolve directory
            result = self.load_analysis_results(task_id)
            if not result:
                logger.warning(f"Cannot list SARIF: Task {task_id} not found")
                return []
            
            result_data = result.raw_data
            task_dir = resolve_task_directory(result_data, task_id)
            
            if not task_dir or not task_dir.exists():
                logger.warning(f"Cannot list SARIF: Result directory not found for task {task_id}")
                return []
            
            sarif_files = []
            
            # Look for SARIF files in sarif/ subdirectory
            sarif_dir = task_dir / "sarif"
            if sarif_dir.exists():
                sarif_files.extend(list(sarif_dir.glob("*.sarif.json")))
            
            # Also check for legacy consolidated file
            legacy_file = task_dir / "consolidated.sarif.json"
            if legacy_file.exists():
                sarif_files.append(legacy_file)
                
            return sarif_files
            
        except Exception as e:
            logger.error(f"Error listing SARIF files for task {task_id}: {e}")
            return []

    def load_sarif_file(self, task_id: str, sarif_path: str) -> Optional[Dict[str, Any]]:
        """
        Load a SARIF file associated with a task.
        
        Args:
            task_id: Unique task identifier
            sarif_path: Relative path to the SARIF file (e.g., "sarif/tool.sarif.json")
            
        Returns:
            Dict containing SARIF data or None if not found
        """
        try:
            # Load main result to resolve directory
            result = self.load_analysis_results(task_id)
            if not result:
                logger.warning(f"Cannot load SARIF: Task {task_id} not found")
                return None
            
            result_data = result.raw_data
            task_dir = resolve_task_directory(result_data, task_id)
            
            if not task_dir:
                logger.warning(f"Cannot load SARIF: Could not resolve directory for task {task_id}")
                return None
            
            task_root = task_dir.resolve()
            sarif_path_obj = Path(sarif_path)
            
            # Handle both absolute (if inside task dir) and relative paths
            if sarif_path_obj.is_absolute():
                sarif_full_path = sarif_path_obj.resolve()
            else:
                sarif_full_path = (task_root / sarif_path_obj).resolve()
            
            # Security check: ensure path is within task directory
            try:
                sarif_full_path.relative_to(task_root)
            except ValueError:
                logger.warning(f"Security violation: SARIF path {sarif_path} escapes task directory {task_root}")
                return None
            
            if not sarif_full_path.exists():
                logger.warning(f"SARIF file not found: {sarif_full_path}")
                return None
            
            with open(sarif_full_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Error loading SARIF file {sarif_path} for task {task_id}: {e}")
            return None
    
    def _hydrate_tools_with_sarif(self, results_data: Dict[str, Any], task_id: str) -> None:
        """
        Hydrate tool results with issues from SARIF files if issues are missing.
        Modifies results_data in-place.
        """
        services = results_data.get('services', {})
        if not services:
            return

        # Iterate through services and tools
        for service_name, service_data in services.items():
            if not isinstance(service_data, dict):
                continue
            
            analysis = service_data.get('analysis', {})
            # Handle different structures (static vs others)
            tools_to_check = []
            
            if service_name == 'static-analyzer' or service_name == 'static':
                # Static analysis usually has language grouping
                results = analysis.get('results', {})
                for lang, lang_tools in results.items():
                    if isinstance(lang_tools, dict):
                        for tool_name, tool_data in lang_tools.items():
                            tools_to_check.append((tool_name, tool_data))
            else:
                # Others usually have flat results or tool_results
                # Check 'results' first
                results = analysis.get('results', {})
                if isinstance(results, dict):
                    for tool_name, tool_data in results.items():
                        tools_to_check.append((tool_name, tool_data))
                
                # Check 'tool_results'
                tool_results = analysis.get('tool_results', {})
                if isinstance(tool_results, dict):
                    for tool_name, tool_data in tool_results.items():
                        tools_to_check.append((tool_name, tool_data))

            for tool_name, tool_data in tools_to_check:
                if not isinstance(tool_data, dict):
                    continue
                
                # Check if issues are missing but SARIF is present
                issues = tool_data.get('issues', [])
                sarif_ref = tool_data.get('sarif')
                
                if (not issues or len(issues) == 0) and sarif_ref:
                    try:
                        sarif_file = None
                        if isinstance(sarif_ref, dict):
                            sarif_file = sarif_ref.get('sarif_file') or sarif_ref.get('path') or sarif_ref.get('file')
                        elif isinstance(sarif_ref, str):
                            sarif_file = sarif_ref
                        
                        if sarif_file:
                            # Resolve SARIF path
                            task_dir = resolve_task_directory(results_data, task_id)
                            if task_dir:
                                task_root = task_dir.resolve()
                                sarif_path_obj = Path(sarif_file)
                                sarif_full_path = sarif_path_obj if sarif_path_obj.is_absolute() else (task_root / sarif_path_obj).resolve()
                                
                                if sarif_full_path.exists():
                                    with open(sarif_full_path, 'r', encoding='utf-8') as f:
                                        sarif_data = json.load(f)
                                    
                                    extracted_issues = extract_issues_from_sarif(sarif_data)
                                    if extracted_issues:
                                        tool_data['issues'] = extracted_issues
                                        tool_data['total_issues'] = len(extracted_issues)
                                        # Also update top-level findings if this is a security tool
                                        # This is tricky because 'findings' is a separate list.
                                        # We might need to append to it.
                                        if service_name in ['static-analyzer', 'static', 'dynamic-analyzer', 'dynamic']:
                                            current_findings = results_data.get('findings', [])
                                            # Add tool info to findings
                                            for issue in extracted_issues:
                                                issue['service'] = service_name
                                                issue['tool'] = tool_name
                                                issue['category'] = 'security' # Assumption
                                                current_findings.append(issue)
                                            results_data['findings'] = current_findings
                                            
                                            # Update summary counts
                                            summary = results_data.get('summary', {})
                                            summary['total_findings'] = len(current_findings)
                                            
                                            # Update severity breakdown
                                            breakdown = summary.get('severity_breakdown', {})
                                            for issue in extracted_issues:
                                                sev = issue.get('severity', 'info').lower()
                                                breakdown[sev] = breakdown.get(sev, 0) + 1
                                            summary['severity_breakdown'] = breakdown
                                            
                                            logger.info(f"Hydrated {len(extracted_issues)} issues for {tool_name} from SARIF")
                    except Exception as e:
                        logger.warning(f"Failed to hydrate SARIF for {tool_name}: {e}")
