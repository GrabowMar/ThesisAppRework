"""Generation statistics aggregation utilities.

This module provides rich read operations over the generated artifacts stored
on disk. The intent is to complement the database-driven statistics service by
capturing everything that exists in ``generated/`` (payload snapshots,
metadata manifests, Markdown transcripts, etc.).

The functions concentrate on *reading* data and should not mutate files.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, cast

from app.paths import (
    GENERATED_APPS_DIR,
    GENERATED_MARKDOWN_DIR,
    GENERATED_RAW_API_PAYLOADS_DIR,
    GENERATED_RAW_API_RESPONSES_DIR,
    GENERATED_INDICES_DIR,
    GENERATED_ROOT,
)

try:
    from app.constants import AnalysisStatus
    from app.models import GeneratedApplication, GeneratedCodeResult
except Exception:  # pragma: no cover - optional during early init/tests
    AnalysisStatus = None  # type: ignore
    GeneratedApplication = None  # type: ignore
    GeneratedCodeResult = None  # type: ignore

DATE_PATTERN = re.compile(r"^\d{8}T\d{6}")
SUMMARY_PATH = GENERATED_INDICES_DIR / "generation_stats_summary.json"
RESULTS_ROOT = GENERATED_ROOT.parent / "results"
ANALYSIS_DIR_NAME = "analysis"


@dataclass(slots=True)
class ArtifactPaths:
    """Container for the canonical artifact locations for a single run."""

    payload_path: Optional[Path]
    response_path: Optional[Path]
    metadata_path: Optional[Path]
    markdown_path: Optional[Path]


@dataclass(slots=True)
class GenerationRecord:
    """Normalized representation of a generation run."""

    run_id: str
    model: str
    app_num: Optional[int]
    app_name: Optional[str]
    component: Optional[str]
    timestamp: Optional[datetime]
    success: Optional[bool]
    duration: Optional[float]
    attempts: Optional[int]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    finish_reason: Optional[str]
    error_message: Optional[str]
    request_headers: Dict[str, Any]
    request_payload: Dict[str, Any]
    response_status: Optional[int]
    response_headers: Dict[str, Any]
    response_summary: Dict[str, Any]
    files: ArtifactPaths
    # Code metrics
    total_lines: Optional[int] = None
    total_files: Optional[int] = None
    files_by_language: Optional[Dict[str, int]] = None
    lines_by_language: Optional[Dict[str, int]] = None
    # Analysis aggregates
    analysis_findings: Optional[Dict[str, Any]] = None
    security_issues: Optional[int] = None
    performance_score: Optional[float] = None
    requirements_met: Optional[int] = None
    requirements_total: Optional[int] = None
    # OpenRouter metadata
    generation_id: Optional[str] = None
    model_used: Optional[str] = None
    created_timestamp: Optional[int] = None
    native_tokens_prompt: Optional[int] = None
    native_tokens_completion: Optional[int] = None
    generation_time_ms: Optional[int] = None
    provider_name: Optional[str] = None
    prompt_cost: Optional[float] = None
    completion_cost: Optional[float] = None
    estimated_cost: Optional[float] = None


def _normalize_timestamp(value: Optional[datetime]) -> Optional[datetime]:
    if not value:
        return None
    if value.tzinfo:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _iter_metadata_files() -> Iterable[Path]:
    runs_root = GENERATED_INDICES_DIR / "runs"
    if not runs_root.exists():
        return []
    return runs_root.rglob("*_metadata.json")


def _resolve_markdown_path(model: str, app_num: Optional[int]) -> Optional[Path]:
    if app_num is None:
        return None
    safe_model = re.sub(r"[^\w\-_.]", "_", model)
    safe_app = f"app_{app_num}" if isinstance(app_num, int) else str(app_num)
    candidates = list((GENERATED_MARKDOWN_DIR / safe_model).glob(f"*{safe_app}*.md"))
    return candidates[0] if candidates else None


def _safe_model_dir(model: str) -> str:
    return re.sub(r"[^\w\-_.]", "_", model or "unknown_model")


def _app_label(app_num: Optional[int]) -> Optional[str]:
    if app_num is None:
        return None
    return f"app{app_num}"


def _latest_file(directory: Path, pattern: str = "*.json") -> Optional[Path]:
    if not directory.exists():
        return None
    candidates = [p for p in directory.glob(pattern) if p.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _load_json(path: Path) -> Optional[Dict[str, object]]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _parse_timestamp(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return _normalize_timestamp(parsed)
    except ValueError:
        if DATE_PATTERN.match(raw):
            try:
                parsed = datetime.strptime(raw, "%Y%m%dT%H%M%S")
                return _normalize_timestamp(parsed)
            except ValueError:
                return None
        return None


def _find_raw_artifacts(metadata: Dict[str, object]) -> ArtifactPaths:
    payload_path = Path(str(metadata.get("payload_path"))) if metadata.get("payload_path") else None
    response_path = Path(str(metadata.get("response_path"))) if metadata.get("response_path") else None
    metadata_path = Path(str(metadata.get("metadata_path"))) if metadata.get("metadata_path") else None
    markdown_hint = metadata.get("markdown_path")
    markdown_path: Optional[Path] = Path(markdown_hint) if isinstance(markdown_hint, str) else None

    if markdown_path and not markdown_path.exists():
        markdown_path = None

    if metadata_path and not metadata_path.exists():
        metadata_path = None

    return ArtifactPaths(
        payload_path=payload_path if payload_path and payload_path.exists() else None,
        response_path=response_path if response_path and response_path.exists() else None,
        metadata_path=metadata_path if metadata_path and metadata_path.exists() else None,
        markdown_path=markdown_path,
    )


def _guess_artifact_paths(model: str, app_num: Optional[int]) -> ArtifactPaths:
    safe_model = _safe_model_dir(model)
    app_label = _app_label(app_num)

    if not app_label:
        return ArtifactPaths(None, None, None, None)

    payload_dir = GENERATED_RAW_API_PAYLOADS_DIR / safe_model / app_label
    response_dir = GENERATED_RAW_API_RESPONSES_DIR / safe_model / app_label
    metadata_dir = GENERATED_INDICES_DIR / "runs" / safe_model / app_label
    markdown_dir = GENERATED_MARKDOWN_DIR / safe_model

    payload_path = _latest_file(payload_dir)
    response_path = _latest_file(response_dir)
    metadata_path = _latest_file(metadata_dir)
    markdown_path = _latest_file(markdown_dir, pattern=f"*{app_label}*.md")

    if not metadata_path:
        analysis_dir = RESULTS_ROOT / safe_model / app_label / ANALYSIS_DIR_NAME
        metadata_path = _latest_file(analysis_dir)

    return ArtifactPaths(payload_path, response_path, metadata_path, markdown_path)


def _compute_code_metrics_from_blocks(blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute code metrics from extracted blocks metadata."""
    total_lines = 0
    total_files = len(blocks)
    lines_by_lang: Dict[str, int] = {}
    files_by_lang: Dict[str, int] = {}
    
    for block in blocks:
        lang = (block.get("language") or "unknown").lower()
        line_count = block.get("line_count", 0)
        if isinstance(line_count, int) and line_count > 0:
            total_lines += line_count
            lines_by_lang[lang] = lines_by_lang.get(lang, 0) + line_count
            files_by_lang[lang] = files_by_lang.get(lang, 0) + 1
    
    return {
        "total_lines": total_lines,
        "total_files": total_files,
        "lines_by_language": lines_by_lang,
        "files_by_language": files_by_lang,
    }


def _load_analysis_results(model: str, app_num: Optional[int]) -> Dict[str, Any]:
    """Load and aggregate analysis results from results directory."""
    if not app_num:
        return {}
    
    safe_model = _safe_model_dir(model)
    app_label = _app_label(app_num)
    if not app_label:
        return {}
    
    analysis_dir = RESULTS_ROOT / safe_model / app_label / ANALYSIS_DIR_NAME
    if not analysis_dir.exists():
        return {}
    
    aggregates: Dict[str, Any] = {
        "security_issues": 0,
        "performance_score": None,
        "requirements_met": 0,
        "requirements_total": 0,
        "static_findings": 0,
        "dynamic_findings": 0,
        "ai_findings": 0,
        "analysis_types": [],
        "tools_used": set(),
    }
    
    for result_file in analysis_dir.glob("*.json"):
        try:
            data = _load_json(result_file)
            if not data:
                continue
            
            # Determine analysis type from filename or metadata
            filename = result_file.name.lower()
            if "static" in filename:
                aggregates["analysis_types"].append("static")
                results_raw = data.get("results", {})
                results = results_raw if isinstance(results_raw, dict) else {}
                summary_raw = results.get("summary", {}) if results else {}
                summary = summary_raw if isinstance(summary_raw, dict) else {}
                aggregates["static_findings"] = summary.get("total_findings", 0) if isinstance(summary, dict) else 0
                severity = summary.get("severity_breakdown", {}) if isinstance(summary, dict) else {}
                aggregates["security_issues"] += severity.get("high", 0) if isinstance(severity, dict) else 0
                tools = summary.get("tools_used", [])
                if isinstance(tools, list):
                    aggregates["tools_used"].update(tools)
            
            elif "dynamic" in filename:
                aggregates["analysis_types"].append("dynamic")
                results_raw = data.get("results", {})
                results = results_raw if isinstance(results_raw, dict) else {}
                summary_raw = results.get("summary", {}) if results else {}
                summary = summary_raw if isinstance(summary_raw, dict) else {}
                aggregates["dynamic_findings"] = summary.get("total_findings", 0) if isinstance(summary, dict) else 0
            
            elif "performance" in filename:
                aggregates["analysis_types"].append("performance")
                results_raw = data.get("results", {})
                results = results_raw if isinstance(results_raw, dict) else {}
                summary_raw = results.get("summary", {}) if results else {}
                summary = summary_raw if isinstance(summary_raw, dict) else {}
                score = summary.get("performance_score") if isinstance(summary, dict) else None
                if isinstance(score, (int, float)):
                    aggregates["performance_score"] = float(score)
            
            elif "_ai_" in filename or filename.endswith("_ai.json"):
                aggregates["analysis_types"].append("ai")
                # Path: results → raw_outputs → analysis → results → requirement_checks
                results_1_obj = data.get("results", {})
                results_1 = results_1_obj if isinstance(results_1_obj, dict) else {}
                raw_outputs_obj = results_1.get("raw_outputs", {}) if results_1 else {}
                raw_outputs = raw_outputs_obj if isinstance(raw_outputs_obj, dict) else {}
                analysis_obj = raw_outputs.get("analysis", {}) if raw_outputs else {}
                analysis = analysis_obj if isinstance(analysis_obj, dict) else {}
                results_2_obj = analysis.get("results", {}) if analysis else {}
                results_2 = results_2_obj if isinstance(results_2_obj, dict) else {}
                req_checks = results_2.get("requirement_checks", []) if results_2 else []
                if isinstance(req_checks, list):
                    aggregates["requirements_total"] = len(req_checks)
                    aggregates["requirements_met"] = sum(
                        1 for check in req_checks 
                        if isinstance(check, dict) and check.get("result", {}).get("met") is True
                    )
        except Exception:
            continue
    
    aggregates["tools_used"] = list(aggregates["tools_used"])
    return aggregates


def _backfill_artifacts(record: GenerationRecord) -> None:
    if not record.files.metadata_path:
        return
    if record.files.payload_path and record.files.response_path and record.files.markdown_path:
        return

    meta = _load_json(record.files.metadata_path)
    if not meta:
        return

    backfilled_paths = _find_raw_artifacts(meta)
    record.files = ArtifactPaths(
        payload_path=record.files.payload_path or backfilled_paths.payload_path,
        response_path=record.files.response_path or backfilled_paths.response_path,
        metadata_path=record.files.metadata_path,
        markdown_path=record.files.markdown_path or backfilled_paths.markdown_path,
    )


def _load_openrouter_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Extract OpenRouter-specific metadata from generation metadata."""
    openrouter_data = {}
    
    # Extract from top-level metadata fields
    openrouter_data["generation_id"] = metadata.get("generation_id")
    openrouter_data["model_used"] = metadata.get("model_used")
    openrouter_data["created_timestamp"] = metadata.get("created_timestamp")
    openrouter_data["native_tokens_prompt"] = metadata.get("native_tokens_prompt")
    openrouter_data["native_tokens_completion"] = metadata.get("native_tokens_completion")
    openrouter_data["generation_time_ms"] = metadata.get("generation_time_ms")
    openrouter_data["provider_name"] = metadata.get("provider_name")
    openrouter_data["prompt_cost"] = metadata.get("prompt_cost")
    openrouter_data["completion_cost"] = metadata.get("completion_cost")
    openrouter_data["estimated_cost"] = metadata.get("estimated_cost")
    
    return openrouter_data


def _enrich_record_with_metrics(record: GenerationRecord) -> None:
    """Enrich record with code metrics and analysis data."""
    # Load metadata to get extracted blocks
    if record.files.metadata_path:
        meta = _load_json(record.files.metadata_path)
        if meta and isinstance(meta, dict):
            blocks = meta.get("extracted_blocks", [])
            if isinstance(blocks, list) and blocks:
                metrics = _compute_code_metrics_from_blocks(blocks)
                record.total_lines = metrics.get("total_lines")
                record.total_files = metrics.get("total_files")
                record.lines_by_language = metrics.get("lines_by_language")
                record.files_by_language = metrics.get("files_by_language")
            
            # Load OpenRouter metadata
            openrouter_data = _load_openrouter_metadata(meta)
            record.generation_id = openrouter_data.get("generation_id")
            record.model_used = openrouter_data.get("model_used")
            record.created_timestamp = openrouter_data.get("created_timestamp")
            record.native_tokens_prompt = openrouter_data.get("native_tokens_prompt")
            record.native_tokens_completion = openrouter_data.get("native_tokens_completion")
            record.generation_time_ms = openrouter_data.get("generation_time_ms")
            record.provider_name = openrouter_data.get("provider_name")
            record.prompt_cost = openrouter_data.get("prompt_cost")
            record.completion_cost = openrouter_data.get("completion_cost")
            record.estimated_cost = openrouter_data.get("estimated_cost")
    
    # Load analysis results
    analysis_data = _load_analysis_results(record.model, record.app_num)
    if analysis_data:
        record.analysis_findings = {
            "static_findings": analysis_data.get("static_findings", 0),
            "dynamic_findings": analysis_data.get("dynamic_findings", 0),
            "ai_findings": analysis_data.get("ai_findings", 0),
            "analysis_types": analysis_data.get("analysis_types", []),
            "tools_used": analysis_data.get("tools_used", []),
        }
        record.security_issues = analysis_data.get("security_issues")
        record.performance_score = analysis_data.get("performance_score")
        record.requirements_met = analysis_data.get("requirements_met")
        record.requirements_total = analysis_data.get("requirements_total")


def _load_generation_records_from_files() -> List[GenerationRecord]:
    records: List[GenerationRecord] = []
    for meta_path in _iter_metadata_files():
        metadata: Dict[str, Any] = _load_json(meta_path) or {}
        run_id = str(metadata.get("result_id") or meta_path.stem)
        model = str(metadata.get("model") or "unknown")
        component = metadata.get("component")
        app_num_raw = metadata.get("app_num")
        try:
            app_num_value = int(app_num_raw) if app_num_raw is not None else None
        except (TypeError, ValueError):
            app_num_value = None

        files = ArtifactPaths(
            payload_path=Path(str(path_hint)) if isinstance((path_hint := metadata.get("payload_path")), str) else None,
            response_path=Path(str(resp_hint)) if isinstance((resp_hint := metadata.get("response_path")), str) else None,
            metadata_path=meta_path,
            markdown_path=None,
        )

        app_name_raw = metadata.get("app_name")
        app_name_value = app_name_raw if isinstance(app_name_raw, str) else None

        success_raw = metadata.get("success")
        success_value = success_raw if isinstance(success_raw, bool) else None

        duration_raw = metadata.get("duration")
        duration_value = float(duration_raw) if isinstance(duration_raw, (int, float)) else None

        attempts_raw = metadata.get("attempts")
        attempts_value = int(attempts_raw) if isinstance(attempts_raw, int) else None

        prompt_tokens_raw = metadata.get("prompt_tokens")
        prompt_tokens_value = int(prompt_tokens_raw) if isinstance(prompt_tokens_raw, int) else None

        completion_tokens_raw = metadata.get("completion_tokens")
        completion_tokens_value = int(completion_tokens_raw) if isinstance(completion_tokens_raw, int) else None

        total_tokens_raw = metadata.get("total_tokens")
        total_tokens_value = int(total_tokens_raw) if isinstance(total_tokens_raw, int) else None

        finish_reason_raw = metadata.get("finish_reason")
        finish_reason_value = finish_reason_raw if isinstance(finish_reason_raw, str) else None

        error_raw = metadata.get("error_message")
        error_value = error_raw if isinstance(error_raw, str) else None

        request_headers_raw = metadata.get("request_headers")
        request_headers_value: Dict[str, Any] = request_headers_raw if isinstance(request_headers_raw, dict) else {}

        request_payload_raw = metadata.get("request_payload")
        request_payload_value: Dict[str, Any] = request_payload_raw if isinstance(request_payload_raw, dict) else {}

        response_status_raw = metadata.get("response_status")
        response_status_value = int(response_status_raw) if isinstance(response_status_raw, int) else None

        response_headers_raw = metadata.get("response_headers")
        response_headers_value: Dict[str, Any] = response_headers_raw if isinstance(response_headers_raw, dict) else {}

        timestamp_raw = metadata.get("timestamp")
        timestamp_value = _parse_timestamp(timestamp_raw) if isinstance(timestamp_raw, str) else None

        record = GenerationRecord(
            run_id=run_id,
            model=model,
            app_num=app_num_value,
            app_name=app_name_value,
            component=component if isinstance(component, str) else None,
            timestamp=timestamp_value,
            success=success_value,
            duration=duration_value,
            attempts=attempts_value,
            prompt_tokens=prompt_tokens_value,
            completion_tokens=completion_tokens_value,
            total_tokens=total_tokens_value,
            finish_reason=finish_reason_value,
            error_message=error_value,
            request_headers=request_headers_value,
            request_payload=request_payload_value,
            response_status=response_status_value,
            response_headers=response_headers_value,
            response_summary={},
            files=files,
        )
        _backfill_artifacts(record)
        _enrich_record_with_metrics(record)
        if not record.files.markdown_path:
            record.files = ArtifactPaths(
                payload_path=record.files.payload_path,
                response_path=record.files.response_path,
                metadata_path=record.files.metadata_path,
                markdown_path=_resolve_markdown_path(model, record.app_num),
            )
        records.append(record)
    return records


def _load_generation_records_from_code_results(limit: Optional[int] = None) -> List[GenerationRecord]:
    if not GeneratedCodeResult:
        return []

    try:
        query = GeneratedCodeResult.query.order_by(GeneratedCodeResult.timestamp.desc())
        if limit:
            query = query.limit(limit)
        rows = query.all()
    except Exception:
        return []

    records: List[GenerationRecord] = []
    for row in rows:
        run_id = str(row.result_id or f"code-result-{row.id}")
        timestamp = _normalize_timestamp(getattr(row, "timestamp", None))
        files = _guess_artifact_paths(getattr(row, "model", "unknown"), getattr(row, "app_num", None))

        request_payload: Dict[str, Any] = {}
        if getattr(row, "requirements_json", None):
            raw_requirements = row.requirements_json
            try:
                parsed_requirements = json.loads(raw_requirements)
            except Exception:
                parsed_requirements = raw_requirements
            request_payload["requirements"] = parsed_requirements

        response_summary: Dict[str, Any] = {}
        if getattr(row, "content", None):
            response_summary["content_preview"] = row.content[:120]

        record = GenerationRecord(
            run_id=run_id,
            model=getattr(row, "model", "unknown"),
            app_num=getattr(row, "app_num", None),
            app_name=getattr(row, "app_name", None),
            component="combined",
            timestamp=timestamp,
            success=getattr(row, "success", None),
            duration=getattr(row, "duration", None),
            attempts=None,
            prompt_tokens=None,
            completion_tokens=None,
            total_tokens=None,
            finish_reason=None,
            error_message=getattr(row, "error_message", None),
            request_headers={},
            request_payload=request_payload,
            response_status=None,
            response_headers={},
            response_summary=response_summary,
            files=files,
        )
        _backfill_artifacts(record)
        _enrich_record_with_metrics(record)
        records.append(record)
    return records


def _load_generation_records_from_applications(limit: Optional[int] = None) -> List[GenerationRecord]:
    if not GeneratedApplication:
        return []

    try:
        query = GeneratedApplication.query.order_by(GeneratedApplication.created_at.desc())
        if limit:
            query = query.limit(limit)
        apps = query.all()
    except Exception:
        return []

    records: List[GenerationRecord] = []
    for app in apps:
        metadata = app.get_metadata() if hasattr(app, "get_metadata") else {}
        run_id = str(metadata.get("result_id") or f"app-{app.id}")

        status_value = metadata.get("success")
        if isinstance(status_value, bool):
            success_value: Optional[bool] = status_value
        else:
            status_raw = getattr(app.generation_status, "value", app.generation_status)
            if isinstance(status_raw, str):
                success_value = status_raw.lower() == "completed"
            elif AnalysisStatus and app.generation_status == AnalysisStatus.COMPLETED:
                success_value = True
            elif AnalysisStatus and app.generation_status == AnalysisStatus.FAILED:
                success_value = False
            else:
                success_value = None

        def _as_int(value: Any) -> Optional[int]:
            if isinstance(value, int):
                return value
            try:
                return int(value)
            except Exception:
                return None

        def _as_float(value: Any) -> Optional[float]:
            if isinstance(value, (int, float)):
                return float(value)
            try:
                return float(value)
            except Exception:
                return None

        request_payload: Dict[str, Any] = {}
        if isinstance(metadata.get("request_payload"), dict):
            request_payload = metadata["request_payload"]
        elif metadata.get("requirements"):
            request_payload = {"requirements": metadata.get("requirements")}

        response_headers = cast(Dict[str, Any], metadata.get("response_headers")) if isinstance(metadata.get("response_headers"), dict) else {}
        request_headers = cast(Dict[str, Any], metadata.get("request_headers")) if isinstance(metadata.get("request_headers"), dict) else {}

        record = GenerationRecord(
            run_id=run_id,
            model=getattr(app, "model_slug", "unknown"),
            app_num=getattr(app, "app_number", None),
            app_name=metadata.get("app_name"),
            component=metadata.get("component") if isinstance(metadata.get("component"), str) else "combined",
            timestamp=_normalize_timestamp(getattr(app, "created_at", None)),
            success=success_value,
            duration=_as_float(metadata.get("duration")),
            attempts=_as_int(metadata.get("attempts")),
            prompt_tokens=_as_int(metadata.get("prompt_tokens")),
            completion_tokens=_as_int(metadata.get("completion_tokens")),
            total_tokens=_as_int(metadata.get("total_tokens")),
            finish_reason=metadata.get("finish_reason") if isinstance(metadata.get("finish_reason"), str) else None,
            error_message=metadata.get("error_message") if isinstance(metadata.get("error_message"), str) else None,
            request_headers=request_headers,
            request_payload=request_payload,
            response_status=_as_int(metadata.get("response_status")),
            response_headers=response_headers,
            response_summary={"linked_components": metadata.get("linked_components") or {}},
            files=_guess_artifact_paths(getattr(app, "model_slug", "unknown"), getattr(app, "app_number", None)),
        )
        _backfill_artifacts(record)
        _enrich_record_with_metrics(record)
        records.append(record)
    return records


def load_generation_records(
    limit: Optional[int] = None,
    *,
    include_files: bool = True,
    include_db: bool = True,
    include_applications: bool = True,
) -> List[GenerationRecord]:
    records: Dict[str, GenerationRecord] = {}

    if include_files:
        for record in _load_generation_records_from_files():
            records[record.run_id] = record

    if include_db:
        for record in _load_generation_records_from_code_results(limit=limit):
            records.setdefault(record.run_id, record)

    if include_applications:
        for record in _load_generation_records_from_applications(limit=limit):
            records.setdefault(record.run_id, record)

    ordered = sorted(records.values(), key=lambda r: r.timestamp or datetime.min, reverse=True)
    if limit:
        return ordered[:limit]
    return ordered


def _get_task_statistics() -> Dict[str, Any]:
    """Gather statistics about analysis tasks from the database."""
    try:
        from app.models import AnalysisTask
        from app.constants import AnalysisStatus, AnalysisType
        from sqlalchemy import func
        
        # Get total task counts by status
        total_tasks = AnalysisTask.query.count()
        
        if total_tasks == 0:
            return {
                "total_tasks": 0,
                "by_status": {},
                "by_type": {},
                "success_rate": 0.0,
                "avg_duration": 0.0,
                "total_issues_found": 0,
            }
        
        # Count by status
        status_counts = {}
        for status in AnalysisStatus:
            count = AnalysisTask.query.filter_by(status=status).count()
            if count > 0:
                status_counts[status.value] = count
        
        # Count by type
        type_counts = {}
        for analysis_type in AnalysisType:
            count = AnalysisTask.query.filter_by(analysis_type=analysis_type).count()
            if count > 0:
                type_counts[analysis_type.value] = count
        
        # Calculate success rate
        completed_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.COMPLETED).count()
        failed_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.FAILED).count()
        success_rate = (completed_tasks / (completed_tasks + failed_tasks) * 100) if (completed_tasks + failed_tasks) > 0 else 0.0
        
        # Calculate average duration for completed tasks
        avg_duration_result = AnalysisTask.query.filter(
            AnalysisTask.status == AnalysisStatus.COMPLETED,
            AnalysisTask.actual_duration.isnot(None)
        ).with_entities(func.avg(AnalysisTask.actual_duration)).scalar()
        avg_duration = float(avg_duration_result) if avg_duration_result else 0.0
        
        # Sum total issues found
        total_issues_result = AnalysisTask.query.with_entities(
            func.sum(AnalysisTask.issues_found)
        ).scalar()
        total_issues = int(total_issues_result) if total_issues_result else 0
        
        return {
            "total_tasks": total_tasks,
            "by_status": status_counts,
            "by_type": type_counts,
            "success_rate": round(success_rate, 2),
            "avg_duration": round(avg_duration, 2),
            "total_issues_found": total_issues,
        }
    except Exception as e:
        # Gracefully handle database/import errors
        return {
            "total_tasks": 0,
            "by_status": {},
            "by_type": {},
            "success_rate": 0.0,
            "avg_duration": 0.0,
            "total_issues_found": 0,
            "error": str(e),
        }


def summarize_generation_counts() -> Dict[str, object]:
    records = load_generation_records()
    total = len(records)
    by_model: Dict[str, int] = {}
    by_component: Dict[str, int] = {}
    by_provider: Dict[str, int] = {}
    success_count = 0
    total_duration = 0.0
    total_lines = 0
    total_tokens = 0
    records_with_duration = 0
    records_with_lines = 0
    records_with_tokens = 0
    security_issues_total = 0
    requirements_met_total = 0
    requirements_total_count = 0
    # OpenRouter aggregates
    total_native_tokens_prompt = 0
    total_native_tokens_completion = 0
    total_generation_time_ms = 0
    total_cost = 0.0
    records_with_native_tokens = 0
    records_with_generation_time = 0
    records_with_cost = 0

    for rec in records:
        key_model = rec.model or "unknown"
        by_model[key_model] = by_model.get(key_model, 0) + 1
        comp_key = rec.component or "combined"
        by_component[comp_key] = by_component.get(comp_key, 0) + 1
        if rec.provider_name:
            by_provider[rec.provider_name] = by_provider.get(rec.provider_name, 0) + 1
        if rec.success:
            success_count += 1
        if rec.duration and rec.duration > 0:
            total_duration += rec.duration
            records_with_duration += 1
        if rec.total_lines and rec.total_lines > 0:
            total_lines += rec.total_lines
            records_with_lines += 1
        if rec.total_tokens and rec.total_tokens > 0:
            total_tokens += rec.total_tokens
            records_with_tokens += 1
        if rec.security_issues:
            security_issues_total += rec.security_issues
        if rec.requirements_met:
            requirements_met_total += rec.requirements_met
        if rec.requirements_total:
            requirements_total_count += rec.requirements_total
        # OpenRouter metrics
        if rec.native_tokens_prompt and rec.native_tokens_completion:
            total_native_tokens_prompt += rec.native_tokens_prompt
            total_native_tokens_completion += rec.native_tokens_completion
            records_with_native_tokens += 1
        if rec.generation_time_ms:
            total_generation_time_ms += rec.generation_time_ms
            records_with_generation_time += 1
        if rec.estimated_cost:
            total_cost += rec.estimated_cost
            records_with_cost += 1

    # Get task statistics
    task_stats = _get_task_statistics()

    return {
        "total_runs": total,
        "successful_runs": success_count,
        "success_rate": round(success_count / total * 100, 2) if total else 0.0,
        "by_model": by_model,
        "by_component": by_component,
        "by_provider": by_provider,
        "avg_duration": round(total_duration / records_with_duration, 2) if records_with_duration else 0.0,
        "total_lines_generated": total_lines,
        "avg_lines_per_generation": round(total_lines / records_with_lines, 0) if records_with_lines else 0,
        "total_tokens_used": total_tokens,
        "avg_tokens_per_generation": round(total_tokens / records_with_tokens, 0) if records_with_tokens else 0,
        "total_security_issues": security_issues_total,
        "requirements_met": requirements_met_total,
        "requirements_total": requirements_total_count,
        "requirements_compliance_rate": round(requirements_met_total / requirements_total_count * 100, 2) if requirements_total_count else 0.0,
        # OpenRouter metrics
        "avg_native_tokens_prompt": round(total_native_tokens_prompt / records_with_native_tokens, 0) if records_with_native_tokens else 0,
        "avg_native_tokens_completion": round(total_native_tokens_completion / records_with_native_tokens, 0) if records_with_native_tokens else 0,
        "avg_generation_time_ms": round(total_generation_time_ms / records_with_generation_time, 0) if records_with_generation_time else 0,
        "total_cost": round(total_cost, 4),
        "avg_cost_per_generation": round(total_cost / records_with_cost, 4) if records_with_cost else 0.0,
        # Task statistics
        "task_stats": task_stats,
    }


def build_generation_table_data(limit: Optional[int] = None) -> List[Dict[str, object]]:
    records = load_generation_records(limit=limit)
    rows: List[Dict[str, object]] = []
    for record in records:
        rows.append(
            {
                "run_id": record.run_id,
                "timestamp": record.timestamp.isoformat() if record.timestamp else None,
                "model": record.model,
                "component": record.component,
                "app_num": record.app_num,
                "app_name": record.app_name,
                "success": record.success,
                "duration": record.duration,
                "attempts": record.attempts,
                "prompt_tokens": record.prompt_tokens,
                "completion_tokens": record.completion_tokens,
                "total_tokens": record.total_tokens,
                "finish_reason": record.finish_reason,
                "error_message": record.error_message,
                "payload_path": str(record.files.payload_path) if record.files.payload_path else None,
                "response_path": str(record.files.response_path) if record.files.response_path else None,
                "metadata_path": str(record.files.metadata_path) if record.files.metadata_path else None,
                "markdown_path": str(record.files.markdown_path) if record.files.markdown_path else None,
                # Code metrics
                "total_lines": record.total_lines,
                "total_files": record.total_files,
                "lines_by_language": record.lines_by_language,
                "files_by_language": record.files_by_language,
                # Analysis data
                "analysis_findings": record.analysis_findings,
                "security_issues": record.security_issues,
                "performance_score": record.performance_score,
                "requirements_met": record.requirements_met,
                "requirements_total": record.requirements_total,
                # OpenRouter metadata
                "generation_id": record.generation_id,
                "model_used": record.model_used,
                "created_timestamp": record.created_timestamp,
                "native_tokens_prompt": record.native_tokens_prompt,
                "native_tokens_completion": record.native_tokens_completion,
                "generation_time_ms": record.generation_time_ms,
                "provider_name": record.provider_name,
                "prompt_cost": record.prompt_cost,
                "completion_cost": record.completion_cost,
                "estimated_cost": record.estimated_cost,
            }
        )
    return rows


def collect_file_system_metrics() -> Dict[str, object]:
    def _count_files(root: Path) -> int:
        if not root.exists():
            return 0
        return sum(1 for _ in root.rglob("*") if _.is_file())

    return {
        "raw_payload_files": _count_files(GENERATED_RAW_API_PAYLOADS_DIR),
        "raw_response_files": _count_files(GENERATED_RAW_API_RESPONSES_DIR),
        "markdown_files": _count_files(GENERATED_MARKDOWN_DIR),
        "app_directories": len([p for p in GENERATED_APPS_DIR.glob("*") if p.is_dir()]),
    }


def write_generation_summary(limit: Optional[int] = None) -> Path:
    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": summarize_generation_counts(),
        "filesystem": collect_file_system_metrics(),
        "records": build_generation_table_data(limit=limit),
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return SUMMARY_PATH


__all__ = [
    "GenerationRecord",
    "load_generation_records",
    "summarize_generation_counts",
    "build_generation_table_data",
    "collect_file_system_metrics",
    "write_generation_summary",
]
