"""
Analysis-related database models.
"""
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from ..extensions import db
from ..utils.time import utc_now
from ..constants import AnalysisStatus, JobPriority as Priority, SeverityLevel, AnalysisType

class AnalyzerConfiguration(db.Model):
    """Configuration profiles for different analyzer types and tools."""
    __tablename__ = 'analyzer_configurations'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    description = db.Column(db.Text)
    
    # Configuration settings stored as JSON
    config_data = db.Column(db.Text, nullable=False)  # Tool-specific configuration
    template_config = db.Column(db.Text)  # Reusable template settings
    
    # Metadata and categorization
    is_active = db.Column(db.Boolean, default=True, index=True)
    is_default = db.Column(db.Boolean, default=False)
    tags = db.Column(db.Text)  # JSON array of tags
    category = db.Column(db.String(100))  # e.g., "quick-scan", "comprehensive"
    
    # Usage and performance metrics
    usage_count = db.Column(db.Integer, default=0)
    success_rate = db.Column(db.Float, default=0.0)  # Percentage of successful runs
    avg_execution_time = db.Column(db.Float, default=0.0)  # Average time in seconds
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    last_used = db.Column(db.DateTime(timezone=True))
    
    def __init__(
        self,
        *,
        name: str = "",
        description: Optional[str] = None,
        config_data: str = "{}",
        template_config: Optional[str] = None,
        is_active: bool = True,
        is_default: bool = False,
        tags: Optional[str] = None,
        category: Optional[str] = None,
        usage_count: int = 0,
        success_rate: float = 0.0,
        avg_execution_time: float = 0.0,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        last_used: Optional[datetime] = None,
        **kwargs: Any
    ) -> None:
        """Initialize AnalyzerConfiguration with typed parameters."""
        # Pack all params into kwargs for SQLAlchemy
        init_kwargs = {
            'name': name,
            'description': description,
            'config_data': config_data,
            'template_config': template_config,
            'is_active': is_active,
            'is_default': is_default,
            'tags': tags,
            'category': category,
            'usage_count': usage_count,
            'success_rate': success_rate,
            'avg_execution_time': avg_execution_time,
            'created_at': created_at,
            'updated_at': updated_at,
            'last_used': last_used,
            **kwargs
        }
        super().__init__(**init_kwargs)
    
    def get_config_data(self) -> Dict[str, Any]:
        """Get configuration data as dictionary."""
        if self.config_data:
            try:
                return json.loads(self.config_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_config_data(self, config_dict: Dict[str, Any]) -> None:
        """Set configuration data from dictionary."""
        self.config_data = json.dumps(config_dict)
    
    def get_template_config(self) -> Dict[str, Any]:
        """Get template configuration as dictionary."""
        if self.template_config:
            try:
                return json.loads(self.template_config)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_template_config(self, template_dict: Dict[str, Any]) -> None:
        """Set template configuration from dictionary."""
        self.template_config = json.dumps(template_dict)
    
    def get_tags(self) -> List[str]:
        """Get tags as list."""
        if self.tags:
            try:
                return json.loads(self.tags)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_tags(self, tags_list: List[str]) -> None:
        """Set tags from list."""
        self.tags = json.dumps(tags_list)
    
    def update_metrics(self, execution_time: float, success: bool) -> None:
        """Update usage metrics."""
        self.usage_count += 1
        self.last_used = utc_now()
        
        # Update average execution time
        if self.usage_count == 1:
            self.avg_execution_time = execution_time
        else:
            self.avg_execution_time = ((self.avg_execution_time * (self.usage_count - 1)) + execution_time) / self.usage_count
        
        # Update success rate
        if success:
            successful_runs = (self.success_rate / 100.0) * (self.usage_count - 1) + 1
        else:
            successful_runs = (self.success_rate / 100.0) * (self.usage_count - 1)
        self.success_rate = (successful_runs / self.usage_count) * 100.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'config_data': self.get_config_data(),
            'template_config': self.get_template_config(),
            'is_active': self.is_active,
            'is_default': self.is_default,
            'tags': self.get_tags(),
            'category': self.category,
            'usage_count': self.usage_count,
            'success_rate': self.success_rate,
            'avg_execution_time': self.avg_execution_time,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_used': self.last_used
        }
    
    def __repr__(self) -> str:
        return f'<AnalyzerConfiguration {self.name}>'

    # --- Backward compatibility helpers expected by analyzer_service ---
    @property
    def config_id(self) -> int:
        return self.id

    def get_tools_config(self) -> Dict[str, Any]:
        return self.get_config_data().get('tools_config', {})

    def get_execution_config(self) -> Dict[str, Any]:
        return self.get_config_data().get('execution_config', {})

    def get_output_config(self) -> Dict[str, Any]:
        return self.get_config_data().get('output_config', {})


class AnalysisTask(db.Model):
    """Individual analysis task tracking and management."""
    __tablename__ = 'analysis_tasks'
    # NOTE: Unique constraint on (target_model, target_app_number, batch_id) prevents duplicate tasks
    # for the same app within a pipeline. For SQLite (which doesn't support row-level locking),
    # this is a critical safety net to prevent race condition duplicates.
    __table_args__ = (
        db.UniqueConstraint(
            'target_model', 'target_app_number', 'batch_id',
            name='uq_analysis_task_model_app_pipeline'
        ),
        {'extend_existing': True}
    )
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Task hierarchy (parent/child relationship)
    parent_task_id = db.Column(db.String(100), db.ForeignKey('analysis_tasks.task_id'), nullable=True, index=True)
    is_main_task = db.Column(db.Boolean, default=False, index=True)
    service_name = db.Column(db.String(100), nullable=True)  # e.g., 'static-analyzer', 'ai-analyzer' for subtasks
    
    # --- Compatibility Property ---
    @property
    def analysis_type(self):
        """Temporary compatibility property to avoid AttributeError.
        
        This allows older code referencing `analysis_type` to still function
        by redirecting it to the correct `task_name` attribute.
        
        TODO: Remove this property after all references are updated.
        """
        return self.task_name
    # --------------------------

    # Task configuration
    analyzer_config_id = db.Column(db.Integer, db.ForeignKey('analyzer_configurations.id'), nullable=False)
    status = db.Column(db.Enum(AnalysisStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]), default=AnalysisStatus.PENDING, index=True)
    priority = db.Column(db.Enum(Priority, native_enum=False, values_callable=lambda obj: [e.value for e in obj]), default=Priority.NORMAL, index=True)
    
    # Target application information
    target_model = db.Column(db.String(200), nullable=False, index=True)
    target_app_number = db.Column(db.Integer, nullable=False)
    target_path = db.Column(db.String(500))
    
    # Task metadata
    task_name = db.Column(db.String(200))
    description = db.Column(db.Text)
    task_metadata = db.Column(db.Text)  # JSON metadata
    
    # Progress tracking
    progress_percentage = db.Column(db.Float, default=0.0)
    current_step = db.Column(db.String(200))
    total_steps = db.Column(db.Integer)
    completed_steps = db.Column(db.Integer, default=0)
    
    # Batch association
    batch_id = db.Column(db.String(100), index=True)  # Optional batch association
    
    # Execution details
    assigned_worker = db.Column(db.String(100))  # Worker/analyzer instance
    execution_context = db.Column(db.Text)  # JSON execution context
    
    # Results summary
    result_summary = db.Column(db.Text)  # JSON summary of findings
    issues_found = db.Column(db.Integer, default=0)
    severity_breakdown = db.Column(db.Text)  # JSON severity count breakdown
    
    # Timing and performance
    estimated_duration = db.Column(db.Integer)  # Estimated duration in seconds
    actual_duration = db.Column(db.Float)  # Actual duration in seconds
    queue_time = db.Column(db.Float)  # Time spent in queue
    
    # Error handling
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    
    # Relationships
    analyzer_config = db.relationship('AnalyzerConfiguration', backref='tasks')
    results = db.relationship('AnalysisResult', backref='task', cascade='all, delete-orphan')
    
    # Parent-child task relationships
    subtasks = db.relationship('AnalysisTask', 
                               backref=db.backref('parent_task', remote_side=[task_id]),
                               foreign_keys=[parent_task_id],
                               cascade='all, delete-orphan')
    
    def get_all_subtasks(self):
        """Get all subtasks recursively."""
        if not self.is_main_task:
            return []
        return list(self.subtasks)  # type: ignore[arg-type]
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.task_metadata:
            try:
                return json.loads(self.task_metadata)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.task_metadata = json.dumps(metadata_dict)
    
    def get_execution_context(self) -> Dict[str, Any]:
        """Get execution context as dictionary."""
        if self.execution_context:
            try:
                return json.loads(self.execution_context)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_execution_context(self, context_dict: Dict[str, Any]) -> None:
        """Set execution context from dictionary."""
        self.execution_context = json.dumps(context_dict)
    
    def get_result_summary(self) -> Dict[str, Any]:
        """Get result summary as dictionary."""
        if self.result_summary:
            try:
                return json.loads(self.result_summary)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_result_summary(self, summary_dict: Dict[str, Any]) -> None:
        """Set result summary from dictionary."""
        self.result_summary = json.dumps(summary_dict)
    
    def get_severity_breakdown(self) -> Dict[str, int]:
        """Get severity breakdown as dictionary."""
        if self.severity_breakdown:
            try:
                return json.loads(self.severity_breakdown)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_severity_breakdown(self, breakdown_dict: Dict[str, int]) -> None:
        """Set severity breakdown from dictionary."""
        self.severity_breakdown = json.dumps(breakdown_dict)
    
    def update_progress(self, percentage: float, current_step: Optional[str] = None) -> None:
        """Update task progress."""
        self.progress_percentage = min(100.0, max(0.0, percentage))
        if current_step:
            self.current_step = current_step
        self.updated_at = utc_now()
    
    def start_execution(self, worker: Optional[str] = None) -> None:
        """Mark task as started."""
        self.status = AnalysisStatus.RUNNING
        self.started_at = utc_now()
        if worker:
            self.assigned_worker = worker
    
    def complete_execution(self, success: bool = True, error_message: Optional[str] = None) -> None:
        """Mark task as completed or failed."""
        self.completed_at = utc_now()
        if success:
            self.status = AnalysisStatus.COMPLETED
            self.progress_percentage = 100.0
        else:
            self.status = AnalysisStatus.FAILED
            if error_message:
                self.error_message = error_message
        
        # Calculate actual duration (ensure both timestamps are timezone-aware)
        if self.started_at:
            started = self.started_at
            completed = self.completed_at
            # Normalize to UTC if one is naive
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            if completed.tzinfo is None:
                completed = completed.replace(tzinfo=timezone.utc)
            self.actual_duration = (completed - started).total_seconds()

    # --- Compatibility methods for analyzer_integration (legacy naming) ---
    def mark_completed(self, analysis_data: Dict[str, Any] | None = None) -> None:
        """Backward compatible wrapper used by analyzer_integration.

        Parameters:
            analysis_data: Optional dict with summary/result info to persist to result_summary
        """
        self.complete_execution(success=True)
        if analysis_data is not None:
            # Store summary under result_summary field
            try:
                self.set_result_summary(analysis_data if isinstance(analysis_data, dict) else {'data': analysis_data})
            except Exception:
                # Fail-safe: ignore serialization issues
                pass

    def mark_failed(self, error_message: str) -> None:
        """Backward compatible wrapper used by analyzer_integration."""
        self.complete_execution(success=False, error_message=error_message)
    
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.retry_count < self.max_retries and self.status == AnalysisStatus.FAILED
    
    def retry(self) -> None:
        """Retry the task."""
        if self.can_retry():
            self.retry_count += 1
            self.status = AnalysisStatus.PENDING
            self.error_message = None
            self.started_at = None
            self.completed_at = None
            self.progress_percentage = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'analyzer_config_id': self.analyzer_config_id,
            'status': self.status.value if self.status else None,
            'priority': self.priority.value if self.priority else None,
            'target_model': self.target_model,
            'target_app_number': self.target_app_number,
            'target_path': self.target_path,
            'task_name': self.task_name,
            'description': self.description,
            'metadata': self.get_metadata(),
            'progress_percentage': self.progress_percentage,
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'completed_steps': self.completed_steps,
            'batch_id': self.batch_id,
            'assigned_worker': self.assigned_worker,
            'execution_context': self.get_execution_context(),
            'result_summary': self.get_result_summary(),
            'issues_found': self.issues_found,
            'severity_breakdown': self.get_severity_breakdown(),
            'estimated_duration': self.estimated_duration,
            'actual_duration': self.actual_duration,
            'queue_time': self.queue_time,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at
        }
    
    def __repr__(self) -> str:
        return f'<AnalysisTask {self.task_id}>'


class AnalysisResult(db.Model):
    """Detailed analysis results and findings."""
    __tablename__ = 'analysis_results'
    
    id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Association with task
    task_id = db.Column(db.String(100), db.ForeignKey('analysis_tasks.task_id'), nullable=False, index=True)
    
    # Result metadata
    tool_name = db.Column(db.String(100), nullable=False)  # Specific tool that generated result
    tool_version = db.Column(db.String(50))
    result_type = db.Column(db.String(50), nullable=False)  # finding, metric, summary, etc.
    
    # Finding details
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    severity = db.Column(db.Enum(SeverityLevel), nullable=False, index=True)
    confidence = db.Column(db.String(20))  # low, medium, high
    
    # Location information
    file_path = db.Column(db.String(1000))
    line_number = db.Column(db.Integer)
    column_number = db.Column(db.Integer)
    code_snippet = db.Column(db.Text)
    
    # Classification
    category = db.Column(db.String(100))  # security, performance, quality, etc.
    rule_id = db.Column(db.String(100))   # Tool-specific rule identifier
    tags = db.Column(db.Text)  # JSON array of tags
    
    # SARIF 2.1.0 compliance fields
    sarif_level = db.Column(db.String(20))  # SARIF level: note, warning, error
    sarif_rule_id = db.Column(db.String(100))  # SARIF ruleId (may differ from tool rule_id)
    sarif_metadata = db.Column(db.Text)  # JSON: CWE IDs, WASC, tool-specific properties
    
    # Detailed data
    raw_output = db.Column(db.Text)  # Raw tool output
    structured_data = db.Column(db.Text)  # JSON structured finding data
    recommendations = db.Column(db.Text)  # JSON array of recommendations
    
    # Impact and priority
    impact_score = db.Column(db.Float)  # 0-10 impact score
    business_impact = db.Column(db.String(20))  # low, medium, high, critical
    remediation_effort = db.Column(db.String(20))  # low, medium, high
    
    # Status tracking
    status = db.Column(db.String(20), default='new')  # new, reviewed, resolved, false_positive
    reviewed_by = db.Column(db.String(100))
    review_notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    reviewed_at = db.Column(db.DateTime(timezone=True))
    
    def __init__(
        self,
        *,
        result_id: str = "",
        task_id: str = "",
        tool_name: str = "",
        tool_version: Optional[str] = None,
        result_type: str = "finding",
        title: str = "",
        description: Optional[str] = None,
        severity: SeverityLevel = SeverityLevel.LOW,
        confidence: Optional[str] = None,
        file_path: Optional[str] = None,
        line_number: Optional[int] = None,
        column_number: Optional[int] = None,
        code_snippet: Optional[str] = None,
        category: Optional[str] = None,
        rule_id: Optional[str] = None,
        tags: Optional[str] = None,
        sarif_level: Optional[str] = None,
        sarif_rule_id: Optional[str] = None,
        sarif_metadata: Optional[str] = None,
        raw_output: Optional[str] = None,
        structured_data: Optional[str] = None,
        recommendations: Optional[str] = None,
        impact_score: Optional[float] = None,
        business_impact: Optional[str] = None,
        remediation_effort: Optional[str] = None,
        status: str = 'new',
        reviewed_by: Optional[str] = None,
        review_notes: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        reviewed_at: Optional[datetime] = None,
        **kwargs: Any
    ) -> None:
        """Initialize AnalysisResult with typed parameters."""
        init_kwargs = {
            'result_id': result_id,
            'task_id': task_id,
            'tool_name': tool_name,
            'tool_version': tool_version,
            'result_type': result_type,
            'title': title,
            'description': description,
            'severity': severity,
            'confidence': confidence,
            'file_path': file_path,
            'line_number': line_number,
            'column_number': column_number,
            'code_snippet': code_snippet,
            'category': category,
            'rule_id': rule_id,
            'tags': tags,
            'sarif_level': sarif_level,
            'sarif_rule_id': sarif_rule_id,
            'sarif_metadata': sarif_metadata,
            'raw_output': raw_output,
            'structured_data': structured_data,
            'recommendations': recommendations,
            'impact_score': impact_score,
            'business_impact': business_impact,
            'remediation_effort': remediation_effort,
            'status': status,
            'reviewed_by': reviewed_by,
            'review_notes': review_notes,
            'created_at': created_at,
            'updated_at': updated_at,
            'reviewed_at': reviewed_at,
            **kwargs
        }
        # Filter out None values that aren't explicitly set
        filtered_kwargs = {k: v for k, v in init_kwargs.items() if v is not None or k in ('description', 'file_path')}
        super().__init__(**filtered_kwargs)
    
    def get_structured_data(self) -> Dict[str, Any]:
        """Get structured data as dictionary."""
        if self.structured_data:
            try:
                return json.loads(self.structured_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_structured_data(self, data_dict: Dict[str, Any]) -> None:
        """Set structured data from dictionary."""
        self.structured_data = json.dumps(data_dict)
    
    def get_recommendations(self) -> List[str]:
        """Get recommendations as list."""
        if self.recommendations:
            try:
                return json.loads(self.recommendations)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_recommendations(self, recommendations_list: List[str]) -> None:
        """Set recommendations from list."""
        self.recommendations = json.dumps(recommendations_list)
    
    def get_tags(self) -> List[str]:
        """Get tags as list."""
        if self.tags:
            try:
                return json.loads(self.tags)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_tags(self, tags_list: List[str]) -> None:
        """Set tags from list."""
        self.tags = json.dumps(tags_list)
    
    def get_sarif_metadata(self) -> Dict[str, Any]:
        """Get SARIF metadata as dictionary."""
        if self.sarif_metadata:
            try:
                return json.loads(self.sarif_metadata)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_sarif_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set SARIF metadata from dictionary."""
        self.sarif_metadata = json.dumps(metadata_dict)
    
    def mark_reviewed(self, reviewer: str, notes: Optional[str] = None) -> None:
        """Mark result as reviewed."""
        self.status = 'reviewed'
        self.reviewed_by = reviewer
        self.reviewed_at = utc_now()
        if notes:
            self.review_notes = notes
    
    def mark_false_positive(self, reviewer: str, notes: Optional[str] = None) -> None:
        """Mark result as false positive."""
        self.status = 'false_positive'
        self.reviewed_by = reviewer
        self.reviewed_at = utc_now()
        if notes:
            self.review_notes = notes
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'result_id': self.result_id,
            'task_id': self.task_id,
            'tool_name': self.tool_name,
            'tool_version': self.tool_version,
            'result_type': self.result_type,
            'title': self.title,
            'description': self.description,
            'severity': self.severity.value if self.severity else None,
            'confidence': self.confidence,
            'file_path': self.file_path,
            'line_number': self.line_number,
            'column_number': self.column_number,
            'code_snippet': self.code_snippet,
            'category': self.category,
            'rule_id': self.rule_id,
            'tags': self.get_tags(),
            'sarif_level': self.sarif_level,
            'sarif_rule_id': self.sarif_rule_id,
            'sarif_metadata': self.get_sarif_metadata(),
            'raw_output': self.raw_output,
            'structured_data': self.get_structured_data(),
            'recommendations': self.get_recommendations(),
            'impact_score': self.impact_score,
            'business_impact': self.business_impact,
            'remediation_effort': self.remediation_effort,
            'status': self.status,
            'reviewed_by': self.reviewed_by,
            'review_notes': self.review_notes,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'reviewed_at': self.reviewed_at
        }
    
    def __repr__(self) -> str:
        return f'<AnalysisResult {self.result_id} ({self.tool_name})>'

class AnalysisIssue:
    pass
