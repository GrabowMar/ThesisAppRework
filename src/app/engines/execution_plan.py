"""Execution planning primitives for the analysis orchestrator.

This module defines lightweight data containers that describe how the
`AnalysisOrchestrator` will execute a requested analysis run. Splitting these
concerns out of `orchestrator.py` keeps that module focused on application
logic while sharing a consistent contract between planning, execution, and
result aggregation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class AnalysisContext:
    """Shared context for an analysis run.

    Attributes:
        model_slug: Canonical model identifier.
        app_number: Application number within the model catalog.
        target_path: Resolved filesystem path to the generated application.
        requested_tools: Normalized tool identifiers requested for the run.
        detected_languages: Languages detected from the codebase (best-effort).
        tags: Optional tag filters provided by the caller.
    """

    model_slug: str
    app_number: int
    target_path: Path
    requested_tools: Tuple[str, ...]
    detected_languages: Tuple[str, ...]
    tags: Tuple[str, ...] = tuple()

    def with_tools(self, tools: Sequence[str]) -> "AnalysisContext":
        """Return a copy of the context with a different tool selection."""

        return AnalysisContext(
            model_slug=self.model_slug,
            app_number=self.app_number,
            target_path=self.target_path,
            requested_tools=tuple(tools),
            detected_languages=self.detected_languages,
            tags=self.tags,
        )


@dataclass(frozen=True)
class ServiceDelegation:
    """Represents a group of tools handled by a single analyzer service."""

    service_name: str
    tools: Tuple[str, ...]

    def is_empty(self) -> bool:
        return not self.tools


@dataclass(frozen=True)
class ToolExecutionPlan:
    """Complete execution plan for a run.

    Attributes:
        context: Shared analysis context.
        delegated: Sequence of service delegations (non-local execution).
        local_tools: Tools expected to run in-process (legacy/local path).
    """

    context: AnalysisContext
    delegated: Tuple[ServiceDelegation, ...]
    local_tools: Tuple[str, ...] = tuple()

    @property
    def all_tools(self) -> Tuple[str, ...]:
        return tuple(tool for block in self.delegated for tool in block.tools) + self.local_tools

    def has_work(self) -> bool:
        return bool(self.delegated or self.local_tools)


@dataclass
class ToolExecutionOutcome:
    """Result metadata captured for a single tool execution."""

    tool_name: str
    status: str
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    findings: List[Any] = field(default_factory=list)
    delegated: bool = False
    error: Optional[str] = None

    def mark_delegated(self) -> None:
        self.delegated = True


@dataclass
class ExecutionAggregate:
    """High-level aggregation of a run for persistence and presentation."""

    context: AnalysisContext
    expected_tools: int = 0
    outcomes: List[ToolExecutionOutcome] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    raw_outputs: Dict[str, Mapping[str, object]] = field(default_factory=dict)
    findings: List[Any] = field(default_factory=list)

    def register_outcome(self, outcome: ToolExecutionOutcome, findings: Iterable[Any] = ()) -> None:
        findings_list = list(findings)
        outcome.findings = findings_list
        self.outcomes.append(outcome)
        status_lower = outcome.status.lower()
        if outcome.status.startswith("❌") or "error" in status_lower or "fail" in status_lower or "not available" in status_lower:
            self.failure_count += 1
        else:
            self.success_count += 1
        if outcome.raw_payload:
            snapshot: Dict[str, Any] = {}
            for field in ('raw_output', 'output', 'stdout', 'stderr', 'command_line', 'exit_code', 'error'):
                value = outcome.raw_payload.get(field)
                if value is not None:
                    snapshot[field] = value
            if snapshot:
                self.raw_outputs[outcome.tool_name] = snapshot
        for finding in findings_list:
            self.findings.append(finding)

    @property
    def tool_results(self) -> Dict[str, Mapping[str, object]]:
        return {outcome.tool_name: outcome.raw_payload for outcome in self.outcomes}

    @property
    def completed_tools(self) -> int:
        return len(self.outcomes)

    @property
    def progress_percentage(self) -> float:
        if not self.expected_tools:
            return 0.0
        return min(100.0, (self.completed_tools / self.expected_tools) * 100.0)

    def to_summary(self) -> Mapping[str, object]:
        return {
            "tools_successful": self.success_count,
            "tools_failed": self.failure_count,
            "tools_requested": list(self.context.requested_tools),
        }


def group_tools_by_service(
    service_mapper: Mapping[str, Optional[str]],
    tools: Iterable[str],
) -> Tuple[List[ServiceDelegation], List[str]]:
    """Group tools into delegated vs. local blocks based on a mapping.

    Args:
        service_mapper: Mapping of tool->service name ("local" or ``None`` for in-process).
        tools: Normalized tool identifiers.

    Returns:
        Tuple of (delegated blocks, local tools).
    """

    delegated: Dict[str, List[str]] = {}
    local: List[str] = []

    for tool in tools:
        service = service_mapper.get(tool)
        if service and service != "local":
            delegated.setdefault(service, []).append(tool)
        else:
            local.append(tool)

    delegated_groups = [ServiceDelegation(service, tuple(sorted(t_list))) for service, t_list in sorted(delegated.items())]
    local_sorted = sorted(local)
    return delegated_groups, local_sorted
