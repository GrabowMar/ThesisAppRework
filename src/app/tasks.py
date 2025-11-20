"""
Celery Tasks
============

Distributed tasks for analysis execution.
"""

import logging
import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from app.celery_worker import celery
from app.extensions import db
from app.models import AnalysisTask, AnalysisStatus
from app.services.result_summary_utils import summarise_findings

logger = logging.getLogger(__name__)

@celery.task(bind=True)
def execute_subtask(self, subtask_id: int, model_slug: str, app_number: int, tools: List[str], service_name: str) -> Dict[str, Any]:
    """
    Execute a single analysis subtask via WebSocket.
    """
    logger.info(f"[CELERY] Starting subtask {subtask_id} for {service_name}")
    
    # We need to import here to avoid circular imports at module level
    # if these modules import celery/tasks
    from app.models import AnalysisTask, AnalysisStatus
    
    try:
        # Get fresh subtask from DB
        subtask = AnalysisTask.query.get(subtask_id)
        if not subtask:
            return {'status': 'error', 'error': f'Subtask {subtask_id} not found'}
        
        # Mark as running
        subtask.status = AnalysisStatus.RUNNING
        subtask.started_at = datetime.now(timezone.utc)
        db.session.commit()
        
        # Execute via WebSocket (reusing logic from TaskExecutionService, but adapted)
        # We can't easily reuse the instance method, so we'll duplicate the WS logic here
        # or extract it to a shared utility. For now, let's implement the WS call here.
        
        result = _run_websocket_sync(service_name, model_slug, app_number, tools)
        
        # Store result
        status = str(result.get('status', '')).lower()
        success = status in ('success', 'completed', 'ok', 'partial')
        is_partial = status == 'partial'
        
        subtask.status = AnalysisStatus.PARTIAL_SUCCESS if is_partial else (AnalysisStatus.COMPLETED if success else AnalysisStatus.FAILED)
        subtask.completed_at = datetime.now(timezone.utc)
        subtask.progress_percentage = 100.0
        
        if result.get('payload'):
            subtask.set_result_summary(result['payload'])
        
        if result.get('error'):
            subtask.error_message = result['error']
        
        db.session.commit()
        
        return {
            'status': result.get('status', 'error'),
            'payload': result.get('payload', {}),
            'error': result.get('error'),
            'service_name': service_name,
            'subtask_id': subtask_id
        }
        
    except Exception as e:
        logger.error(f"[CELERY] Subtask {subtask_id} failed: {e}", exc_info=True)
        try:
            subtask = AnalysisTask.query.get(subtask_id)
            if subtask:
                subtask.status = AnalysisStatus.FAILED
                subtask.error_message = str(e)
                subtask.completed_at = datetime.now(timezone.utc)
                db.session.commit()
        except Exception:
            pass
        return {'status': 'error', 'error': str(e), 'service_name': service_name}

@celery.task(bind=True)
def execute_analysis(self, task_id: int) -> Dict[str, Any]:
    """
    Execute a full analysis task (comprehensive or specific type).
    """
    logger.info(f"[CELERY] Starting analysis task {task_id}")
    
    from app.models import AnalysisTask, AnalysisStatus
    from app.services.analyzer_manager_wrapper import get_analyzer_wrapper
    
    try:
        # Get fresh task from DB
        task = AnalysisTask.query.get(task_id)
        if not task:
            return {'status': 'error', 'error': f'Task {task_id} not found'}
        
        # Mark as running
        task.status = AnalysisStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        task.progress_percentage = 10.0
        db.session.commit()
        
        # Get wrapper
        wrapper = get_analyzer_wrapper()
        
        # Extract tool names from metadata
        meta = task.get_metadata() if hasattr(task, 'get_metadata') else {}
        custom_options = meta.get('custom_options', {})
        tool_names = custom_options.get('tools') or custom_options.get('selected_tool_names') or []
        
        # Determine analysis type
        analysis_type_map = {
            'security': 'security',
            'static': 'static',
            'dynamic': 'dynamic',
            'performance': 'performance',
            'ai': 'ai',
            'comprehensive': 'comprehensive'
        }
        analysis_method = analysis_type_map.get(task.task_name, 'comprehensive')
        
        logger.info(f"[CELERY] Running {analysis_method} analysis for task {task.task_id}")
        
        # Update progress
        task.progress_percentage = 30.0
        db.session.commit()
        
        # Execute analysis
        task_name = task.task_id
        
        if analysis_method == 'comprehensive':
            result = wrapper.run_comprehensive_analysis(
                model_slug=task.target_model,
                app_number=task.target_app_number,
                task_name=task_name,
                tools=tool_names if tool_names else None
            )
        elif analysis_method == 'security':
            result = {'security': wrapper.run_security_analysis(task.target_model, task.target_app_number, tool_names)}
        elif analysis_method == 'static':
            result = {'static': wrapper.run_static_analysis(task.target_model, task.target_app_number, tool_names)}
        elif analysis_method == 'dynamic':
            result = {'dynamic': wrapper.run_dynamic_analysis(task.target_model, task.target_app_number, tools=tool_names)}
        elif analysis_method == 'performance':
            result = {'performance': wrapper.run_performance_test(task.target_model, task.target_app_number, tools=tool_names)}
        elif analysis_method == 'ai':
            result = {'ai': wrapper.run_ai_analysis(task.target_model, task.target_app_number, tools=tool_names)}
        else:
            raise ValueError(f"Unknown analysis type: {analysis_method}")
            
        # Process results (similar to TaskExecutionService logic)
        # For comprehensive, result is already consolidated. For others, it's a dict of services.
        
        # Update progress
        task.progress_percentage = 90.0
        db.session.commit()
        
        # Determine status
        # If result has 'results' key, it's likely the consolidated format from comprehensive
        if 'results' in result and 'summary' in result.get('results', {}):
            summary = result['results']['summary']
            status = summary.get('status', 'completed')
            payload = result
        else:
            # Simple service result
            payload = {'services': result}
            # Check status of services
            statuses = [v.get('status') for v in result.values() if isinstance(v, dict)]
            if all(s == 'success' for s in statuses):
                status = 'completed'
            elif any(s == 'success' for s in statuses):
                status = 'partial'
            else:
                status = 'failed'
                
        success = status in ('completed', 'partial', 'success')
        is_partial = status == 'partial'
        
        task.status = AnalysisStatus.PARTIAL_SUCCESS if is_partial else (AnalysisStatus.COMPLETED if success else AnalysisStatus.FAILED)
        task.completed_at = datetime.now(timezone.utc)
        task.progress_percentage = 100.0
        
        # Store result summary
        task.set_result_summary(payload)
        
        # Update issues count if available
        if 'summary' in payload: # Direct payload
             summary = payload['summary']
             task.issues_found = summary.get('total_findings', 0)
        elif 'results' in payload and 'summary' in payload['results']: # Nested
             summary = payload['results']['summary']
             task.issues_found = summary.get('total_findings', 0)
             
        db.session.commit()
        
        return {'status': status, 'task_id': task_id}
        
    except Exception as e:
        logger.error(f"[CELERY] Analysis task {task_id} failed: {e}", exc_info=True)
        try:
            task = AnalysisTask.query.get(task_id)
            if task:
                task.status = AnalysisStatus.FAILED
                task.error_message = str(e)
                task.completed_at = datetime.now(timezone.utc)
                db.session.commit()
        except Exception:
            pass
        return {'status': 'error', 'error': str(e)}

@celery.task(bind=True)
def aggregate_results(self, results: List[Dict[str, Any]], main_task_id: str) -> Dict[str, Any]:
    """
    Aggregate results from parallel subtasks.
    """
    logger.info(f"[CELERY] Aggregating {len(results)} results for main task {main_task_id}")
    
    try:
        main_task = AnalysisTask.query.filter_by(task_id=main_task_id).first()
        if not main_task:
            return {'status': 'error', 'error': 'Main task not found'}
            
        all_services = {}
        all_findings = []
        combined_tool_results = {}
        any_failed = False
        
        for result in results:
            # Handle potential upstream failures (Celery errors)
            if not isinstance(result, dict):
                logger.error(f"Invalid result format: {result}")
                any_failed = True
                continue
                
            service_name = result.get('service_name', 'unknown')
            all_services[service_name] = result
            
            if result.get('status') not in ('success', 'completed', 'partial'):
                any_failed = True
            
            payload = result.get('payload', {})
            if isinstance(payload, dict):
                findings = payload.get('findings', [])
                if isinstance(findings, list):
                    all_findings.extend(findings)
                
                tool_results = payload.get('tool_results', {})
                if isinstance(tool_results, dict):
                    combined_tool_results.update(tool_results)

        # Build unified payload
        unified_payload = {
            'task': {'task_id': main_task_id},
            'summary': {
                'total_findings': len(all_findings),
                'services_executed': len(all_services),
                'tools_executed': len(combined_tool_results),
                'status': 'completed' if not any_failed else 'partial'
            },
            'services': all_services,
            'tools': combined_tool_results,
            'findings': all_findings,
            'metadata': {
                'unified_analysis': True,
                'orchestrator_version': '3.0.0',
                'executor': 'Celery',
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
        }
        
        # Update main task
        main_task.status = AnalysisStatus.COMPLETED if not any_failed else AnalysisStatus.FAILED
        main_task.completed_at = datetime.now(timezone.utc)
        main_task.progress_percentage = 100.0
        
        if main_task.started_at:
             # Ensure started_at is timezone-aware
            started_at = main_task.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            duration = (main_task.completed_at - started_at).total_seconds()
            main_task.actual_duration = duration
            
        main_task.set_result_summary(unified_payload)
        db.session.commit()
        
        # Write to filesystem (we need to duplicate this logic or import it)
        # Ideally, we should use a shared service for this.
        # For now, we'll rely on the TaskExecutionService to handle filesystem writes 
        # if it's polling, OR we implement it here.
        # Since this is a background task, we should write it here.
        try:
            _write_results_to_fs(main_task, unified_payload)
        except Exception as e:
            logger.error(f"Failed to write results to filesystem: {e}")

        return unified_payload

    except Exception as e:
        logger.error(f"[CELERY] Aggregation failed: {e}", exc_info=True)
        if main_task:
            main_task.status = AnalysisStatus.FAILED
            main_task.error_message = str(e)
            db.session.commit()
        return {'status': 'error', 'error': str(e)}

def _run_websocket_sync(service_name: str, model_slug: str, app_number: int, tools: List[str], timeout: int = 600) -> Dict[str, Any]:
    """Helper to run async WebSocket code synchronously."""
    import websockets
    from websockets.exceptions import ConnectionClosed
    import time
    
    SERVICE_PORTS = {
        'static-analyzer': 2001,
        'dynamic-analyzer': 2002,
        'performance-tester': 2003,
        'ai-analyzer': 2004
    }
    port = SERVICE_PORTS.get(service_name)
    if not port:
        return {'status': 'error', 'error': f'Unknown service: {service_name}'}

    async def _ws_client():
        uri = f'ws://analyzer-gateway:8765' # Use gateway if possible, or direct service
        # In docker-compose, services are reachable by name.
        # But here we are in 'celery-worker' container.
        # We can try direct connection to service container.
        uri = f'ws://{service_name}:{port}'
        
        MESSAGE_TYPES = {
            'static-analyzer': 'static_analyze',
            'dynamic-analyzer': 'dynamic_analyze',
            'ai-analyzer': 'ai_analyze',
            'performance-tester': 'performance_test'
        }
        msg_type = MESSAGE_TYPES.get(service_name, 'analysis_request')
        
        req = {
            'type': msg_type,
            'model_slug': model_slug,
            'app_number': app_number,
            'tools': tools,
            'id': f"{model_slug}_app{app_number}_{service_name}_celery",
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        try:
            async with websockets.connect(uri, open_timeout=10, close_timeout=10) as ws:
                await ws.send(json.dumps(req))
                
                deadline = time.time() + timeout
                while time.time() < deadline:
                    try:
                        resp = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        frame = json.loads(resp)
                        
                        # Check for terminal frame
                        ftype = str(frame.get('type', '')).lower()
                        has_analysis = isinstance(frame.get('analysis'), dict)
                        
                        if ('analysis_result' in ftype) or (ftype.endswith('_analysis') and has_analysis):
                            return {
                                'status': frame.get('status', 'unknown'),
                                'payload': frame.get('analysis', frame),
                                'error': frame.get('error')
                            }
                    except asyncio.TimeoutError:
                        continue
                return {'status': 'timeout', 'error': 'Analysis timed out'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_ws_client())
    finally:
        loop.close()

def _write_results_to_fs(task, payload):
    """Write results to filesystem (simplified version)."""
    from pathlib import Path
    
    # We need to reconstruct the path logic
    # Assuming we are in /app/src/app/tasks.py -> /app/results
    results_base = Path('/app/results')
    if not results_base.exists():
        # Fallback for local dev
        results_base = Path(__file__).parent.parent.parent.parent / 'results'
        
    safe_slug = task.target_model.replace('/', '_')
    task_folder = task.task_id if task.task_id.startswith('task_') else f"task_{task.task_id}"
    
    out_dir = results_base / safe_slug / f"app{task.target_app_number}" / task_folder
    out_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{safe_slug}_app{task.target_app_number}_{task_folder}_{timestamp}.json"
    
    with open(out_dir / filename, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, default=str)
        
    # Write manifest
    manifest = {
        'task_id': task.task_id,
        'status': 'completed',
        'main_result_file': filename,
        'timestamp': datetime.now().isoformat()
    }
    with open(out_dir / 'manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
