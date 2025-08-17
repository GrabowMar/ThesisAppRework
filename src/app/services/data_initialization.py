"""
Data Initialization Service
==========================

Service for loading initial data from JSON files and misc folder into the database.
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from ..extensions import db
from ..models import ModelCapability, GeneratedApplication

logger = logging.getLogger(__name__)


class DataInitializationService:
    """Service for initializing database with data from JSON files and misc folder."""
    
    def __init__(self):
        # Get the project root directory (parent of src)
        current_file = Path(__file__)
        src_path = current_file.parent.parent.parent  # Go up from services -> app -> src
        self.base_path = src_path.parent  # Go up one more to get project root
        self.misc_path = self.base_path / "misc"
        self.models_path = self.misc_path / "models"
        
        logger.info("Data initialization paths:")
        logger.info(f"  Base path: {self.base_path}")
        logger.info(f"  Misc path: {self.misc_path}")
        logger.info(f"  Models path: {self.models_path}")
        
    def initialize_all_data(self) -> Dict[str, Any]:
        """Initialize all data from JSON files and misc folder."""
        results = {
            'models_loaded': 0,
            'applications_loaded': 0,
            'errors': [],
            'success': True,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            # Load model capabilities
            model_results = self.load_model_capabilities()
            results['models_loaded'] = model_results['loaded']
            results['errors'].extend(model_results['errors'])
            
            # Load applications from misc/models folder
            app_results = self.load_applications_from_misc()
            results['applications_loaded'] = app_results['loaded']
            results['errors'].extend(app_results['errors'])
            
            # Commit all changes
            db.session.commit()
            
            logger.info(f"Data initialization completed: {results['models_loaded']} models, {results['applications_loaded']} apps")
            
        except Exception as e:
            logger.error(f"Data initialization failed: {e}")
            db.session.rollback()
            results['success'] = False
            results['errors'].append(f"Critical error: {str(e)}")
            
        return results
    
    def load_model_capabilities(self) -> Dict[str, Any]:
        """Load model capabilities from model_capabilities.json."""
        results = {'loaded': 0, 'errors': []}
        
        try:
            model_caps_file = self.misc_path / "model_capabilities.json"
            if not model_caps_file.exists():
                results['errors'].append("model_capabilities.json not found")
                return results
                
            with open(model_caps_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract models data (handle nested structure)
            models_data = data.get('models', {})
            if isinstance(models_data, dict) and 'models' in models_data:
                models_data = models_data['models']
            
            for model_id, model_info in models_data.items():
                if isinstance(model_info, dict) and 'canonical_slug' in model_info:
                    try:
                        # Check if model already exists
                        existing = ModelCapability.query.filter_by(
                            canonical_slug=model_info['canonical_slug']
                        ).first()
                        
                        if existing:
                            # Update existing model
                            self._update_model_capability(existing, model_info)
                            logger.debug(f"Updated model: {model_info['canonical_slug']}")
                        else:
                            # Create new model
                            self._create_model_capability(model_info)
                            logger.debug(f"Created model: {model_info['canonical_slug']}")
                            
                        results['loaded'] += 1
                        
                    except Exception as e:
                        error_msg = f"Error processing model {model_id}: {str(e)}"
                        results['errors'].append(error_msg)
                        logger.warning(error_msg)
                        
        except Exception as e:
            error_msg = f"Error loading model capabilities: {str(e)}"
            results['errors'].append(error_msg)
            logger.error(error_msg)
            
        return results
    
    def load_applications_from_misc(self) -> Dict[str, Any]:
        """Load applications from misc/models folder structure."""
        results = {'loaded': 0, 'errors': []}
        
        try:
            if not self.models_path.exists():
                results['errors'].append("misc/models folder not found")
                return results
            
            # Iterate through model folders
            for model_folder in self.models_path.iterdir():
                if model_folder.is_dir():
                    model_slug = model_folder.name
                    
                    # Iterate through app folders (app1, app2, etc. OR app_1, app_2, etc.)
                    for app_folder in model_folder.iterdir():
                        if app_folder.is_dir():
                            try:
                                folder_name = app_folder.name
                                app_number = None
                                
                                # Handle both app1, app2... and app_1, app_2... formats
                                if folder_name.startswith('app_'):
                                    try:
                                        app_number = int(folder_name.split('_')[1])
                                    except (ValueError, IndexError):
                                        continue
                                elif folder_name.startswith('app') and folder_name[3:].isdigit():
                                    try:
                                        app_number = int(folder_name[3:])  # Extract number after 'app'
                                    except ValueError:
                                        continue
                                
                                if app_number is not None:
                                    # Check if application already exists
                                    existing = GeneratedApplication.query.filter_by(
                                        model_slug=model_slug,
                                        app_number=app_number
                                    ).first()
                                    
                                    if existing:
                                        # Update existing application
                                        self._update_generated_application(existing, app_folder)
                                    else:
                                        # Create new application
                                        self._create_generated_application(model_slug, app_number, app_folder)
                                        
                                    results['loaded'] += 1
                                    
                            except Exception as e:
                                error_msg = f"Error processing app {app_folder}: {str(e)}"
                                results['errors'].append(error_msg)
                                logger.warning(error_msg)
                                
        except Exception as e:
            error_msg = f"Error loading applications: {str(e)}"
            results['errors'].append(error_msg)
            logger.error(error_msg)
            
        return results
    
    def _create_model_capability(self, model_info: Dict[str, Any]) -> None:
        """Create a new ModelCapability record."""
        # Extract pricing information with proper error handling
        pricing = model_info.get('pricing', {})
        input_price = 0.0
        output_price = 0.0
        
        try:
            # Handle different pricing key formats
            if 'prompt_tokens' in pricing:
                input_price = float(pricing['prompt_tokens'])
            elif 'prompt' in pricing:
                input_price = float(pricing['prompt'])
        except (ValueError, TypeError):
            input_price = 0.0
        
        try:
            if 'completion_tokens' in pricing:
                output_price = float(pricing['completion_tokens'])
            elif 'completion' in pricing:
                output_price = float(pricing['completion'])
        except (ValueError, TypeError):
            output_price = 0.0

        # Create then set attributes to avoid constructor signature issues in static analysis
        model = ModelCapability()
        model.model_id = model_info.get('model_id', '')
        model.canonical_slug = model_info.get('canonical_slug', '')
        model.provider = model_info.get('provider', 'unknown')
        model.model_name = model_info.get('model_name', '')
        model.is_free = bool(model_info.get('is_free', False))
        model.context_window = int(model_info.get('context_window', 0) or 0)
        model.max_output_tokens = int(model_info.get('max_output_tokens', 0) or 0)
        model.supports_function_calling = bool(model_info.get('supports_function_calling', False))
        model.supports_vision = bool(model_info.get('supports_vision', False))
        model.supports_streaming = bool(model_info.get('supports_streaming', False))
        model.supports_json_mode = bool(model_info.get('supports_json_mode', False))
        model.input_price_per_token = float(input_price)
        model.output_price_per_token = float(output_price)
        model.capabilities_json = json.dumps(model_info)
        model.updated_at = datetime.now(timezone.utc)

        db.session.add(model)
    
    def _update_model_capability(self, model: ModelCapability, model_info: Dict[str, Any]) -> None:
        """Update an existing ModelCapability record."""
        model.model_id = model_info.get('model_id', model.model_id)
        model.provider = model_info.get('provider', model.provider)
        model.model_name = model_info.get('model_name', model.model_name)
        model.is_free = model_info.get('is_free', model.is_free)
        model.context_window = model_info.get('context_window', model.context_window)
        model.max_output_tokens = model_info.get('max_output_tokens', model.max_output_tokens)
        model.supports_function_calling = model_info.get('supports_function_calling', model.supports_function_calling)
        model.supports_vision = model_info.get('supports_vision', model.supports_vision)
        model.supports_streaming = model_info.get('supports_streaming', model.supports_streaming)

        # Update pricing with flexible key handling
        pricing = model_info.get('pricing', {}) or {}
        try:
            prompt_price = pricing.get('prompt')
            if prompt_price is None:
                prompt_price = pricing.get('prompt_tokens')
            if prompt_price is not None:
                model.input_price_per_token = float(prompt_price)
        except (TypeError, ValueError):
            # Keep existing value on parse error
            pass

        try:
            completion_price = pricing.get('completion')
            if completion_price is None:
                completion_price = pricing.get('completion_tokens')
            if completion_price is not None:
                model.output_price_per_token = float(completion_price)
        except (TypeError, ValueError):
            # Keep existing value on parse error
            pass

        model.capabilities_json = json.dumps(model_info)
        model.updated_at = datetime.now(timezone.utc)
    
    def _create_generated_application(self, model_slug: str, app_number: int, app_folder: Path) -> None:
        """Create a new GeneratedApplication record."""
        # Analyze folder structure to determine frameworks and capabilities
        analysis = self._analyze_app_folder(app_folder)

        # Get model info for provider
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        provider = model.provider if model else model_slug.split('_')[0]

        # Create then set attributes to avoid constructor signature issues
        app = GeneratedApplication()
        app.model_slug = model_slug
        app.app_number = app_number
        app.app_type = 'web_application'
        app.provider = provider
        app.has_backend = analysis['has_backend']
        app.has_frontend = analysis['has_frontend']
        app.has_docker_compose = analysis['has_docker_compose']
        app.backend_framework = analysis['backend_framework']
        app.frontend_framework = analysis['frontend_framework']
        app.container_status = 'unknown'
        app.updated_at = datetime.now(timezone.utc)

        db.session.add(app)
    
    def _update_generated_application(self, app: GeneratedApplication, app_folder: Path) -> None:
        """Update an existing GeneratedApplication record."""
        analysis = self._analyze_app_folder(app_folder)

        app.has_backend = analysis['has_backend']
        app.has_frontend = analysis['has_frontend']
        app.has_docker_compose = analysis['has_docker_compose']
        app.backend_framework = analysis['backend_framework']
        app.frontend_framework = analysis['frontend_framework']
        app.updated_at = datetime.now(timezone.utc)
    
    def _analyze_app_folder(self, app_folder: Path) -> Dict[str, Any]:
        """Analyze app folder structure to determine capabilities."""
        analysis = {
            'has_backend': False,
            'has_frontend': False,
            'has_docker_compose': False,
            'backend_framework': None,
            'frontend_framework': None
        }
        
        # Check for common files
        files = [f.name.lower() for f in app_folder.rglob('*') if f.is_file()]
        
        # Check for Docker Compose
        analysis['has_docker_compose'] = any(
            'docker-compose' in f for f in files
        )
        
        # Check for backend frameworks
        if any('requirements.txt' in f or 'main.py' in f or 'app.py' in f for f in files):
            analysis['has_backend'] = True
            analysis['backend_framework'] = 'Flask'  # Default assumption
            
        if any('package.json' in f for f in files):
            if not analysis['has_backend']:
                analysis['has_backend'] = True
                analysis['backend_framework'] = 'Node.js'
            else:
                analysis['has_frontend'] = True
                analysis['frontend_framework'] = 'React'
        
        # Check for frontend indicators
        if any('index.html' in f or 'src/' in str(f) for f in files):
            analysis['has_frontend'] = True
            if not analysis['frontend_framework']:
                analysis['frontend_framework'] = 'HTML/JS'
                
        return analysis
    
    def get_initialization_status(self) -> Dict[str, Any]:
        """Get current initialization status."""
        return {
            'models_count': ModelCapability.query.count(),
            'applications_count': GeneratedApplication.query.count(),
            'last_model_update': self._get_last_model_update(),
            'misc_folder_exists': self.models_path.exists(),
            'model_capabilities_file_exists': (self.misc_path / "model_capabilities.json").exists()
        }
    
    def _get_last_model_update(self) -> Optional[str]:
        """Get timestamp of last model update."""
        latest = ModelCapability.query.order_by(
            ModelCapability.updated_at.desc()
        ).first()
        return latest.updated_at.isoformat() if latest and latest.updated_at else None


# Create global instance
data_init_service = DataInitializationService()
