from __future__ import annotations
import json
from typing import Dict, Any
from ..extensions import db
from ..utils.time import utc_now

class ProcessTracking(db.Model):
    """Track running processes to replace PID files."""
    __tablename__ = 'process_tracking'
    
    id = db.Column(db.Integer, primary_key=True)
    service_name = db.Column(db.String(100), nullable=False, index=True)
    service_type = db.Column(db.String(50), nullable=False, index=True)
    process_id = db.Column(db.Integer, nullable=False)
    
    status = db.Column(db.String(20), default='running', index=True)
    host = db.Column(db.String(100), default='localhost')
    port = db.Column(db.Integer)
    
    command_line = db.Column(db.Text)
    working_directory = db.Column(db.String(500))
    environment_info_json = db.Column(db.Text)
    
    last_heartbeat = db.Column(db.DateTime(timezone=True), default=utc_now)
    resource_usage_json = db.Column(db.Text)
    
    started_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    stopped_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def get_environment_info(self) -> Dict[str, Any]:
        if self.environment_info_json:
            try:
                return json.loads(self.environment_info_json)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_environment_info(self, info: Dict[str, Any]) -> None:
        self.environment_info_json = json.dumps(info)

    def get_resource_usage(self) -> Dict[str, Any]:
        """Get resource usage statistics."""
        if self.resource_usage_json:
            try:
                return json.loads(self.resource_usage_json)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_resource_usage(self, usage: Dict[str, Any]) -> None:
        """Set resource usage statistics."""
        self.resource_usage_json = json.dumps(usage)


