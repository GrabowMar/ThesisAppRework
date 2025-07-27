"""
Generation Lookup Service
=========================

Service for looking up details of generation runs and model app combinations.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


@dataclass
class GenerationMetadata:
    """Metadata for a generation run"""
    timestamp: str
    filename: str
    models_count: int
    apps_count: int
    total_successful: int
    total_failed: int
    generation_time: float
    fastest_model: str
    slowest_model: str
    most_successful_app: int
    least_successful_app: int


@dataclass
class ModelAppDetails:
    """Details for a specific model-app combination"""
    model: str
    display_name: str
    provider: str
    is_free: bool
    app_num: int
    app_name: str
    success_rate: float
    frontend_success: bool
    backend_success: bool
    total_tokens: int
    response_quality: float
    generation_time: Optional[float]
    markdown_files: List[str]
    extracted_files: List[str]
    requirements: List[str]


class GenerationLookupService:
    """Service for looking up generation details"""
    
    def __init__(self, generated_conversations_dir: str = "generated_conversations"):
        self.conversations_dir = Path(generated_conversations_dir)
        self.logger = logging.getLogger(__name__)
    
    def list_generation_runs(self) -> List[GenerationMetadata]:
        """List all available generation runs"""
        runs = []
        
        try:
            # Look for metadata files
            metadata_files = list(self.conversations_dir.glob("metadata_detailed_*.json"))
            
            for metadata_file in sorted(metadata_files, reverse=True):  # Most recent first
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # Extract timestamp from filename
                    timestamp = metadata_file.stem.replace("metadata_detailed_", "")
                    
                    # Parse performance metrics
                    perf_metrics = data.get("performance_metrics", {})
                    
                    runs.append(GenerationMetadata(
                        timestamp=timestamp,
                        filename=metadata_file.name,
                        models_count=len(data.get("models_statistics", [])),
                        apps_count=len(data.get("apps_statistics", [])),
                        total_successful=sum(1 for m in data.get("models_statistics", []) if m.get("success_rate", 0) > 0),
                        total_failed=sum(1 for m in data.get("models_statistics", []) if m.get("success_rate", 0) == 0),
                        generation_time=perf_metrics.get("avg_generation_time_per_request", 0),
                        fastest_model=perf_metrics.get("fastest_model", "Unknown"),
                        slowest_model=perf_metrics.get("slowest_model", "Unknown"),
                        most_successful_app=perf_metrics.get("most_successful_app", 1),
                        least_successful_app=perf_metrics.get("least_successful_app", 1)
                    ))
                    
                except Exception as e:
                    self.logger.warning(f"Failed to parse metadata file {metadata_file}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Failed to list generation runs: {e}")
        
        return runs
    
    def get_generation_details(self, timestamp: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific generation run"""
        try:
            metadata_file = self.conversations_dir / f"metadata_detailed_{timestamp}.json"
            
            if not metadata_file.exists():
                return None
            
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        except Exception as e:
            self.logger.error(f"Failed to get generation details for {timestamp}: {e}")
            return None
    
    def get_model_app_details(self, timestamp: str, model: str, app_num: int) -> Optional[ModelAppDetails]:
        """Get detailed information for a specific model-app combination"""
        try:
            # Get generation details
            gen_data = self.get_generation_details(timestamp)
            if not gen_data:
                return None
            
            # Find model statistics
            model_stats = None
            for stats in gen_data.get("models_statistics", []):
                if stats.get("model") == model:
                    model_stats = stats
                    break
            
            if not model_stats:
                return None
            
            # Find app statistics
            app_stats = None
            for stats in gen_data.get("apps_statistics", []):
                if stats.get("app_num") == app_num:
                    app_stats = stats
                    break
            
            # Check if this model attempted this app
            attempted_apps = model_stats.get("apps_attempted", [])
            successful_apps = model_stats.get("successful_apps", [])
            
            if app_num not in attempted_apps:
                return None
            
            # Find markdown files
            model_safe = model.replace('/', '_').replace(':', '_')
            model_dir = self.conversations_dir / model_safe
            markdown_files = []
            extracted_files = []
            
            if model_dir.exists():
                # Look for markdown files for this app
                for md_file in model_dir.glob(f"app_{app_num}_*.md"):
                    markdown_files.append(str(md_file.relative_to(self.conversations_dir)))
                
                # Look for extracted files
                app_dir = model_dir / f"app{app_num}"
                if app_dir.exists():
                    for extracted_file in app_dir.rglob("*"):
                        if extracted_file.is_file():
                            extracted_files.append(str(extracted_file.relative_to(self.conversations_dir)))
            
            return ModelAppDetails(
                model=model,
                display_name=model_stats.get("display_name", model),
                provider=model_stats.get("provider", "unknown"),
                is_free=model_stats.get("is_free", False),
                app_num=app_num,
                app_name=app_stats.get("name", f"App {app_num}") if app_stats else f"App {app_num}",
                success_rate=model_stats.get("success_rate", 0),
                frontend_success=app_num in successful_apps,
                backend_success=app_num in successful_apps,
                total_tokens=model_stats.get("total_tokens_estimated", 0),
                response_quality=model_stats.get("avg_response_quality", 0),
                generation_time=None,  # Not available per app
                markdown_files=markdown_files,
                extracted_files=extracted_files,
                requirements=app_stats.get("requirements", []) if app_stats else []
            )
        
        except Exception as e:
            self.logger.error(f"Failed to get model app details: {e}")
            return None
    
    def get_model_performance_summary(self, timestamp: str) -> Dict[str, Any]:
        """Get performance summary for all models in a generation run"""
        try:
            gen_data = self.get_generation_details(timestamp)
            if not gen_data:
                return {}
            
            models = gen_data.get("models_statistics", [])
            
            # Calculate summary statistics
            total_models = len(models)
            successful_models = sum(1 for m in models if m.get("success_rate", 0) > 0)
            free_models = sum(1 for m in models if m.get("is_free", False))
            paid_models = total_models - free_models
            
            # Average metrics
            avg_success_rate = sum(m.get("success_rate", 0) for m in models) / max(total_models, 1)
            avg_tokens = sum(m.get("total_tokens_estimated", 0) for m in models) / max(total_models, 1)
            avg_quality = sum(m.get("avg_response_quality", 0) for m in models if m.get("avg_response_quality", 0) > 0)
            avg_quality = avg_quality / max(sum(1 for m in models if m.get("avg_response_quality", 0) > 0), 1)
            
            # Provider breakdown
            providers = {}
            for model in models:
                provider = model.get("provider", "unknown")
                if provider not in providers:
                    providers[provider] = {"total": 0, "successful": 0, "free": 0}
                providers[provider]["total"] += 1
                if model.get("success_rate", 0) > 0:
                    providers[provider]["successful"] += 1
                if model.get("is_free", False):
                    providers[provider]["free"] += 1
            
            return {
                "total_models": total_models,
                "successful_models": successful_models,
                "failed_models": total_models - successful_models,
                "free_models": free_models,
                "paid_models": paid_models,
                "avg_success_rate": avg_success_rate,
                "avg_tokens": avg_tokens,
                "avg_quality": avg_quality,
                "providers": providers,
                "performance_metrics": gen_data.get("performance_metrics", {})
            }
        
        except Exception as e:
            self.logger.error(f"Failed to get model performance summary: {e}")
            return {}
    
    def search_generations(self, model_filter: Optional[str] = None, app_filter: Optional[int] = None, 
                          success_only: bool = False) -> List[Tuple[str, str, int, bool]]:
        """Search for generations matching criteria
        
        Returns list of (timestamp, model, app_num, success) tuples
        """
        results = []
        
        try:
            for run in self.list_generation_runs():
                gen_data = self.get_generation_details(run.timestamp)
                if not gen_data:
                    continue
                
                for model_stats in gen_data.get("models_statistics", []):
                    model = model_stats.get("model", "")
                    
                    # Apply model filter
                    if model_filter and model_filter.lower() not in model.lower():
                        continue
                    
                    for app_num in model_stats.get("apps_attempted", []):
                        # Apply app filter
                        if app_filter is not None and app_num != app_filter:
                            continue
                        
                        # Check success
                        is_successful = app_num in model_stats.get("successful_apps", [])
                        
                        # Apply success filter
                        if success_only and not is_successful:
                            continue
                        
                        results.append((run.timestamp, model, app_num, is_successful))
        
        except Exception as e:
            self.logger.error(f"Failed to search generations: {e}")
        
        return results
    
    def get_file_content(self, relative_path: str) -> Optional[str]:
        """Get content of a generated file"""
        try:
            file_path = self.conversations_dir / relative_path
            
            if not file_path.exists() or not file_path.is_file():
                return None
            
            # Check if it's within the conversations directory (security)
            if not str(file_path.resolve()).startswith(str(self.conversations_dir.resolve())):
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        except Exception as e:
            self.logger.error(f"Failed to get file content for {relative_path}: {e}")
            return None
