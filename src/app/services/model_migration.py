"""
Model Database Migration Service
=================================

Permanent service for migrating and fixing model IDs in the database.
Replaces one-time scripts with maintainable service layer.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ModelMigrationService:
    """Service for migrating and fixing model database records."""
    
    def __init__(self, db_session: Optional[Session] = None):
        """Initialize migration service.
        
        Args:
            db_session: SQLAlchemy database session (optional, will use app context if not provided)
        """
        self.db = db_session
        
    def normalize_provider_namespaces(self, dry_run: bool = True) -> Dict[str, Any]:
        """Normalize provider namespaces for all models in database.
        
        Uses ModelValidator.PROVIDER_NAMESPACE_MAP to correct organization names
        to OpenRouter provider names.
        
        Args:
            dry_run: If True, only report changes without applying them
            
        Returns:
            Dict with 'fixed', 'skipped', 'errors' counts and details
        """
        from app.models import ModelCapability
        from app.services.model_validator import get_validator
        
        validator = get_validator()
        validator.refresh_catalog(force=True)
        
        fixed = []
        skipped = []
        errors = []
        
        # Get all models from database
        models = ModelCapability.query.all()
        
        for model in models:
            try:
                # Get current OpenRouter ID (same priority as generation service)
                old_id = model.hugging_face_id or model.base_model_id or model.model_id
                
                if not old_id:
                    skipped.append({
                        'slug': model.canonical_slug,
                        'reason': 'No model ID found'
                    })
                    continue
                
                # Try to normalize provider namespace
                normalized_id = validator.normalize_provider_namespace(old_id)
                
                # Check if normalization changed the ID
                if normalized_id == old_id.lower():
                    # Only case change, no provider namespace change
                    skipped.append({
                        'slug': model.canonical_slug,
                        'old_id': old_id,
                        'reason': 'Already correct provider namespace'
                    })
                    continue
                
                # Check if normalized ID is valid in OpenRouter
                if not validator.is_valid_model_id(normalized_id):
                    # Try suggestion as fallback
                    suggestion = validator.suggest_correction(old_id)
                    if suggestion:
                        suggested_id, reason = suggestion
                        normalized_id = suggested_id
                    else:
                        errors.append({
                            'slug': model.canonical_slug,
                            'old_id': old_id,
                            'attempted_id': normalized_id,
                            'reason': 'Normalized ID not found in OpenRouter catalog'
                        })
                        continue
                
                # Record the fix
                fix_record = {
                    'slug': model.canonical_slug,
                    'old_id': old_id,
                    'new_id': normalized_id,
                    'field': 'hugging_face_id' if model.hugging_face_id else ('base_model_id' if model.base_model_id else 'model_id')
                }
                fixed.append(fix_record)
                
                # Apply fix if not dry run
                if not dry_run:
                    if model.hugging_face_id:
                        model.hugging_face_id = normalized_id
                    elif model.base_model_id:
                        model.base_model_id = normalized_id
                    else:
                        model.model_id = normalized_id
                    
                    logger.info(f"Fixed {model.canonical_slug}: {old_id} → {normalized_id}")
                
            except Exception as e:
                logger.error(f"Error processing {model.canonical_slug}: {e}", exc_info=True)
                errors.append({
                    'slug': model.canonical_slug,
                    'error': str(e)
                })
        
        # Commit changes if not dry run
        if not dry_run and fixed:
            try:
                if self.db:
                    self.db.commit()
                else:
                    from app.extensions import db
                    db.session.commit()
                logger.info(f"Committed {len(fixed)} model ID fixes to database")
            except Exception as e:
                logger.error(f"Failed to commit changes: {e}", exc_info=True)
                if self.db:
                    self.db.rollback()
                else:
                    from app.extensions import db
                    db.session.rollback()
                return {
                    'fixed': [],
                    'skipped': skipped,
                    'errors': errors + [{'error': f'Commit failed: {e}'}],
                    'summary': {
                        'total': len(models),
                        'fixed': 0,
                        'skipped': len(skipped),
                        'errors': len(errors) + 1
                    }
                }
        
        return {
            'fixed': fixed,
            'skipped': skipped,
            'errors': errors,
            'summary': {
                'total': len(models),
                'fixed': len(fixed),
                'skipped': len(skipped),
                'errors': len(errors),
                'dry_run': dry_run
            }
        }
    
    def validate_and_fix_all_models(self, dry_run: bool = True, auto_fix: bool = True) -> Dict:
        """Validate all models and optionally fix invalid ones.
        
        This is the comprehensive fix-all method that:
        1. Validates all models against OpenRouter catalog
        2. Normalizes provider namespaces
        3. Applies fuzzy-matched corrections
        4. Reports unfixable issues
        
        Args:
            dry_run: If True, only report changes without applying them
            auto_fix: If True, automatically apply suggested corrections
            
        Returns:
            Dict with validation results and applied fixes
        """
        from app.models import ModelCapability
        from app.services.model_validator import get_validator
        
        validator = get_validator()
        validator.refresh_catalog(force=True)
        
        valid = []
        invalid = []
        fixed = []
        unfixable = []
        
        models = ModelCapability.query.all()
        
        for model in models:
            old_id = model.hugging_face_id or model.base_model_id or model.model_id
            
            if not old_id:
                unfixable.append({
                    'slug': model.canonical_slug,
                    'reason': 'No model ID present in database'
                })
                continue
            
            # Check if valid
            if validator.is_valid_model_id(old_id):
                valid.append({
                    'slug': model.canonical_slug,
                    'model_id': old_id
                })
                continue
            
            # Invalid - try to fix
            suggestion = validator.suggest_correction(old_id)
            
            if suggestion and auto_fix:
                corrected_id, reason = suggestion
                
                fix_record = {
                    'slug': model.canonical_slug,
                    'old_id': old_id,
                    'new_id': corrected_id,
                    'reason': reason
                }
                
                # Apply fix if not dry run
                if not dry_run:
                    if model.hugging_face_id:
                        model.hugging_face_id = corrected_id
                    elif model.base_model_id:
                        model.base_model_id = corrected_id
                    else:
                        model.model_id = corrected_id
                
                fixed.append(fix_record)
                logger.info(f"Fixed {model.canonical_slug}: {old_id} → {corrected_id} ({reason})")
            else:
                unfixable.append({
                    'slug': model.canonical_slug,
                    'model_id': old_id,
                    'reason': 'No correction available' if not suggestion else 'Auto-fix disabled'
                })
                invalid.append({
                    'slug': model.canonical_slug,
                    'model_id': old_id
                })
        
        # Commit if not dry run
        if not dry_run and fixed:
            try:
                if self.db:
                    self.db.commit()
                else:
                    from app.extensions import db
                    db.session.commit()
                logger.info(f"Committed {len(fixed)} model fixes to database")
            except Exception as e:
                logger.error(f"Failed to commit: {e}", exc_info=True)
                if self.db:
                    self.db.rollback()
                else:
                    from app.extensions import db
                    db.session.rollback()
        
        return {
            'valid': valid,
            'invalid': invalid,
            'fixed': fixed,
            'unfixable': unfixable,
            'summary': {
                'total': len(models),
                'valid': len(valid),
                'invalid': len(invalid),
                'fixed': len(fixed),
                'unfixable': len(unfixable),
                'dry_run': dry_run
            }
        }


# Singleton instance
_migration_service = None


def get_migration_service(db_session: Optional[Session] = None) -> ModelMigrationService:
    """Get singleton migration service instance."""
    global _migration_service
    if _migration_service is None:
        _migration_service = ModelMigrationService(db_session)
    return _migration_service
