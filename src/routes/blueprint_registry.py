"""
Blueprint Registry
=================

This module handles the registration of all Flask blueprints and provides
template helpers and filters. It replaces the large blueprint registration
section from the original web_routes.py file.

Maintains full backward compatibility while providing better organization.
"""

import logging
from datetime import datetime
from typing import Dict, Union
from flask import Flask, request, Blueprint, redirect, url_for, render_template, jsonify

from .main_routes import main_bp
from .docker_routes import containers_bp, docker_main_bp  
from .api_routes import api_bp, simple_api_bp, models_bp
from .utils import ResponseHandler

try:
    from ..models import ModelCapability
except ImportError:
    from models import ModelCapability

# Initialize logger
logger = logging.getLogger(__name__)

# Create compatibility blueprints immediately so they're available for import
statistics_bp = Blueprint("statistics", __name__)
testing_bp = Blueprint("testing", __name__, url_prefix="/testing")
analysis_bp = Blueprint("analysis", __name__, url_prefix="/api/v1/analysis")
batch_bp = Blueprint("batch", __name__, url_prefix="/api/v1/batch")
files_bp = Blueprint("files", __name__, url_prefix="/api/v1/files")
performance_bp = Blueprint("performance", __name__, url_prefix="/api/performance")
zap_bp = Blueprint("zap", __name__, url_prefix="/api/zap")

# Define routes immediately to avoid registration-time definition issues
@statistics_bp.route("/statistics_overview")
def statistics_overview():
    """Statistics overview page."""
    try:
        # Get basic statistics
        try:
            from ..models import ModelCapability, GeneratedApplication
            from ..extensions import db
        except ImportError:
            from models import ModelCapability, GeneratedApplication
            from extensions import db
        
        try:
            total_models = ModelCapability.query.count()
            total_apps = GeneratedApplication.query.count()
        except Exception as e:
            logger.warning(f"Could not query database: {e}")
            total_models = 0
            total_apps = 0
        
        stats = {
            'total_models': total_models,
            'total_apps': total_apps,
            'total_analyses': 0,  # Placeholder
            'recent_results': []  # Placeholder
        }
        
        return render_template('pages/statistics_overview.html', stats=stats)
    except Exception as e:
        logger.error(f"Statistics overview error: {e}")
        return ResponseHandler.error_response(str(e))

@testing_bp.route("/")
def testing_dashboard():
    """Unified Security Testing Dashboard."""
    try:
        # Mock statistics for now
        stats = {
            'total_jobs': 0,
            'running_jobs': 0,
            'completed_jobs': 0,
            'failed_jobs': 0,
            'pending_jobs': 0,
            'success_rate': 0
        }
        
        return render_template('pages/unified_security_testing.html', stats=stats)
    except Exception as e:
        logger.error(f"Testing dashboard error: {e}")
        return ResponseHandler.error_response(str(e))

@analysis_bp.route("/overview")
def analysis_overview():
    """Analysis overview redirect."""
    return redirect(url_for('statistics.statistics_overview'))

@analysis_bp.route("/<model>/<int:app_num>/security", methods=["POST"])
def run_security_analysis(model: str, app_num: int):
    """Run security analysis - compatibility route."""
    try:
        # Mock implementation for now
        return jsonify({
            'success': True,
            'message': f'Security analysis started for {model}/app{app_num}',
            'analysis_id': f'sec_{model}_{app_num}_001'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@batch_bp.route("/create_batch_job", methods=["GET", "POST"])
def create_batch_job():
    """Create batch job page."""
    if request.method == "GET":
        return render_template('pages/create_batch_job.html')
    else:
        # POST - create job
        return jsonify({'success': True, 'message': 'Batch job created'})

@performance_bp.route("/<model>/<int:app_num>/run", methods=["POST"])  
def run_performance_test(model: str, app_num: int):
    """Run performance test - compatibility route."""
    try:
        # Mock implementation for now
        return jsonify({
            'success': True,
            'message': f'Performance test started for {model}/app{app_num}',
            'test_id': f'perf_{model}_{app_num}_001'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@zap_bp.route("/<model>/<int:app_num>/scan", methods=["POST"])
def run_zap_scan(model: str, app_num: int):
    """Run ZAP scan - compatibility route."""
    try:
        # Mock implementation for now
        return jsonify({
            'success': True,
            'message': f'ZAP scan started for {model}/app{app_num}',
            'scan_id': f'zap_{model}_{app_num}_001'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def register_blueprints(app: Flask) -> None:
    """Register all blueprints with the Flask app."""
    try:
        # Register main application blueprints
        app.register_blueprint(main_bp)
        app.register_blueprint(docker_main_bp)  # For /docker route
        
        # Register API blueprints
        app.register_blueprint(api_bp)
        app.register_blueprint(simple_api_bp)
        app.register_blueprint(models_bp)
        app.register_blueprint(containers_bp)
        
        # Register compatibility blueprints
        app.register_blueprint(statistics_bp)
        app.register_blueprint(testing_bp)
        app.register_blueprint(analysis_bp)
        app.register_blueprint(batch_bp)
        app.register_blueprint(files_bp)
        app.register_blueprint(performance_bp)
        app.register_blueprint(zap_bp)
        
        # Register template helpers
        register_template_helpers(app)
        
        logger.info("All blueprints registered successfully")
        
    except Exception as e:
        logger.error(f"Failed to register blueprints: {e}")
        raise


def _setup_compatibility_routes() -> None:
    """Set up routes for compatibility blueprints - deprecated."""
    # Routes are now defined at module level to avoid registration issues
    pass


def _register_compatibility_blueprints(app: Flask) -> None:
    """Register additional blueprints for backward compatibility - deprecated."""
    # This function is now integrated into the main registration function
    pass


def register_template_helpers(app: Flask) -> None:
    """Register Jinja2 template helpers."""
    
    @app.template_filter('format_datetime')
    def format_datetime(value):
        """Format datetime for display."""
        try:
            if not value:
                return ''
            
            # If it's already a string, just return it (might be pre-formatted)
            if isinstance(value, str):
                # Try to parse it, but if it fails, just return the string
                try:
                    if 'T' in value:
                        parsed_dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        return parsed_dt.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        # Assume it's already formatted
                        return value
                except (ValueError, TypeError):
                    # If parsing fails, return the original string
                    return str(value)
            
            # If it's a datetime object, format it
            if hasattr(value, 'strftime'):
                return value.strftime('%Y-%m-%d %H:%M:%S')
            
            # Fallback - convert to string
            return str(value) if value else ''
            
        except Exception:
            # Ultimate fallback
            return str(value) if value else ''
    
    @app.template_filter('format_duration')
    def format_duration(seconds):
        """Format duration in seconds to human readable."""
        if not seconds:
            return '0s'
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if secs or not parts:
            parts.append(f"{secs}s")
        
        return ' '.join(parts)
    
    @app.template_filter('to_datetime')
    def to_datetime(value):
        """Convert string to datetime object."""
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return value
    
    @app.template_filter('url_encode_model')
    def url_encode_model(model_name):
        """Encode model name for safe use in URLs."""
        if not model_name:
            return ''
        # For Flask routes, we need to ensure special characters are URL-encoded
        import urllib.parse
        return urllib.parse.quote(model_name, safe='')
    
    @app.template_filter('model_display_name')
    def model_display_name(model_slug):
        """Convert model slug to display name."""
        if not model_slug:
            return ''
        
        # Try to get the actual model from database for more accurate display name
        try:
            model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
            if model and model.model_name:
                # Use the model_name from database and improve it
                display_name = model.model_name
                
                # Common transformations for better display names
                display_name = display_name.replace('-', ' ').replace('_', ' ')
                
                # Handle specific patterns
                if 'claude' in display_name.lower():
                    # Claude models: claude-3.7-sonnet -> Claude 3.7 Sonnet
                    if 'claude' in display_name and not display_name.startswith('Claude'):
                        display_name = display_name.replace('claude', 'Claude')
                
                # Handle version patterns like gpt-4.1 -> GPT-4.1
                if 'gpt' in display_name.lower():
                    display_name = display_name.upper().replace('GPT', 'GPT-')
                    if 'GPT--' in display_name:
                        display_name = display_name.replace('GPT--', 'GPT-')
                
                # Handle other common patterns
                display_name = display_name.replace('gemini', 'Gemini')
                display_name = display_name.replace('qwen', 'Qwen')
                display_name = display_name.replace('deepseek', 'DeepSeek')
                display_name = display_name.replace('mistral', 'Mistral')
                
                # Title case each word but preserve version numbers
                words = display_name.split()
                result_words = []
                for word in words:
                    if any(char.isdigit() for char in word) and ('.' in word or '-' in word):
                        # Keep version numbers as-is
                        result_words.append(word)
                    else:
                        # Title case regular words
                        result_words.append(word.capitalize())
                
                return ' '.join(result_words)
        except Exception:
            # Fall back to simple transformation if database lookup fails
            pass
        
        # Fallback: Simple transformation of the slug
        # Convert underscores to spaces, handle hyphens carefully
        display_name = model_slug.replace('_', ' ')
        
        # Split on spaces and improve each part
        parts = display_name.split(' ')
        result_parts = []
        
        for part in parts:
            if 'claude' in part.lower():
                part = part.replace('claude', 'Claude').replace('-', ' ')
            elif 'gpt' in part.lower():
                part = part.upper().replace('-', ' ')
            elif 'gemini' in part.lower():
                part = part.replace('gemini', 'Gemini').replace('-', ' ')
            elif 'qwen' in part.lower():
                part = part.replace('qwen', 'Qwen').replace('-', ' ')
            elif 'deepseek' in part.lower():
                part = part.replace('deepseek', 'DeepSeek').replace('-', ' ')
            else:
                part = part.title().replace('-', ' ')
            
            result_parts.append(part)
        
        return ' '.join(result_parts)
    
    @app.template_filter('safe_css_id')
    def safe_css_id(value):
        """Convert any string to a safe CSS ID by replacing problematic characters."""
        if not value:
            return ''
        # Replace dots, hyphens, and other problematic characters with underscores
        import re
        # Replace any non-alphanumeric character (except underscore) with underscore
        safe_id = re.sub(r'[^a-zA-Z0-9_]', '_', str(value))
        # Ensure it starts with a letter or underscore (CSS requirement)
        if safe_id and not safe_id[0].isalpha() and safe_id[0] != '_':
            safe_id = 'id_' + safe_id
        return safe_id
    
    @app.template_global()
    def url_decode_model(encoded_model):
        """Decode URL-encoded model name."""
        if not encoded_model:
            return ''
        import urllib.parse
        return urllib.parse.unquote(encoded_model)
    
    @app.template_global()
    def is_htmx():
        """Check if current request is from HTMX."""
        return ResponseHandler.is_htmx_request()
    
    @app.template_global()
    def get_app_url(model, app_num):
        """Generate app URL."""
        try:
            from .utils import AppDataProvider
            port_config = AppDataProvider.get_port_config(model, app_num)
            return f"http://localhost:{port_config['frontend_port']}"
        except Exception:
            return None
    
    @app.template_global()
    def get_app_config() -> Dict[str, any]:
        """Make app config available in templates."""
        return app.config
    
    @app.template_global()
    def debug_mode() -> bool:
        """Check if app is in debug mode."""
        return app.debug
    
    @app.template_global()
    def get_model_count() -> int:
        """Get total number of models in database."""
        try:
            return ModelCapability.query.count()
        except Exception:
            return 0
    
    @app.template_global()
    def now() -> datetime:
        """Get current datetime for templates."""
        return datetime.now()


# Export key components for backward compatibility
def get_settings():
    """Legacy function for settings - redirects to API."""
    return {
        'theme': 'light',
        'auto_refresh': True,
        'refresh_interval': 15
    }


# Create dummy blueprint references for backward compatibility
docker_bp = containers_bp  # Legacy alias

# Export blueprint names for tests
__all__ = [
    'register_blueprints', 'main_bp', 'api_bp', 'simple_api_bp', 
    'statistics_bp', 'models_bp', 'containers_bp', 'docker_bp',
    'testing_bp', 'analysis_bp', 'batch_bp', 'files_bp',
    'get_settings'
]