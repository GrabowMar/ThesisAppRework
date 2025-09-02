"""
WebSocket API Routes
Handles WebSocket service status and test functionality.
"""

from pathlib import Path
from flask import Blueprint, request, current_app
from app.extensions import get_websocket_service
from app.routes.response_utils import json_success, json_error
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

# WebSocket API Blueprint
websocket_api_bp = Blueprint('websocket_api', __name__, url_prefix='/api/websocket')


def _find_models_root() -> Path | None:
    """Find the root directory containing model directories."""
    try:
        # Try relative to current working directory
        cwd = Path.cwd()
        models_dir = cwd / 'generated'
        if models_dir.exists() and models_dir.is_dir():
            return models_dir

        # Try relative to Flask app root
        if hasattr(current_app, 'root_path'):
            app_root = Path(current_app.root_path)
            models_dir = app_root.parent / 'generated'
            if models_dir.exists() and models_dir.is_dir():
                return models_dir

        # Try absolute path
        abs_models = Path('generated')
        if abs_models.exists() and abs_models.is_dir():
            return abs_models

        return None
    except Exception as e:
        logger.warning(f"Error finding models root: {e}")
        return None


def _pick_available_model_slug(preferred: list[str] | None = None) -> str | None:
    """Pick an available model slug from the filesystem."""
    root = _find_models_root()
    if not root:
        return None

    def has_app1(p: Path) -> bool:
        return (p / 'app1').exists()

    if preferred:
        for slug in preferred:
            cp = root / slug
            if cp.exists() and cp.is_dir() and has_app1(cp):
                return slug

    for entry in sorted(root.iterdir()):
        try:
            if entry.is_dir() and has_app1(entry):
                return entry.name
        except Exception:
            continue
    return None


@websocket_api_bp.route('/status', methods=['GET'])
def get_websocket_status():
    """Get WebSocket service status."""
    try:
        websocket_service = get_websocket_service()
        if not websocket_service:
            return json_error('WebSocket service not available', status=503)

        status = websocket_service.get_status()
        active_service = 'unknown'
        if isinstance(status, dict):
            active_service = status.get('service') or ('mock_websocket' if status.get('mock_mode') else 'unknown')

        return json_success({
            'data': status,
            'active_service': active_service,
            'strict': bool(current_app.config.get('WEBSOCKET_STRICT_CELERY', False)),
            'preference': current_app.config.get('WEBSOCKET_SERVICE_PREFERENCE', 'auto')
        }, message='WebSocket status retrieved')

    except Exception as e:
        logger.error(f"Error getting WebSocket status: {e}")
        return json_error(str(e), status=500)


@websocket_api_bp.route('/test', methods=['POST'])
def test_websocket():
    """Test WebSocket functionality with a sample analysis."""
    try:
        websocket_service = get_websocket_service()
        if not websocket_service:
            return json_error('WebSocket service not available', status=503)

        payload = request.get_json(silent=True) or {}
        if not payload:
            payload = request.form.to_dict() if request.form else {}

        model_slug = payload.get('model_slug') or request.args.get('model_slug')
        app_number_val = payload.get('app_number') or request.args.get('app_number')

        try:
            app_number = int(app_number_val) if app_number_val is not None else 1
        except (TypeError, ValueError):
            return json_error('app_number must be an integer', status=400)

        if not model_slug:
            preferred_cfg = current_app.config.get('WEBSOCKET_MODEL_PREFERENCE') or []
            if isinstance(preferred_cfg, str):
                preferred_list = [s.strip() for s in preferred_cfg.split(',') if s.strip()]
            else:
                preferred_list = list(preferred_cfg) if isinstance(preferred_cfg, (list, tuple)) else []
            model_slug = _pick_available_model_slug(preferred=preferred_list) or _pick_available_model_slug()

        test_data = {
            'analysis_type': payload.get('analysis_type', 'security'),
            'model_slug': model_slug,
            'app_number': app_number,
            'config': payload.get('config') or {
                'tools': ['static_analysis'],
                'severity': 'medium'
            }
        }

        analysis_id = websocket_service.start_analysis(test_data)

        if analysis_id:
            return json_success({
                'analysis_id': analysis_id,
                'model_slug': model_slug,
                'app_number': app_number
            }, message='Test analysis started - check WebSocket events for progress')
        else:
            return json_error('Failed to start test analysis', status=503,
                            details='WebSocket backend unavailable or task enqueue failed')

    except Exception as e:
        logger.error(f"Error in WebSocket test: {e}")
        msg = str(e).lower()
        if any(tok in msg for tok in [
            'redis', 'connection refused', 'econnrefused', '10061', '111', 'timeout', 'timed out', 'connect', 'refused'
        ]):
            return json_error('WebSocket backend unavailable', status=503, details=str(e))
        return json_error(str(e), status=500)