"""Analyzer Manager Wrapper Service
===================================

Thin synchronous wrapper around analyzer_manager.py for use in Flask context.
Delegates all analysis work to the proven CLI analyzer_manager implementation.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

from app.utils.logging_config import get_logger
from app.utils.async_utils import run_async_safely

logger = get_logger('analyzer_wrapper')

# Import analyzer_manager from the analyzer directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / 'analyzer'))

try:
    # Use the pooled version for concurrent analysis with load balancing
    from analyzer_manager_pooled import PooledAnalyzerManager as AnalyzerManager  # type: ignore[import-not-found]
except ImportError:
    # Fall back to standard analyzer manager if pooled version not available
    try:
        from analyzer_manager import AnalyzerManager  # type: ignore[import-not-found]
    except ImportError as e:
        logger.error(f"Failed to import analyzer_manager: {e}")
        AnalyzerManager = None  # type: ignore


class AnalyzerManagerWrapper:
    """Synchronous wrapper for AnalyzerManager to use in Flask app context."""
    
    def __init__(self):
        """Initialize the wrapper with an AnalyzerManager instance."""
        if AnalyzerManager is None:
            raise RuntimeError("analyzer_manager module not available")
        
        self.manager = AnalyzerManager()
        logger.info("Initialized AnalyzerManagerWrapper")
    
    def run_comprehensive_analysis(
        self,
        model_slug: str,
        app_number: int,
        task_name: Optional[str] = None,
        tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run comprehensive analysis (security, static, performance, dynamic).
        
        This method delegates to analyzer_manager which writes consolidated results to disk.
        Returns the same consolidated result structure that CLI produces for 1:1 parity.
        
        Args:
            model_slug: Model identifier (e.g., 'anthropic_claude-4.5-haiku-20251001')
            app_number: Application number (e.g., 1)
            task_name: Optional task name for results folder (auto-generated if not provided)
            tools: Optional list of specific tools to run (defaults to all if None)
        
        Returns:
            Consolidated result dictionary with structure:
            {
                'metadata': {...},
                'results': {
                    'task': {...},
                    'summary': {...},
                    'services': {...},  # Per-service raw results
                    'tools': {...},     # Flat tool map across services
                    'findings': [...]   # Aggregated findings array
                }
            }
        """
        import json
        from datetime import datetime
        
        logger.info(f"Running comprehensive analysis: {model_slug} app {app_number}")
        
        try:
            # Run the async method synchronously using safe async execution
            # This internally calls save_task_results() which writes files to disk
            service_results = run_async_safely(
                self.manager.run_comprehensive_analysis(
                    model_slug=model_slug,
                    app_number=app_number,
                    task_name=task_name,
                    tools=tools
                )
            )
            
            # Determine the actual task_id that was used
            if task_name:
                task_id = task_name
            else:
                # Auto-generated timestamp-based ID (same pattern as analyzer_manager)
                task_id = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # CRITICAL FIX: Wait for filesystem sync before reading files
            # analyzer_manager writes files asynchronously, we need to ensure they're flushed
            import time
            time.sleep(0.5)  # Give OS time to flush writes
            
            # Read back the consolidated result file that was just saved
            # This ensures 1:1 parity with CLI output structure
            safe_slug = model_slug.replace('/', '_').replace('\\', '_')
            
            # Normalize task_id to match analyzer_manager's _build_task_output_dir logic
            # Strip non-alphanumeric chars except - and _
            sanitized_task = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in str(task_id))
            # Don't add task_ prefix if it already has it
            task_folder_name = sanitized_task if sanitized_task.startswith('task_') else f"task_{sanitized_task}"
            
            task_dir = Path(f"results/{safe_slug}/app{app_number}/{task_folder_name}")
            
            # Find the most recent JSON file in the task directory
            # CRITICAL FIX: Add retry logic with polling to wait for file to appear
            max_retries = 10
            retry_delay = 0.2  # 200ms between retries
            json_files = []
            
            for attempt in range(max_retries):
                if task_dir.exists():
                    # Pattern: {model}_app{num}_{task_folder_name}.json OR {model}_app{num}_{task_folder_name}_{timestamp}.json
                    # Try both patterns (with and without timestamp)
                    json_files = sorted(
                        list(task_dir.glob(f"{safe_slug}_app{app_number}_{task_folder_name}.json")) +
                        list(task_dir.glob(f"{safe_slug}_app{app_number}_{task_folder_name}_*.json")),
                        key=lambda p: p.stat().st_mtime,
                        reverse=True
                    )
                    
                    if json_files:
                        break
                
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
            
            if json_files and task_dir.exists():
                result_file = json_files[0]
                logger.info(f"Reading consolidated result from: {result_file}")
                
                with open(result_file, 'r', encoding='utf-8') as f:
                    consolidated_result = json.load(f)
                
                logger.info(f"Comprehensive analysis completed: {model_slug} app {app_number}")
                logger.info(f"Results saved to: {task_dir}")
                return consolidated_result
            else:
                logger.warning(f"Task directory or result file not found after {max_retries} retries: {task_dir}, returning service results")
            
            # Fallback: if file reading fails, return service results with metadata wrapper
            # This maintains compatibility but doesn't match CLI structure
            return {
                'metadata': {
                    'model_slug': model_slug,
                    'app_number': app_number,
                    'task_id': task_id,
                    'warning': 'Consolidated result file not found, using service results'
                },
                'results': {
                    'services': service_results,
                    'note': 'This is a fallback structure, not the standard consolidated format'
                }
            }
            
        except Exception as e:
            logger.error(f"Comprehensive analysis failed: {e}", exc_info=True)
            return {
                'metadata': {
                    'model_slug': model_slug,
                    'app_number': app_number,
                    'error': str(e)
                },
                'results': {
                    'services': {
                        'security': {'status': 'error', 'error': str(e)},
                        'static': {'status': 'error', 'error': str(e)},
                        'performance': {'status': 'error', 'error': str(e)},
                        'dynamic': {'status': 'error', 'error': str(e)}
                    }
                }
            }
    
    def run_security_analysis(
        self,
        model_slug: str,
        app_number: int,
        tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run security analysis.
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            tools: Optional list of specific tools to run
        
        Returns:
            Security analysis results
        """
        logger.info(f"Running security analysis: {model_slug} app {app_number}")
        
        try:
            result = run_async_safely(
                self.manager.run_security_analysis(
                    model_slug=model_slug,
                    app_number=app_number,
                    tools=tools
                )
            )
            
            logger.info(f"Security analysis completed: {model_slug} app {app_number}")
            return result
            
        except Exception as e:
            logger.error(f"Security analysis failed: {e}", exc_info=True)
            return {'status': 'error', 'error': str(e)}
    
    def run_static_analysis(
        self,
        model_slug: str,
        app_number: int,
        tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run static code analysis.
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            tools: Optional list of specific tools to run
        
        Returns:
            Static analysis results
        """
        logger.info(f"Running static analysis: {model_slug} app {app_number}")
        
        try:
            result = run_async_safely(
                self.manager.run_static_analysis(
                    model_slug=model_slug,
                    app_number=app_number,
                    tools=tools
                )
            )
            
            logger.info(f"Static analysis completed: {model_slug} app {app_number}")
            return result
            
        except Exception as e:
            logger.error(f"Static analysis failed: {e}", exc_info=True)
            return {'status': 'error', 'error': str(e)}
    
    def run_dynamic_analysis(
        self,
        model_slug: str,
        app_number: int,
        options: Optional[Dict[str, Any]] = None,
        tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run dynamic analysis.
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            options: Optional configuration
            tools: Optional list of specific tools to run
        
        Returns:
            Dynamic analysis results
        """
        logger.info(f"Running dynamic analysis: {model_slug} app {app_number}")
        
        try:
            result = run_async_safely(
                self.manager.run_dynamic_analysis(
                    model_slug=model_slug,
                    app_number=app_number,
                    options=options,
                    tools=tools
                )
            )
            
            logger.info(f"Dynamic analysis completed: {model_slug} app {app_number}")
            return result
            
        except Exception as e:
            logger.error(f"Dynamic analysis failed: {e}", exc_info=True)
            return {'status': 'error', 'error': str(e)}
    
    def run_performance_test(
        self,
        model_slug: str,
        app_number: int,
        test_config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Run performance testing.
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            test_config: Optional test configuration
            tools: Optional list of specific tools to run
        
        Returns:
            Performance test results
        """
        logger.info(f"Running performance test: {model_slug} app {app_number}")
        
        try:
            result = run_async_safely(
                self.manager.run_performance_test(
                    model_slug=model_slug,
                    app_number=app_number,
                    test_config=test_config,
                    tools=tools
                )
            )
            
            logger.info(f"Performance test completed: {model_slug} app {app_number}")
            return result
            
        except Exception as e:
            logger.error(f"Performance test failed: {e}", exc_info=True)
            return {'status': 'error', 'error': str(e)}
    
    def run_ai_analysis(
        self,
        model_slug: str,
        app_number: int,
        tools: Optional[List[str]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run AI-powered analysis.
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            tools: Optional list of specific tools to run
            options: Optional configuration
        
        Returns:
            AI analysis results
        """
        logger.info(f"Running AI analysis: {model_slug} app {app_number}")
        
        try:
            result = run_async_safely(
                self.manager.run_ai_analysis(
                    model_slug=model_slug,
                    app_number=app_number,
                    tools=tools,
                    config=options
                )
            )
            
            logger.info(f"AI analysis completed: {model_slug} app {app_number}")
            return result
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}", exc_info=True)
            return {'status': 'error', 'error': str(e)}


# Global singleton instance
_analyzer_wrapper: Optional[AnalyzerManagerWrapper] = None


def get_analyzer_wrapper() -> AnalyzerManagerWrapper:
    """Get or create the global AnalyzerManagerWrapper instance."""
    global _analyzer_wrapper
    
    if _analyzer_wrapper is None:
        _analyzer_wrapper = AnalyzerManagerWrapper()
    
    return _analyzer_wrapper
