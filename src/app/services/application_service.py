"""Application Service Layer
===========================

Encapsulates business logic for GeneratedApplication entities to keep route
handlers thin and focused on HTTP concerns.

Design Goals:
- Provide clear, testable functions for CRUD + status operations
- Centralize validation rules and defaults
- Return plain Python data structures (dict) ready for json_success
- Raise custom exceptions for error cases; route layer maps to HTTP

Future Enhancements:
- Integrate schema validation (Pydantic / Marshmallow)
- Add caching for list endpoints
- Introduce repository pattern if database logic grows complex
"""
from __future__ import annotations

from typing import Optional, Dict, Any
from sqlalchemy.orm import Query

from ..models import GeneratedApplication
from ..extensions import db
from ..constants import AnalysisStatus
from .service_base import NotFoundError, ValidationError
from ..utils.time import utc_now

# Exceptions now provided by service_base (NotFoundError, ValidationError)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_CREATE_FIELDS = ['model_slug', 'app_number', 'app_type', 'provider']
OPTIONAL_FIELDS = [
    'has_backend', 'has_frontend', 'has_docker_compose', 'backend_framework',
    'frontend_framework', 'container_status'
]
UPDATABLE_FIELDS = REQUIRED_CREATE_FIELDS + OPTIONAL_FIELDS + ['generation_status']

# ---------------------------------------------------------------------------
# Core Operations
# ---------------------------------------------------------------------------

def list_applications(*, status: Optional[str]=None, app_type: Optional[str]=None) -> Query:
    query = GeneratedApplication.query
    if status:
        query = query.filter(GeneratedApplication.generation_status == status)
    if app_type:
        query = query.filter(GeneratedApplication.app_type == app_type)
    return query.order_by(GeneratedApplication.created_at.desc())

def create_application(data: Dict[str, Any]) -> Dict[str, Any]:
    missing = [f for f in REQUIRED_CREATE_FIELDS if f not in data]
    if missing:
        raise ValidationError(f"Missing required fields: {', '.join(missing)}")

    app = GeneratedApplication()
    app.model_slug = data['model_slug']
    app.app_number = data['app_number']
    app.app_type = data['app_type']
    app.provider = data['provider']
    app.generation_status = data.get('generation_status', AnalysisStatus.PENDING)

    for field in OPTIONAL_FIELDS:
        if field in data:
            setattr(app, field, data[field])

    db.session.add(app)
    db.session.commit()
    return app.to_dict()

def get_application(app_id: int) -> Dict[str, Any]:
    app = db.session.get(GeneratedApplication, app_id)
    if not app:
        raise NotFoundError("Application not found")
    return app.to_dict()

def update_application(app_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    app = db.session.get(GeneratedApplication, app_id)
    if not app:
        raise NotFoundError("Application not found")
    for field in UPDATABLE_FIELDS:
        if field in data:
            setattr(app, field, data[field])
    if 'metadata' in data:
        app.set_metadata(data['metadata'])
    db.session.commit()
    return app.to_dict()

def delete_application(app_id: int) -> None:
    app = db.session.get(GeneratedApplication, app_id)
    if not app:
        raise NotFoundError("Application not found")
    db.session.delete(app)
    db.session.commit()

def start_application(app_id: int) -> Dict[str, Any]:
    app = db.session.get(GeneratedApplication, app_id)
    if not app:
        raise NotFoundError("Application not found")
    app.update_container_status('running')
    db.session.commit()
    return {"app_id": app_id, "status": app.container_status}

def stop_application(app_id: int) -> Dict[str, Any]:
    app = db.session.get(GeneratedApplication, app_id)
    if not app:
        raise NotFoundError("Application not found")
    app.update_container_status('stopped')
    db.session.commit()
    return {"app_id": app_id, "status": app.container_status}

def restart_application(app_id: int) -> Dict[str, Any]:
    app = db.session.get(GeneratedApplication, app_id)
    if not app:
        raise NotFoundError("Application not found")
    app.update_container_status('running')
    db.session.commit()
    return {"app_id": app_id, "status": app.container_status}

# ---------------------------------------------------------------------------
# Model-wide operations
# ---------------------------------------------------------------------------

def start_model_containers(model_slug: str) -> Dict[str, Any]:
    """Start all containers for a given model slug.

    Returns dict with counts; does not raise NotFound if zero (caller can decide).
    """
    apps = GeneratedApplication.query.filter_by(model_slug=model_slug).all()
    started = 0
    for app in apps:
        if app.container_status != 'running':
            app.update_container_status('running')
            started += 1
    db.session.commit()
    return {"model_slug": model_slug, "affected": len(apps), "started": started}

def stop_model_containers(model_slug: str) -> Dict[str, Any]:
    """Stop all running containers for a given model slug."""
    apps = GeneratedApplication.query.filter_by(model_slug=model_slug).all()
    stopped = 0
    for app in apps:
        if app.container_status == 'running':
            app.update_container_status('stopped')
            stopped += 1
    db.session.commit()
    return {"model_slug": model_slug, "affected": len(apps), "stopped": stopped}

def refresh_all_application_statuses() -> Dict[str, Any]:
    """Refresh all application container statuses from Docker and update database.
    
    Returns summary of refresh operation including number of apps updated.
    """
    from ..extensions import db
    from .service_locator import ServiceLocator
    from typing import cast, TYPE_CHECKING
    
    if TYPE_CHECKING:
        from .docker_manager import DockerManager
    
    # Get all applications from database
    apps = GeneratedApplication.query.all()
    total_count = len(apps)
    updated_count = 0
    error_count = 0
    
    # Get docker manager
    docker_mgr = ServiceLocator.get_docker_manager()
    if not docker_mgr:
        raise RuntimeError("Docker manager unavailable")
    
    # Cast to proper type for method access
    docker_mgr = cast('DockerManager', docker_mgr)
    
    for app in apps:
        try:
            # Get real Docker status
            status_summary = docker_mgr.container_status_summary(app.model_slug, app.app_number)
            states = status_summary.get('states', [])
            
            # Determine actual status
            if any(s.lower() == 'running' for s in states):
                new_status = 'running'
            elif states:  # Has containers but not running
                new_status = 'stopped'
            else:  # No containers
                # Check if compose file exists
                preflight = docker_mgr.compose_preflight(app.model_slug, app.app_number)
                if preflight.get('compose_file_exists'):
                    new_status = 'not_created'
                else:
                    new_status = 'no_compose'
            
            # Update if status changed
            if app.container_status != new_status:
                app.update_container_status(new_status)
                updated_count += 1
            else:
                # Update timestamp even if status didn't change
                app.last_status_check = utc_now()
                
        except Exception as e:
            error_count += 1
            # Log error but continue with other apps
            print(f"Error checking status for {app.model_slug}/app{app.app_number}: {e}")
    
    # Commit all changes
    db.session.commit()
    
    return {
        "total_checked": total_count,
        "updated": updated_count,
        "errors": error_count,
        "timestamp": db.session.query(db.func.now()).scalar()
    }

__all__ = [
    'NotFoundError', 'ValidationError',
    'list_applications', 'create_application', 'get_application',
    'update_application', 'delete_application',
    'start_application', 'stop_application', 'restart_application',
    'start_model_containers', 'stop_model_containers',
    'refresh_all_application_statuses'
]
