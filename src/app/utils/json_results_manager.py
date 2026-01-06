"""Database-backed results storage with optional Redis caching."""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading
import zlib
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union, cast

try:  # pragma: no cover - optional dependency
    import redis  # type: ignore
except Exception:  # pragma: no cover - redis client not available
    redis = None

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ResultRecord:
    record_key: str
    model_slug: str
    model_safe: str
    app_number: int
    analysis_type: str
    created_at: str
    summary: Optional[Dict[str, Any]]
    size_bytes: int


class JsonResultsManager:
    """Persist analyzer results in SQLite with optional Redis caching."""

    def __init__(
        self,
        base_path: Union[str, Path],
        module_name: str,
        *,
        redis_url: Optional[str] = None,
        cache_ttl: Optional[int] = None,
    ) -> None:
        self.base_path = Path(base_path).resolve()
        self.module_name = module_name.lower().replace('-', '_')
        self.db_path = self.base_path / "analysis_results.db"
        self.cache_ttl = cache_ttl or int(os.getenv("RESULTS_CACHE_TTL", "3600"))
        self._lock = threading.Lock()
        self._tool_tables: Set[str] = set()

        self.base_path.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._initialize_database()

        self.redis_client = self._create_redis_client(redis_url)
        self._bootstrap_from_filesystem()
        logger.debug(
            "JsonResultsManager initialized (db=%s, module=%s, redis_cache=%s)",
            self.db_path,
            self.module_name,
            bool(self.redis_client),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def save_results(
        self,
        model: str,
        app_num: int,
        results: Any,
        file_name: Optional[str] = None,
        **kwargs: Any,
    ) -> Path:
        """Persist result payload to the database and cache."""
        analysis_type = (kwargs.get('analysis_type') or self.module_name or 'analysis').lower()
        record_key = self._build_record_key(model, app_num, analysis_type, file_name)
        created_at = datetime.now(timezone.utc).isoformat()
        model_safe = self._normalize_model_name(model)
        tool_entries: Dict[str, Dict[str, Any]] = {}
        if isinstance(results, dict):
            tool_entries = self._extract_tool_payloads(results)

        storage_payload = results
        if isinstance(results, dict) and tool_entries:
            storage_payload = deepcopy(results)
            tool_refs = self._strip_tool_segments(storage_payload, tool_entries)
            if tool_refs:
                refs_container = storage_payload.setdefault('_tool_refs', {})
                for tool_name, paths in tool_refs.items():
                    existing_paths = refs_container.setdefault(tool_name, [])
                    for ref_path in paths:
                        if ref_path not in existing_paths:
                            existing_paths.append(ref_path)

        payload_text = json.dumps(storage_payload, ensure_ascii=False, default=str)
        payload_blob = zlib.compress(payload_text.encode('utf-8'))
        size_bytes = len(payload_blob)
        summary_json = json.dumps(
            self._build_summary(results, analysis_type),
            ensure_ascii=False,
            default=str,
        )

        with self._lock:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO analysis_results (
                        record_key,
                        model_slug,
                        model_safe,
                        app_number,
                        analysis_type,
                        created_at,
                        summary,
                        size_bytes,
                        payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(record_key) DO UPDATE SET
                        payload=excluded.payload,
                        size_bytes=excluded.size_bytes,
                        created_at=excluded.created_at,
                        summary=excluded.summary,
                        analysis_type=excluded.analysis_type,
                        model_slug=excluded.model_slug,
                        model_safe=excluded.model_safe,
                        app_number=excluded.app_number
                    """,
                    (
                        record_key,
                        model,
                        model_safe,
                        int(app_num),
                        analysis_type,
                        created_at,
                        summary_json,
                        size_bytes,
                        payload_blob,
                    ),
                )

        cache_payload = storage_payload
        if isinstance(storage_payload, dict) and tool_entries:
            cache_payload = deepcopy(storage_payload)
            self._rehydrate_tool_payloads(cache_payload, tool_entries)
        cache_json = json.dumps(cache_payload, ensure_ascii=False, default=str)
        self._write_to_cache(record_key, cache_json)
        if tool_entries:
            self._persist_tool_payloads(
                record_key=record_key,
                model_slug=str(model),
                model_safe=model_safe,
                app_number=int(app_num),
                analysis_type=analysis_type,
                created_at=created_at,
                tool_entries=tool_entries,
            )
        return self.db_path

    def load_results(
        self,
        model: str,
        app_num: int,
        file_name: Optional[str] = None,
        **_: Any,
    ) -> Optional[Any]:
        """Load results payload from cache/DB, falling back gracefully."""
        record_key = self._resolve_record_key(model, app_num, file_name)
        if not record_key:
            logger.debug("JsonResultsManager.load_results: no record for %s app%s", model, app_num)
            return None

        cached = self._read_from_cache(record_key)
        if cached is not None:
            return cached

        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM analysis_results WHERE record_key=?",
                (record_key,),
            ).fetchone()

        if not row:
            logger.debug(
                "JsonResultsManager.load_results: cache miss and no DB row for %s",
                record_key,
            )
            return None

        payload = self._deserialize_payload(row['payload'])
        tool_entries = self._load_tool_entries(record_key)
        if isinstance(payload, dict) and tool_entries:
            self._rehydrate_tool_payloads(payload, tool_entries)
        cache_json = json.dumps(payload, ensure_ascii=False, default=str)
        self._write_to_cache(record_key, cache_json)
        return payload

    def list_available_results(self, model: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return metadata for stored analysis runs sorted by recency."""
        rows = self._fetch_records(model)
        results: List[Dict[str, Any]] = []
        for record in rows:
            entry: Dict[str, Any] = {
                'file_path': record.record_key,
                'file_name': record.record_key,
                'model': record.model_slug,
                'app_number': record.app_number,
                'analysis_type': record.analysis_type,
                'size_bytes': record.size_bytes,
                'modified_at': record.created_at,
                'module': self.module_name,
                'storage': 'database',
            }
            if record.summary is not None:
                entry['summary'] = record.summary
            results.append(entry)
        return results

    def delete_results(self, model: str, app_num: int, file_name: Optional[str] = None) -> bool:
        """Delete stored results and remove any cached entry."""
        with self._lock:
            if file_name:
                record_key = self._normalise_record_key(file_name)
                cursor = self._conn.execute(
                    "DELETE FROM analysis_results WHERE record_key=?",
                    (record_key,),
                )
                deleted = cursor.rowcount > 0
                if deleted:
                    self._evict_cache(record_key)
                return deleted

            cursor = self._conn.execute(
                "DELETE FROM analysis_results WHERE model_safe=? AND app_number=?",
                (self._normalize_model_name(model), int(app_num)),
            )
            removed = cursor.rowcount > 0
            if removed:
                logger.info(
                    "Deleted %s records for %s app%s",
                    cursor.rowcount,
                    model,
                    app_num,
                )
            return removed

    def get_result_path(self, model: str, app_num: int, file_name: Optional[str] = None) -> Path:
        """Return the backing SQLite database path for introspection."""
        return self.db_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _initialize_database(self) -> None:
        with self._lock:
            with self._conn:
                self._conn.execute("PRAGMA journal_mode=WAL;")
                self._conn.execute("PRAGMA foreign_keys=ON;")
                self._conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS analysis_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        record_key TEXT UNIQUE NOT NULL,
                        model_slug TEXT NOT NULL,
                        model_safe TEXT NOT NULL,
                        app_number INTEGER NOT NULL,
                        analysis_type TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        summary TEXT,
                        size_bytes INTEGER NOT NULL,
                        payload BLOB NOT NULL
                    )
                    """
                )
                self._conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_analysis_lookup
                    ON analysis_results(model_safe, app_number, datetime(created_at) DESC)
                    """
                )

    def _bootstrap_from_filesystem(self) -> None:
        must_import = os.getenv("RESULTS_BOOTSTRAP_JSON", "1").lower() not in {"0", "false", "no"}
        if not must_import:
            return
        try:
            existing = self._existing_record_keys()
            max_files = int(os.getenv("RESULTS_BOOTSTRAP_LIMIT", "500"))
            delete_after = os.getenv("RESULTS_DELETE_IMPORTED_JSON", "0").lower() in {"1", "true", "yes"}
            imported = 0
            legacy_files = sorted(self.base_path.glob("**/analysis/*.json"))
            for file_path in legacy_files:
                if file_path.suffix.lower() != ".json":
                    continue
                record_key = file_path.name
                if record_key in existing:
                    continue
                legacy_payload = self._extract_legacy_payload(file_path)
                if legacy_payload is None:
                    continue
                model_slug, app_number, analysis_type, payload = legacy_payload
                try:
                    self.save_results(
                        model_slug,
                        app_number,
                        payload,
                        file_name=record_key,
                        analysis_type=analysis_type,
                    )
                    existing.add(record_key)
                    imported += 1
                    if delete_after:
                        try:
                            file_path.unlink()
                        except Exception as cleanup_exc:  # pragma: no cover - best effort
                            logger.debug("Legacy file cleanup failed (%s): %s", file_path, cleanup_exc)
                    if max_files > 0 and imported >= max_files:
                        break
                except Exception as import_exc:
                    logger.debug("Skipping legacy import for %s: %s", file_path, import_exc)
                    continue
            if imported:
                logger.info("Imported %s legacy result files into SQLite store", imported)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Legacy results bootstrap skipped: %s", exc)

    def _existing_record_keys(self) -> Set[str]:
        with self._lock:
            rows = self._conn.execute("SELECT record_key FROM analysis_results").fetchall()
        return {row["record_key"] for row in rows}

    def _create_redis_client(self, redis_url: Optional[str]) -> Optional[Any]:
        if redis is None:
            return None
        url = redis_url or os.getenv('RESULTS_REDIS_URL') or os.getenv('REDIS_URL')
        if not url:
            return None
        try:
            client = cast(Any, redis.Redis.from_url(url, decode_responses=True, socket_timeout=0.5))
            client.ping()
            logger.debug("Redis cache enabled for results storage")
            return client
        except Exception as exc:  # pragma: no cover - cache optional
            logger.debug("Redis unavailable (%s), continuing without cache", exc)
            return None

    def _build_record_key(
        self,
        model: str,
        app_num: int,
        analysis_type: str,
        file_name: Optional[str],
    ) -> str:
        if file_name:
            return self._normalise_record_key(file_name)
        model_safe = self._normalize_model_name(model)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{model_safe}_app{app_num}_{analysis_type}_{timestamp}.json"

    def _extract_legacy_payload(self, file_path: Path) -> Optional[Tuple[str, int, str, Any]]:
        try:
            with open(file_path, "r", encoding="utf-8") as fh:
                raw_data = json.load(fh)
        except Exception as exc:
            logger.debug("Failed to parse legacy results %s: %s", file_path, exc)
            return None

        if isinstance(raw_data, dict) and "results" in raw_data:
            payload = raw_data["results"]
        else:
            payload = raw_data

        metadata = raw_data.get("metadata") if isinstance(raw_data, dict) else None
        model_slug = metadata.get("model_slug") if isinstance(metadata, dict) else None
        if not model_slug and isinstance(metadata, dict) and metadata.get("model"):
            model_slug = metadata.get("model")
        if not model_slug:
            model_slug = file_path.parents[2].name

        app_number: Optional[int]
        if isinstance(metadata, dict) and isinstance(metadata.get("app_number"), int):
            app_number = metadata["app_number"]
        else:
            app_number = self._extract_app_number(file_path)

        analysis_type: str
        if isinstance(metadata, dict) and isinstance(metadata.get("analysis_type"), str):
            analysis_type = metadata["analysis_type"].lower()
        else:
            analysis_type = self._infer_analysis_type(file_path.stem)

        if app_number is None:
            return None

        return str(model_slug), int(app_number), analysis_type, payload

    def _extract_app_number(self, file_path: Path) -> Optional[int]:
        for part in reversed(file_path.parts):
            if part.lower().startswith("app"):
                digits = "".join(ch for ch in part if ch.isdigit())
                if digits:
                    try:
                        return int(digits)
                    except ValueError:
                        return None
        return None

    def _infer_analysis_type(self, stem: str, default: str = "analysis") -> str:
        if "_task-" in stem:
            return "unified"
        parts = stem.split("_")
        for idx, part in enumerate(parts):
            if part.startswith("app") and idx + 1 < len(parts):
                candidate = parts[idx + 1]
                if candidate and not candidate.isdigit():
                    return candidate.replace("-", "_").lower()
        return default

    def _build_summary(self, results: Any, analysis_type: str) -> Dict[str, Any]:
        summary: Dict[str, Any] = {'analysis_type': analysis_type}
        if isinstance(results, dict):
            summary_section = results.get('summary')
            if isinstance(summary_section, dict):
                for key in (
                    'status',
                    'total_issues',
                    'total_findings',
                    'tools_executed',
                    'services_executed',
                    'severity_breakdown',
                ):
                    if key in summary_section:
                        summary[key] = summary_section[key]
            status = results.get('status')
            if isinstance(status, str):
                summary.setdefault('status', status)
            findings = results.get('findings')
            if isinstance(findings, list):
                summary.setdefault('total_findings', len(findings))
        return summary

    def _sanitize_tool_name(self, tool_name: str) -> str:
        name = (tool_name or '').strip().lower()
        if not name:
            name = 'unknown'
        name = re.sub(r'[^a-z0-9]+', '_', name)
        name = re.sub(r'_+', '_', name).strip('_')
        if not name:
            name = 'unknown'
        if name[0].isdigit():
            name = f"tool_{name}"
        return name

    def _tool_table_name(self, tool_name: str) -> str:
        sanitized = self._sanitize_tool_name(tool_name)
        return f"analysis_tool_{sanitized}"

    def _ensure_tool_table(self, tool_name: str) -> str:
        table_name = self._tool_table_name(tool_name)
        if table_name in self._tool_tables:
            return table_name
        create_sql = (
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_key TEXT UNIQUE NOT NULL,
                model_slug TEXT NOT NULL,
                model_safe TEXT NOT NULL,
                app_number INTEGER NOT NULL,
                analysis_type TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                summary TEXT,
                size_bytes INTEGER NOT NULL,
                payload BLOB NOT NULL
            )
            """
        )
        index_sql = (
            f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_lookup
            ON {table_name}(model_safe, app_number, datetime(created_at) DESC)
            """
        )
        with self._lock:
            with self._conn:
                self._conn.execute(create_sql)
                self._conn.execute(index_sql)
        self._tool_tables.add(table_name)
        return table_name

    def _extract_tool_payloads(self, payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        tool_entries: Dict[str, Dict[str, Any]] = {}

        def add_segment(tool_name: Any, source: str, data: Any) -> None:
            if not isinstance(tool_name, str) or not tool_name.strip():
                return
            key = tool_name.strip()
            entry = tool_entries.setdefault(key, {'tool_name': key, 'segments': []})
            segment = {'source': source, 'data': deepcopy(data)}
            if segment not in entry['segments']:
                entry['segments'].append(segment)

        def walk(obj: Any, path: str = '$') -> None:
            if isinstance(obj, dict):
                if isinstance(obj.get('tool_name'), str):
                    add_segment(obj['tool_name'], f"{path}.tool_name", obj)
                tools_section = obj.get('tools')
                if isinstance(tools_section, dict):
                    for tool_key, tool_value in tools_section.items():
                        if isinstance(tool_key, str):
                            add_segment(tool_key, f"{path}.tools.{tool_key}", tool_value)
                            walk(tool_value, f"{path}.tools.{tool_key}")
                metrics_section = obj.get('tool_metrics')
                if isinstance(metrics_section, dict):
                    for metric_tool, metric_value in metrics_section.items():
                        if isinstance(metric_tool, str):
                            add_segment(metric_tool, f"{path}.tool_metrics.{metric_tool}", metric_value)
                for key, value in obj.items():
                    if key in {'tools', 'tool_metrics'}:
                        continue
                    walk(value, f"{path}.{key}")
            elif isinstance(obj, list):
                for idx, item in enumerate(obj):
                    walk(item, f"{path}[{idx}]")

        walk(payload)
        return tool_entries

    def _build_tool_summary(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        segments = entry.get('segments') or []
        summary: Dict[str, Any] = {
            'tool_name': entry.get('tool_name'),
            'segments': len(segments),
            'sources': sorted(
                {segment.get('source') for segment in segments if isinstance(segment.get('source'), str)}
            ),
        }
        for segment in segments:
            data = segment.get('data')
            if isinstance(data, dict):
                if 'status' in data and 'status' not in summary:
                    summary['status'] = data['status']
                if 'total_issues' in data and 'total_issues' not in summary:
                    summary['total_issues'] = data['total_issues']
                if 'executed' in data and 'executed' not in summary:
                    summary['executed'] = data['executed']
                nested_summary = data.get('summary')
                if isinstance(nested_summary, dict):
                    if 'status' in nested_summary and 'status' not in summary:
                        summary['status'] = nested_summary['status']
                    if 'total_issues' in nested_summary and 'total_issues' not in summary:
                        summary['total_issues'] = nested_summary['total_issues']
        return summary

    def _persist_tool_payloads(
        self,
        *,
        record_key: str,
        model_slug: str,
        model_safe: str,
        app_number: int,
        analysis_type: str,
        created_at: str,
        tool_entries: Dict[str, Dict[str, Any]],
    ) -> None:
        for tool_name, entry in tool_entries.items():
            segments = entry.get('segments') or []
            if not segments:
                continue
            table_name = self._ensure_tool_table(tool_name)
            entry_payload = deepcopy(entry)
            entry_payload['metadata'] = {
                'record_key': record_key,
                'model_slug': model_slug,
                'model_safe': model_safe,
                'app_number': app_number,
                'analysis_type': analysis_type,
                'created_at': created_at,
            }
            payload_json = json.dumps(entry_payload, ensure_ascii=False, default=str)
            payload_blob = zlib.compress(payload_json.encode('utf-8'))
            size_bytes = len(payload_blob)
            summary_json = json.dumps(self._build_tool_summary(entry), ensure_ascii=False, default=str)

            with self._lock:
                with self._conn:
                    self._conn.execute(
                        f"""
                        INSERT INTO {table_name} (
                            record_key,
                            model_slug,
                            model_safe,
                            app_number,
                            analysis_type,
                            tool_name,
                            created_at,
                            summary,
                            size_bytes,
                            payload
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(record_key) DO UPDATE SET
                            model_slug=excluded.model_slug,
                            model_safe=excluded.model_safe,
                            app_number=excluded.app_number,
                            analysis_type=excluded.analysis_type,
                            tool_name=excluded.tool_name,
                            created_at=excluded.created_at,
                            summary=excluded.summary,
                            size_bytes=excluded.size_bytes,
                            payload=excluded.payload
                        """,
                        (
                            record_key,
                            model_slug,
                            model_safe,
                            app_number,
                            analysis_type,
                            tool_name,
                            created_at,
                            summary_json,
                            size_bytes,
                            payload_blob,
                        ),
                    )

    def _strip_tool_segments(
        self,
        payload: Dict[str, Any],
        tool_entries: Dict[str, Dict[str, Any]],
    ) -> Dict[str, List[str]]:
        removed: Dict[str, List[str]] = {}
        for tool_name, entry in tool_entries.items():
            for segment in entry.get('segments', []):
                source = segment.get('source')
                if not isinstance(source, str):
                    continue
                if 'tool_name' in source.split('.')[-1]:
                    continue
                if not any(token in source for token in ('.tools.', '.tool_metrics.', '.raw_outputs')):
                    continue
                components = self._parse_segment_path(source)
                placeholder = {'__tool_ref__': tool_name, '__source__': source}
                if self._apply_placeholder(payload, components, placeholder):
                    removed.setdefault(tool_name, []).append(source)
        return removed

    def _parse_segment_path(self, path: str) -> List[Union[str, int]]:
        trimmed = path.lstrip('$')
        if trimmed.startswith('.'):
            trimmed = trimmed[1:]
        components: List[Union[str, int]] = []
        token = ''
        idx = 0
        length = len(trimmed)
        while idx < length:
            char = trimmed[idx]
            if char == '.':
                if token:
                    components.append(token)
                    token = ''
                idx += 1
                continue
            if char == '[':
                if token:
                    components.append(token)
                    token = ''
                idx += 1
                index_token = ''
                while idx < length and trimmed[idx].isdigit():
                    index_token += trimmed[idx]
                    idx += 1
                if index_token:
                    components.append(int(index_token))
                while idx < length and trimmed[idx] != ']':
                    idx += 1
                idx += 1
                continue
            token += char
            idx += 1
        if token:
            components.append(token)
        return components

    def _apply_placeholder(
        self,
        payload: Any,
        components: List[Union[str, int]],
        placeholder: Any,
    ) -> bool:
        if not components:
            return False
        current = payload
        for idx, comp in enumerate(components):
            is_last = idx == len(components) - 1
            if is_last:
                if isinstance(comp, str) and isinstance(current, dict):
                    current[comp] = placeholder
                    return True
                if isinstance(comp, int) and isinstance(current, list):
                    if 0 <= comp < len(current):
                        current[comp] = placeholder
                        return True
                return False
            if isinstance(comp, str) and isinstance(current, dict):
                current = current.get(comp)
            elif isinstance(comp, int) and isinstance(current, list):
                if 0 <= comp < len(current):
                    current = current[comp]
                else:
                    return False
            else:
                return False
            if current is None:
                return False
        return False

    def _rehydrate_tool_payloads(
        self,
        payload: Dict[str, Any],
        tool_entries: Dict[str, Dict[str, Any]],
    ) -> None:
        for entry in tool_entries.values():
            for segment in entry.get('segments', []):
                source = segment.get('source')
                if not isinstance(source, str):
                    continue
                components = self._parse_segment_path(source)
                data = deepcopy(segment.get('data'))
                self._set_path_value(payload, components, data)

    def _set_path_value(
        self,
        payload: Any,
        components: List[Union[str, int]],
        value: Any,
    ) -> bool:
        if not components:
            return False
        current = payload
        for idx, comp in enumerate(components):
            is_last = idx == len(components) - 1
            next_comp = components[idx + 1] if not is_last else None
            if is_last:
                if isinstance(comp, str):
                    if isinstance(current, dict):
                        current[comp] = value
                        return True
                    return False
                if isinstance(comp, int):
                    if isinstance(current, list):
                        while len(current) <= comp:
                            current.append(None)
                        current[comp] = value
                        return True
                    return False
                return False
            if isinstance(comp, str):
                if not isinstance(current, dict):
                    return False
                if comp not in current or not isinstance(current[comp], (dict, list)):
                    current[comp] = {} if isinstance(next_comp, str) else []
                current = current[comp]
            elif isinstance(comp, int):
                if not isinstance(current, list):
                    return False
                while len(current) <= comp:
                    current.append({} if isinstance(next_comp, str) else [])
                if current[comp] is None:
                    current[comp] = {} if isinstance(next_comp, str) else []
                current = current[comp]
            else:
                return False
        return False

    # Allowed table names for security (prevent SQL injection)
    ALLOWED_TOOL_TABLES = {'analysis_tool_bandit', 'analysis_tool_semgrep', 'analysis_tool_eslint',
                           'analysis_tool_zap', 'analysis_tool_locust', 'analysis_tool_custom'}

    def _get_tool_tables(self) -> Set[str]:
        if not self._tool_tables:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'analysis_tool_%'"
                ).fetchall()
            for row in rows:
                table_name = row[0] if isinstance(row, tuple) else row['name']
                if isinstance(table_name, str):
                    self._tool_tables.add(table_name)
        return self._tool_tables

    def _validate_table_name(self, table_name: str) -> None:
        """Validate table name to prevent SQL injection."""
        # Allow dynamic tool tables that match the pattern, but validate format
        if not re.match(r'^analysis_tool_[a-zA-Z0-9_]+$', table_name):
            raise ValueError(f"Invalid table name format: {table_name}")

    def _load_tool_entries(self, record_key: str) -> Dict[str, Dict[str, Any]]:
        entries: Dict[str, Dict[str, Any]] = {}
        for table_name in self._get_tool_tables():
            # Validate table name before using in query
            self._validate_table_name(table_name)
            query = f"SELECT tool_name, payload FROM {table_name} WHERE record_key=?"
            with self._lock:
                row = self._conn.execute(query, (record_key,)).fetchone()
            if not row:
                continue
            tool_name = row['tool_name'] if isinstance(row, sqlite3.Row) else row[0]
            payload_blob = row['payload'] if isinstance(row, sqlite3.Row) else row[1]
            try:
                payload = self._deserialize_payload(payload_blob)
            except Exception:
                payload = None
            if isinstance(tool_name, str) and isinstance(payload, dict):
                entries[tool_name] = payload
        return entries

    # ------------------------------------------------------------------
    # Public Tool APIs
    # ------------------------------------------------------------------
    def load_tool_results(
        self,
        model: str,
        app_num: int,
        tool_name: str,
        file_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        record_key = self._resolve_record_key(model, app_num, file_name)
        if not record_key:
            return None
        table_name = self._tool_table_name(tool_name)
        if table_name not in self._get_tool_tables():
            return None
        with self._lock:
            row = self._conn.execute(
                f"SELECT payload FROM {table_name} WHERE record_key=?",
                (record_key,),
            ).fetchone()
        if not row:
            return None
        payload_blob = row['payload'] if isinstance(row, sqlite3.Row) else row[0]
        try:
            return self._deserialize_payload(payload_blob)
        except Exception:
            return None

    def list_tool_results(
        self,
        model: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        tables = self._get_tool_tables()
        if tool_name:
            target_table = self._tool_table_name(tool_name)
            tables = {t for t in tables if t == target_table}
        results: List[Dict[str, Any]] = []
        for table_name in tables:
            query = (
                f"SELECT record_key, tool_name, model_slug, model_safe, app_number, analysis_type, created_at, summary, size_bytes"
                f" FROM {table_name}"
            )
            params: List[Any] = []
            conditions: List[str] = []
            if model:
                conditions.append("model_safe=?")
                params.append(self._normalize_model_name(model))
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY datetime(created_at) DESC"
            with self._lock:
                rows = self._conn.execute(query, params).fetchall()
            for row in rows:
                row_map = dict(row)
                summary_raw = row_map.get('summary')
                if isinstance(summary_raw, str):
                    try:
                        row_map['summary'] = json.loads(summary_raw)
                    except json.JSONDecodeError:
                        row_map['summary'] = {'raw': summary_raw}
                row_map['table'] = table_name
                results.append(row_map)
        return results

    def _normalize_model_name(self, model: Optional[str]) -> str:
        if not model:
            return ''
        return model.replace('/', '_').replace('\\', '_').replace(':', '_')

    def _normalise_record_key(self, key: str) -> str:
        name = Path(key).name
        return name if name.endswith('.json') else f"{name}.json"

    def _cache_key(self, record_key: str) -> str:
        return f"analysis:result:{record_key}"

    def _resolve_record_key(self, model: str, app_num: int, file_name: Optional[str]) -> Optional[str]:
        if file_name:
            return self._normalise_record_key(file_name)
        row = self._conn.execute(
            """
            SELECT record_key FROM analysis_results
            WHERE model_safe=? AND app_number=?
            ORDER BY datetime(created_at) DESC
            LIMIT 1
            """,
            (self._normalize_model_name(model), int(app_num)),
        ).fetchone()
        return row['record_key'] if row else None

    def _fetch_records(self, model: Optional[str]) -> Iterable[ResultRecord]:
        params: List[Any] = []
        query = (
            "SELECT record_key, model_slug, model_safe, app_number, analysis_type, "
            "created_at, summary, size_bytes FROM analysis_results"
        )
        if model:
            query += " WHERE model_safe=?"
            params.append(self._normalize_model_name(model))
        query += " ORDER BY datetime(created_at) DESC"

        rows = self._conn.execute(query, params).fetchall()
        for row in rows:
            summary_obj: Optional[Dict[str, Any]] = None
            if row['summary']:
                try:
                    summary_obj = json.loads(row['summary'])
                except json.JSONDecodeError:
                    summary_obj = {'raw': row['summary']}
            yield ResultRecord(
                record_key=row['record_key'],
                model_slug=row['model_slug'],
                model_safe=row['model_safe'],
                app_number=row['app_number'],
                analysis_type=row['analysis_type'],
                created_at=row['created_at'],
                summary=summary_obj,
                size_bytes=row['size_bytes'],
            )

    def _deserialize_payload(self, payload_blob: Any) -> Any:
        data: bytes
        if isinstance(payload_blob, memoryview):
            data = payload_blob.tobytes()
        elif isinstance(payload_blob, bytes):
            data = payload_blob
        else:
            data = bytes(payload_blob)
        try:
            text = zlib.decompress(data).decode('utf-8')
        except zlib.error:
            text = data.decode('utf-8')
        return json.loads(text)

    def _read_from_cache(self, record_key: str) -> Optional[Any]:
        if not self.redis_client:
            return None
        try:
            cached = self.redis_client.get(self._cache_key(record_key))
            if cached is None:
                return None
            return json.loads(cached)
        except Exception:  # pragma: no cover - cache failures are non-fatal
            return None

    def _write_to_cache(self, record_key: str, payload_json: str) -> None:
        if not self.redis_client:
            return
        try:
            self.redis_client.setex(
                self._cache_key(record_key),
                self.cache_ttl,
                payload_json,
            )
        except Exception:  # pragma: no cover - best effort only
            logger.debug("Redis set failed for %s", record_key)

    def _evict_cache(self, record_key: str) -> None:
        if not self.redis_client:
            return
        try:
            self.redis_client.delete(self._cache_key(record_key))
        except Exception:  # pragma: no cover - best effort only
            logger.debug("Redis delete failed for %s", record_key)