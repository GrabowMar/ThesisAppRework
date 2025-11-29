from __future__ import annotations
import json
from typing import List
from ..extensions import db
from ..constants import JobStatus
from ..utils.time import utc_now

class BatchAnalysis(db.Model):
    """Model for tracking batch analysis jobs."""
    __tablename__ = 'batch_analyses'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    status = db.Column(db.Enum(JobStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]), default=JobStatus.PENDING, index=True)
    analysis_types = db.Column(db.Text)
    
    total_tasks = db.Column(db.Integer, default=0)
    completed_tasks = db.Column(db.Integer, default=0)
    failed_tasks = db.Column(db.Integer, default=0)
    progress_percentage = db.Column(db.Float, default=0.0)
    
    model_filter = db.Column(db.Text)
    app_filter = db.Column(db.Text)
    
    results_summary = db.Column(db.Text)
    
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    estimated_completion = db.Column(db.DateTime(timezone=True))
    
    config_json = db.Column(db.Text)
    metadata_json = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def get_analysis_types(self) -> List[str]:
        if self.analysis_types:
            try:
                return json.loads(self.analysis_types)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    def set_analysis_types(self, types_list: List[str]) -> None:
        self.analysis_types = json.dumps(types_list)


