"""
SubtaskResult Schema
====================

Formal dataclass defining the structure of subtask results to prevent structural
drift between individual task execution and pipeline aggregation.

This schema ensures that:
1. Both code paths produce identical result structures
2. Templates can reliably access results via the 'analysis' key
3. Tool results are always at a consistent nesting level
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


@dataclass
class SubtaskResult:
    """
    Standardized result structure for analyzer subtasks.
    
    This matches the format expected by:
    - `transform_services()` in src/app/routes/jinja/analysis.py
    - Template: analysis_result_detail.html
    - UnifiedResultService
    
    Structure:
    {
        'status': 'success|error|partial',
        'service_name': 'static-analyzer',
        'subtask_id': 123,
        'analysis': {
            'results': {...},  # Tool results grouped by language/type
            'tools_used': [...],
            'summary': {...}
        },
        'payload': {...},  # Same as analysis for backward compat
        'error': None,
        'metadata': {...}
    }
    """
    status: str  # 'success', 'error', 'partial', 'timeout'
    service_name: str
    subtask_id: Optional[int] = None
    
    # Analysis results - the core data
    analysis: Dict[str, Any] = field(default_factory=dict)
    
    # Error information (if status is 'error')
    error: Optional[str] = None
    
    # Metadata
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary format expected by templates and aggregation.
        
        Returns structure compatible with transform_services():
        {
            'status': 'success',
            'service_name': 'static-analyzer',
            'analysis': {...},
            'payload': {...},  # Alias for backward compatibility
            'error': None
        }
        """
        result = {
            'status': self.status,
            'service_name': self.service_name,
            'subtask_id': self.subtask_id,
            'analysis': self.analysis,
            'payload': self.analysis,  # Backward compatibility alias
            'error': self.error,
            'metadata': {
                'started_at': self.started_at.isoformat() if self.started_at else None,
                'completed_at': self.completed_at.isoformat() if self.completed_at else None,
                'duration_seconds': self.duration_seconds
            }
        }
        return result
    
    @classmethod
    def from_websocket_response(
        cls,
        response: Dict[str, Any],
        service_name: str,
        subtask_id: Optional[int] = None
    ) -> 'SubtaskResult':
        """
        Create SubtaskResult from raw WebSocket response.
        
        Handles multiple response formats:
        1. {type: 'static_analysis_result', analysis: {...}}
        2. {status: 'success', analysis: {...}}
        3. {status: 'success', payload: {...}}  # Legacy
        """
        # Determine status
        status_val = response.get('status', 'unknown')
        if status_val in ('completed', 'ok'):
            status_val = 'success'
        
        # Extract analysis data from various locations
        analysis = {}
        
        # Priority 1: Direct 'analysis' key (standard format)
        if isinstance(response.get('analysis'), dict):
            analysis = response['analysis']
        
        # Priority 2: 'payload' key (some services wrap in payload)
        elif isinstance(response.get('payload'), dict):
            payload = response['payload']
            # Check if payload contains analysis
            if isinstance(payload.get('analysis'), dict):
                analysis = payload['analysis']
            else:
                # payload IS the analysis
                analysis = payload
        
        # Priority 3: Look for 'results' at top level
        elif isinstance(response.get('results'), dict):
            analysis = {'results': response['results']}
        
        # Extract error
        error = response.get('error')
        if not error and status_val in ('error', 'failed'):
            error = 'Unknown error'
        
        return cls(
            status=status_val,
            service_name=service_name,
            subtask_id=subtask_id,
            analysis=analysis,
            error=error
        )
    
    @classmethod
    def error_result(
        cls,
        service_name: str,
        error_message: str,
        subtask_id: Optional[int] = None
    ) -> 'SubtaskResult':
        """Create an error result."""
        return cls(
            status='error',
            service_name=service_name,
            subtask_id=subtask_id,
            analysis={},
            error=error_message
        )
    
    def get_findings(self) -> List[Dict[str, Any]]:
        """Extract findings from analysis."""
        findings = []
        
        # Check various locations for findings
        if isinstance(self.analysis.get('findings'), list):
            findings.extend(self.analysis['findings'])
        
        if isinstance(self.analysis.get('results'), dict):
            results = self.analysis['results']
            # Static analyzer: results grouped by language
            for lang, tools in results.items():
                if isinstance(tools, dict):
                    for tool_name, tool_data in tools.items():
                        if isinstance(tool_data, dict):
                            tool_issues = tool_data.get('issues', [])
                            if isinstance(tool_issues, list):
                                # Tag each finding with service/tool info
                                for issue in tool_issues:
                                    if isinstance(issue, dict):
                                        issue['service'] = self.service_name
                                        issue['tool'] = tool_name
                                        findings.append(issue)
        
        return findings
    
    def get_tool_results(self) -> Dict[str, Any]:
        """Extract flat tool results for aggregation."""
        tool_results = {}
        
        # Check 'tool_results' key first
        if isinstance(self.analysis.get('tool_results'), dict):
            tool_results.update(self.analysis['tool_results'])
        
        # Extract from nested results structure
        if isinstance(self.analysis.get('results'), dict):
            results = self.analysis['results']
            for lang, tools in results.items():
                if isinstance(tools, dict):
                    for tool_name, tool_data in tools.items():
                        if isinstance(tool_data, dict) and tool_name not in tool_results:
                            tool_results[tool_name] = tool_data
        
        return tool_results


def normalize_subtask_result(
    raw_result: Dict[str, Any],
    service_name: str,
    subtask_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Normalize a raw subtask result to the standard schema.
    
    This function can be used to fix results that don't match the expected schema.
    
    Args:
        raw_result: Raw result from WebSocket or aggregation
        service_name: Service name (e.g., 'static-analyzer')
        subtask_id: Optional subtask ID
        
    Returns:
        Dict matching the SubtaskResult.to_dict() format
    """
    subtask_result = SubtaskResult.from_websocket_response(
        raw_result,
        service_name,
        subtask_id
    )
    return subtask_result.to_dict()
