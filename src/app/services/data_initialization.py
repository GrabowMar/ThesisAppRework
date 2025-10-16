"""
Data Initialization Service
==========================

Service for loading initial data from JSON files and misc folder into the database.
"""

import json
from app.utils.logging_config import get_logger
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from ..extensions import db
from ..models import ModelCapability, GeneratedApplication, PortConfiguration
from flask import current_app

logger = get_logger('data_init')


class DataInitializationService:
    """Service for initializing database with data from JSON files and misc folder."""
    
    def __init__(self):
        # Determine project root and prefer project-root based misc/ and generated/ directories
        current_file = Path(__file__)
        src_path = current_file.parent.parent.parent  # Go up from services -> app -> src
        self.base_path = src_path.parent  # Go up one more to get project root
        self.misc_path = self.base_path / "misc"
        self.models_path = self.base_path / "generated" / "apps"
        
        logger.info("Data initialization paths:")
        logger.info(f"  Base path: {self.base_path}")
        logger.info(f"  Misc path: {self.misc_path}")
        logger.info(f"  Models path: {self.models_path}")
        
    def initialize_all_data(self) -> Dict[str, Any]:
        """Initialize all data from JSON files and misc folder."""
        results = {
            'models_loaded': 0,
            'openrouter_models_loaded': 0,
            'applications_loaded': 0,
            'ports_loaded': 0,
            'errors': [],
            'success': True,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            # Load model capabilities (includes OpenRouter API fallback)
            model_results = self.load_model_capabilities()
            results['models_loaded'] = model_results['loaded']
            results['openrouter_models_loaded'] = model_results.get('openrouter_loaded', 0)
            results['errors'].extend(model_results['errors'])
            
            # Load applications from generated folder
            app_results = self.load_applications_from_generated()
            results['applications_loaded'] = app_results['loaded']
            results['errors'].extend(app_results['errors'])
            
            # Load port configurations
            port_results = self.load_port_config()
            results['ports_loaded'] = port_results['created'] + port_results['updated']
            results['errors'].extend(port_results['errors'])
            
            # Commit all changes
            db.session.commit()
            
            total_models = results['models_loaded'] + results['openrouter_models_loaded']
            logger.info(f"Data initialization completed: {total_models} models ({results['models_loaded']} from file, {results['openrouter_models_loaded']} from OpenRouter), {results['applications_loaded']} apps, {results['ports_loaded']} ports")
            
        except Exception as e:
            logger.error(f"Data initialization failed: {e}")
            db.session.rollback()
            results['success'] = False
            results['errors'].append(f"Critical error: {str(e)}")
            
        return results

    def reload_core_files(self) -> Dict[str, Any]:
        """Reload core JSON files: models_summary.json, port_config.json.

        Returns a structured result with per-file stats and overall success flag.
        """
        results: Dict[str, Any] = {
            'success': True,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'models_summary': {},
            'port_config': {},
            'errors': []
        }

        try:
            summary_res = self.load_models_summary()
            results['models_summary'] = summary_res
            if summary_res.get('errors'):
                results['errors'].extend(summary_res['errors'])

            port_res = self.load_port_config()
            results['port_config'] = port_res
            if port_res.get('errors'):
                results['errors'].extend(port_res['errors'])

            db.session.commit()
        except Exception as e:
            logger.error(f"Core files reload failed: {e}")
            db.session.rollback()
            results['success'] = False
            results['errors'].append(f"Critical error: {str(e)}")

        return results
    
    def load_model_capabilities(self) -> Dict[str, Any]:
        """Load model capabilities from OpenRouter API."""
        results = {'loaded': 0, 'openrouter_loaded': 0, 'errors': []}
        
        # Check if we need to load models from OpenRouter API
        current_model_count = ModelCapability.query.count()
        if current_model_count < 10:  # Arbitrary threshold - if we have less than 10 models, fetch from API
            try:
                import os
                from flask import current_app
                
                api_key = os.getenv('OPENROUTER_API_KEY') or current_app.config.get('OPENROUTER_API_KEY')
                if api_key:
                    logger.info("Loading models from OpenRouter API due to insufficient local models")
                    openrouter_result = self._load_from_openrouter_api(api_key)
                    results['openrouter_loaded'] = openrouter_result['loaded']
                    results['errors'].extend(openrouter_result['errors'])
                else:
                    logger.info("OpenRouter API key not configured, skipping API fetch")
            except Exception as e:
                error_msg = f"Error loading from OpenRouter API: {str(e)}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
        else:
            logger.info(f"Sufficient models already loaded ({current_model_count}), skipping OpenRouter API fetch")
            
        return results
    
    def _load_from_openrouter_api(self, api_key: str) -> Dict[str, Any]:
        """Load models from OpenRouter API."""
        results = {'loaded': 0, 'errors': []}
        
        try:
            import requests
            from ..routes.shared_utils import _upsert_openrouter_models
            
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            logger.info("Fetching models from OpenRouter API...")
            response = requests.get('https://openrouter.ai/api/v1/models', headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                models_data = data.get('data', [])
                logger.info(f"Fetched {len(models_data)} models from OpenRouter API")
                
                # Upsert models using the existing utility function
                upserted_count = _upsert_openrouter_models(models_data)
                results['loaded'] = upserted_count
                logger.info(f"Successfully upserted {upserted_count} models from OpenRouter API")
                
            else:
                error_msg = f"OpenRouter API returned status {response.status_code}: {response.text[:200]}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
                
        except Exception as e:
            error_msg = f"Failed to fetch from OpenRouter API: {str(e)}"
            results['errors'].append(error_msg)
            logger.error(error_msg)
            
        return results
    
    def load_applications_from_generated(self) -> Dict[str, Any]:
        """Load applications from the generated/apps folder structure."""
        results = {'loaded': 0, 'errors': []}
        
        try:
            if not self.models_path.exists():
                results['errors'].append("generated/apps folder not found")
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

    def load_models_summary(self) -> Dict[str, Any]:
        """Load models summary from models_summary.json and update metadata (e.g., color)."""
        results: Dict[str, Any] = {'loaded': 0, 'updated': 0, 'errors': []}

        try:
            summary_file = self.misc_path / "models_summary.json"
            if not summary_file.exists():
                results['errors'].append("models_summary.json not found")
                return results

            with open(summary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            models_list = data.get('models', []) or []
            for entry in models_list:
                name = entry.get('name')
                if not name:
                    continue

                try:
                    model = ModelCapability.query.filter_by(canonical_slug=name).first()
                    if not model:
                        # Try by model_id as a fallback
                        model = ModelCapability.query.filter_by(model_id=name).first()

                    if model:
                        # Merge metadata: keep existing fields, update color/provider hints
                        metadata = model.get_metadata() or {}
                        # Only set color/provider if provided
                        if 'color' in entry and entry['color']:
                            metadata['color'] = entry['color']
                        if 'provider' in entry and entry['provider']:
                            metadata['summary_provider'] = entry['provider']
                        metadata['summary_last_loaded'] = datetime.now(timezone.utc).isoformat()
                        model.set_metadata(metadata)
                        model.updated_at = datetime.now(timezone.utc)
                        results['updated'] += 1
                    # Count entries processed
                    results['loaded'] += 1
                except Exception as e:
                    err = f"Error processing summary for {name}: {str(e)}"
                    results['errors'].append(err)
                    logger.warning(err)

        except Exception as e:
            err = f"Error loading models summary: {str(e)}"
            results['errors'].append(err)
            logger.error(err)

        return results

    def load_port_config(self) -> Dict[str, Any]:
        """Load port configurations from port_config.json into PortConfiguration table (upsert)."""
        results: Dict[str, Any] = {'loaded': 0, 'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}

        try:
            port_file = self.misc_path / "port_config.json"
            if not port_file.exists():
                results['errors'].append("port_config.json not found")
                return results

            with open(port_file, 'r', encoding='utf-8') as f:
                entries = json.load(f)

            if not isinstance(entries, list):
                results['errors'].append("port_config.json must be a list of objects")
                return results

            # Track used ports to detect duplicates
            used_backend_ports = set()
            used_frontend_ports = set()
            
            # Pre-load existing ports from database
            existing_ports = db.session.query(PortConfiguration).all()
            for existing in existing_ports:
                used_backend_ports.add(existing.backend_port)
                used_frontend_ports.add(existing.frontend_port)

            for entry in entries:
                try:
                    model_name = entry.get('model_name') or entry.get('model')
                    app_number = int(entry.get('app_number'))
                    backend_port = int(entry.get('backend_port'))
                    frontend_port = int(entry.get('frontend_port'))

                    if not model_name:
                        continue

                    # Normalize model name: convert / to _ for database storage
                    normalized_model = model_name.replace('/', '_')

                    # Check for port conflicts
                    if backend_port in used_backend_ports:
                        results['errors'].append(f"Duplicate backend_port {backend_port} for {normalized_model}/app{app_number} - skipping")
                        results['skipped'] += 1
                        continue
                        
                    if frontend_port in used_frontend_ports:
                        results['errors'].append(f"Duplicate frontend_port {frontend_port} for {normalized_model}/app{app_number} - skipping")
                        results['skipped'] += 1
                        continue

                    existing = PortConfiguration.query.filter_by(model=normalized_model, app_num=app_number).first()
                    if existing:
                        # Update ports if changed
                        changed = False
                        if existing.backend_port != backend_port:
                            # Remove old port from tracking
                            used_backend_ports.discard(existing.backend_port)
                            existing.backend_port = backend_port
                            changed = True
                        if existing.frontend_port != frontend_port:
                            # Remove old port from tracking
                            used_frontend_ports.discard(existing.frontend_port)
                            existing.frontend_port = frontend_port
                            changed = True
                        if changed:
                            existing.updated_at = datetime.now(timezone.utc)
                            results['updated'] += 1
                        
                        # Add ports to tracking (whether changed or not)
                        used_backend_ports.add(existing.backend_port)
                        used_frontend_ports.add(existing.frontend_port)
                    else:
                        pc = PortConfiguration()
                        pc.model = normalized_model
                        pc.app_num = app_number
                        pc.backend_port = backend_port
                        pc.frontend_port = frontend_port
                        pc.is_available = True
                        pc.updated_at = datetime.now(timezone.utc)
                        db.session.add(pc)
                        results['created'] += 1
                        
                        # Add ports to tracking
                        used_backend_ports.add(backend_port)
                        used_frontend_ports.add(frontend_port)

                    results['loaded'] += 1
                except Exception as e:
                    err = f"Error processing port entry {entry}: {str(e)}"
                    results['errors'].append(err)
                    logger.warning(err)

        except Exception as e:
            err = f"Error loading port configurations: {str(e)}"
            results['errors'].append(err)
            logger.error(err)

        return results
    
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
            'port_config_count': PortConfiguration.query.count(),
            'last_model_update': self._get_last_model_update(),
            'apps_folder_exists': self.models_path.exists(),
            'models_summary_file_exists': (self.misc_path / "models_summary.json").exists(),
            'port_config_file_exists': (self.misc_path / "port_config.json").exists()
        }
    
    def _get_last_model_update(self) -> Optional[str]:
        """Get timestamp of last model update."""
        latest = ModelCapability.query.order_by(
            ModelCapability.updated_at.desc()
        ).first()
        return latest.updated_at.isoformat() if latest and latest.updated_at else None

    def mark_installed_models(self, reset_first: bool = True) -> Dict[str, Any]:
        """Scan the generated/apps folder and set ModelCapability.installed=True for matching slugs.

        Returns a dict with success, updated count, and scanned_folders count or errors on failure.
        """
        results = {'success': True, 'updated': 0, 'scanned_folders': 0, 'errors': [], 'openrouter_enriched': 0}
        try:
            if not self.models_path.exists():
                results.update({'success': False, 'errors': ['generated/apps folder not found']})
                return results

            dirs = [d.name for d in self.models_path.iterdir() if d.is_dir()]
            results['scanned_folders'] = len(dirs)

            if reset_first:
                try:
                    db.session.query(ModelCapability).update({ModelCapability.installed: False})
                    db.session.flush()
                except Exception:
                    db.session.rollback()

            updated = 0
            for d in dirs:
                try:
                    m = ModelCapability.query.filter_by(canonical_slug=d).first()
                    if m and not m.installed:
                        m.installed = True
                        updated += 1
                except Exception as e:
                    results['errors'].append(f"Error marking {d}: {str(e)}")

            # Enrichment
            enriched = 0
            try:
                from app.services.openrouter_service import OpenRouterService
                ors = OpenRouterService()
                if ors.api_key:
                    raw_models = ors.fetch_all_models() or []
                    index: dict[str, dict] = {}
                    for rm in raw_models:
                        if not isinstance(rm, dict):
                            continue
                        mid = rm.get('id')
                        if not mid:
                            continue
                        index[mid] = rm
                        if ':' in mid:
                            base_mid = mid.split(':', 1)[0]
                            index.setdefault(base_mid, rm)
                    installed_models = ModelCapability.query.filter_by(installed=True).all()
                    for m in installed_models:
                        try:
                            if '_' not in m.canonical_slug:
                                continue
                            provider, rest = m.canonical_slug.split('_', 1)
                            candidate_ids = [f"{provider}/{rest}"]
                            if ':' in candidate_ids[0]:
                                candidate_ids.append(candidate_ids[0].split(':', 1)[0])
                            raw = None
                            for cid in candidate_ids:
                                raw = index.get(cid)
                                if raw:
                                    break
                            if not raw:
                                continue
                            pricing = raw.get('pricing') or {}
                            try:
                                p_prompt = float(pricing.get('prompt') or pricing.get('prompt_tokens') or 0)
                                m.input_price_per_token = p_prompt if p_prompt <= 5 else p_prompt / 1000.0
                            except Exception:
                                pass
                            try:
                                p_comp = float(pricing.get('completion') or pricing.get('completion_tokens') or 0)
                                m.output_price_per_token = p_comp if p_comp <= 5 else p_comp / 1000.0
                            except Exception:
                                pass
                            ctx = raw.get('context_length') or (raw.get('top_provider') or {}).get('context_length')
                            if ctx:
                                try:
                                    m.context_window = int(ctx)
                                except Exception:
                                    pass
                            max_out = (raw.get('top_provider') or {}).get('max_completion_tokens')
                            if max_out:
                                try:
                                    m.max_output_tokens = int(max_out)
                                except Exception:
                                    pass
                            m.supports_function_calling = bool(raw.get('supports_tool_calls'))
                            m.supports_json_mode = bool(raw.get('supports_json_mode'))
                            m.supports_streaming = bool(raw.get('supports_streaming'))
                            m.supports_vision = bool(raw.get('supports_vision'))
                            m.is_free = (
                                (pricing.get('prompt') in (0, '0', '0.0', None, '')) and
                                (pricing.get('completion') in (0, '0', '0.0', None, ''))
                            )
                            arch = raw.get('architecture') or {}
                            caps: list[str] = []
                            for key in ('modality', 'input_modalities', 'output_modalities'):
                                val = arch.get(key)
                                if isinstance(val, str):
                                    caps.append(val)
                                elif isinstance(val, list):
                                    caps.extend([v for v in val if v])
                            caps_dict = {
                                'capabilities': list({c for c in caps if c}),
                                'supports_tool_calls': raw.get('supports_tool_calls'),
                                'supports_json_mode': raw.get('supports_json_mode'),
                                'supports_streaming': raw.get('supports_streaming'),
                                'supports_vision': raw.get('supports_vision')
                            }
                            try:
                                m.set_capabilities(caps_dict)
                            except Exception:
                                pass
                            meta_subset = {
                                'openrouter_id': raw.get('id'),
                                'openrouter_name': raw.get('name'),
                                'openrouter_canonical_slug': raw.get('canonical_slug'),
                                'openrouter_description': raw.get('description'),
                                'openrouter_top_provider': raw.get('top_provider'),
                                'openrouter_architecture': raw.get('architecture'),
                                'openrouter_pricing': pricing,
                                'openrouter_variants': raw.get('variants') or raw.get('static_variants')
                            }
                            try:
                                existing_meta = m.get_metadata()
                                existing_meta.update({k: v for k, v in meta_subset.items() if v is not None})
                                m.set_metadata(existing_meta)
                            except Exception:
                                pass
                            enriched += 1
                        except Exception:
                            continue
                else:
                    current_app.logger.info('OpenRouter enrichment skipped: API key missing')
            except Exception as _e:
                current_app.logger.warning(f'OpenRouter enrichment failure: {_e}')
            results['openrouter_enriched'] = enriched
            db.session.commit()
            results['updated'] = updated
            return results
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            results.update({'success': False, 'errors': [str(e)]})
            return results


# Create global instance
data_init_service = DataInitializationService()
