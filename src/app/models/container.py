from __future__ import annotations
import json
from typing import Dict, Any
from ..extensions import db
from ..constants import ContainerState
from ..utils.time import utc_now

class ContainerizedTest(db.Model):
    """Model for tracking containerized test services."""
    __tablename__ = 'containerized_tests'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    container_name = db.Column(db.String(200), unique=True, nullable=False, index=True)
    service_type = db.Column(db.String(100), nullable=False)
    
    container_id = db.Column(db.String(100))
    image_name = db.Column(db.String(200))
    port = db.Column(db.Integer)
    status = db.Column(db.String(50), default=ContainerState.STOPPED.value)
    
    last_health_check = db.Column(db.DateTime(timezone=True))
    health_status = db.Column(db.String(50))
    
    total_requests = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime(timezone=True))
    
    config_json = db.Column(db.Text)
    metadata_json = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def get_config(self) -> Dict[str, Any]:
        if self.config_json:
            try:
                return json.loads(self.config_json)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_config(self, config_dict: Dict[str, Any]) -> None:
        self.config_json = json.dumps(config_dict)

    def get_metadata(self) -> Dict[str, Any]:
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        self.metadata_json = json.dumps(metadata_dict)
