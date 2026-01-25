"""
Celery Tasks
============

Distributed tasks for analysis execution with distributed locking
to prevent SQLite concurrency issues.
"""

import logging
import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from app.celery_worker import celery
from app.extensions import db
from app.models import AnalysisTask, AnalysisStatus
from app.utils.distributed_lock import database_write_lock

logger = logging.getLogger(__name__)


def _extract_total_issues(payload: Dict[str, Any]) -> int:
    """Extract total issue count from various result payload formats.
    
    Handles multiple result structures:
    1. Direct summary: {'summary': {'total_findings': N}}
    2. Comprehensive nested: {'results': {'summary': {...}, 'services': {...}}}
    3. Service-specific: {'services': {'static': {'analysis': {'results': {...}}}}}
    
    If the summary shows 0 but services contain actual findings, 
    we compute the real count from service results.
    """
    total_issues = 0
    
    # Try to get from summary first
    summary_issues = 0
    if 'summary' in payload:
        summary_issues = payload['summary'].get('total_findings', 0)
    elif 'results' in payload and isinstance(payload.get('results'), dict):
        results = payload['results']
        if 'summary' in results:
            summary_issues = results['summary'].get('total_findings', 0)
    
    # If summary shows issues, trust it
    if summary_issues > 0:
        return summary_issues
    
    # Otherwise, compute from service results (summary might be buggy)
    services_to_scan = {}
    
    # Check for services at different nesting levels
    if 'services' in payload:
        services_to_scan = payload['services']
    elif 'results' in payload and isinstance(payload.get('results'), dict):
        results = payload['results']
        if 'services' in results:
            services_to_scan = results['services']
    
    # Also check top-level service keys (static, dynamic, etc.)
    for key in ('static', 'dynamic', 'performance', 'ai', 'security'):
        if key in payload and isinstance(payload[key], dict):
            services_to_scan[key] = payload[key]
    
    # Extract issues from each service
    for svc_name, svc_result in services_to_scan.items():
        if not isinstance(svc_result, dict):
            continue
        
        # Try to get from service-level summary first
        svc_analysis = svc_result.get('analysis', {})
        if isinstance(svc_analysis, dict):
            svc_summary = svc_analysis.get('summary', {})
            if isinstance(svc_summary, dict):
                svc_total = svc_summary.get('total_issues_found', 0) or svc_summary.get('total_findings', 0)
                if svc_total > 0:
                    total_issues += svc_total
                    continue
            
            # Dive into tool results: analysis.results.{language}.{tool}.total_issues
            results_data = svc_analysis.get('results', {})
            if isinstance(results_data, dict):
                for lang_results in results_data.values():
                    if isinstance(lang_results, dict):
                        for tool_result in lang_results.values():
                            if isinstance(tool_result, dict):
                                # Use total_issues OR issue_count, not both (they're the same)
                                tool_issues = tool_result.get('total_issues', 0) or tool_result.get('issue_count', 0)
                                total_issues += tool_issues
    
    return total_issues


@celery.task(bind=True)
def execute_subtask(self, subtask_id: int, model_slug: str, app_number: int, tools: List[str], service_name: str) -> Dict[str, Any]:
    """
    Execute a single analysis subtask via WebSocket.
    """
    logger.info(f"[CELERY] Starting subtask {subtask_id} for {service_name}")

    try:
        # Get fresh subtask from DB
        subtask = AnalysisTask.query.get(subtask_id)
        if not subtask:
            return {'status': 'error', 'error': f'Subtask {subtask_id} not found'}

        # Mark as running (with distributed lock to prevent SQLite I/O errors)
        with database_write_lock(f"subtask_{subtask_id}_start"):
            subtask.status = AnalysisStatus.RUNNING
            subtask.started_at = datetime.now(timezone.utc)
            subtask.current_step = f"Starting {service_name} analysis..."
            subtask.progress_percentage = 10.0
            db.session.commit()

        # Execute via WebSocket using the pooled analyzer manager
        from app.services.analyzer_manager_wrapper import get_analyzer_wrapper
        
        # Update progress before execution
        with database_write_lock(f"subtask_{subtask_id}_progress"):
            subtask.current_step = f"Running {service_name} analyzer with {len(tools)} tools..."
            subtask.progress_percentage = 30.0
            db.session.commit()

        # Build message payload typically expected by the manager
        # The manager specific methods (run_static_analysis etc) handle message construction,
        # but here we have a generic service_name. 
        # We can use the lower-level send_websocket_message if we want generic support,
        # OR switch based on service name to use the typed methods. 
        # Using typed methods is safer as they handle service-specific fields (like target_urls).
        
        wrapper = get_analyzer_wrapper()
        
        # Map service name to wrapper method
        result = {}
        if service_name == 'static-analyzer':
            result = wrapper.run_static_analysis(model_slug, app_number, tools)
        elif service_name == 'dynamic-analyzer':
             # For dynamic/performance, we might need options/config. 
             # Assuming standard defaults or extracting from subtask options if needed.
             result = wrapper.run_dynamic_analysis(model_slug, app_number, tools=tools)
        elif service_name == 'performance-tester':
             result = wrapper.run_performance_test(model_slug, app_number, tools=tools)
        elif service_name == 'ai-analyzer':
             result = wrapper.run_ai_analysis(model_slug, app_number, tools=tools)
        else:
             # Fallback to generic if needed, or error
             raise ValueError(f"Unknown service: {service_name}")
        
        # Store result (with distributed lock to prevent SQLite I/O errors)
        status = str(result.get('status', '')).lower()
        success = status in ('success', 'completed', 'ok', 'partial')
        is_partial = status == 'partial'

        with database_write_lock(f"subtask_{subtask_id}_complete"):
            subtask.status = AnalysisStatus.PARTIAL_SUCCESS if is_partial else (AnalysisStatus.COMPLETED if success else AnalysisStatus.FAILED)
            subtask.completed_at = datetime.now(timezone.utc)
            subtask.progress_percentage = 100.0

            # Set completion message
            if success:
                subtask.current_step = f"✓ {service_name} analysis completed successfully"
            elif is_partial:
                subtask.current_step = f"⚠ {service_name} analysis completed with warnings"
            else:
                subtask.current_step = f"✗ {service_name} analysis failed"

            # Wrapper results are usually {status:..., payload:...} or just the payload if success?
            # AnalyzerManagerWrapper guarantees strict return shapes usually.
            # Let's handle generic structure.
            
            payload = result.get('payload', result) if 'payload' in result else result
            
            if payload:
                subtask.set_result_summary(payload)

            if result.get('error'):
                subtask.error_message = result['error']

            db.session.commit()
        
        return {
            'status': result.get('status', 'success' if success else 'error'),
            'payload': payload,
            'error': result.get('error'),
            'service_name': service_name,
            'subtask_id': subtask_id
        }
        
    except Exception as e:
        logger.error(f"[CELERY] Subtask {subtask_id} failed: {e}", exc_info=True)
        try:
            subtask = AnalysisTask.query.get(subtask_id)
            if subtask:
                with database_write_lock(f"subtask_{subtask_id}_error"):
                    subtask.status = AnalysisStatus.FAILED
                    subtask.error_message = str(e)
                    subtask.completed_at = datetime.now(timezone.utc)
                    db.session.commit()
        except Exception as db_err:
            logger.warning(f"Failed to update subtask {subtask_id} status in DB: {db_err}", exc_info=True)
        return {'status': 'error', 'error': str(e), 'service_name': service_name}

@celery.task(bind=True)
def execute_analysis(self, task_id: int) -> Dict[str, Any]:
    """
    Execute a full analysis task (comprehensive or specific type).
    """
    logger.info(f"[CELERY] Starting analysis task {task_id}")

    from app.services.analyzer_manager_wrapper import get_analyzer_wrapper

    try:
        # Get fresh task from DB
        task = AnalysisTask.query.get(task_id)
        if not task:
            return {'status': 'error', 'error': f'Task {task_id} not found'}
        
        # Mark as running (with distributed lock)
        with database_write_lock(f"task_{task_id}_start"):
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
        
        # Update progress (with distributed lock)
        with database_write_lock(f"task_{task_id}_progress"):
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
        
        # Update progress (with distributed lock)
        with database_write_lock(f"task_{task_id}_progress_90"):
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
        
        # Store result summary (with distributed lock)
        with database_write_lock(f"task_{task_id}_complete"):
            task.set_result_summary(payload)

            # Update issues count - extract from various result formats
            total_issues = _extract_total_issues(payload)
            
            task.issues_found = total_issues
            logger.info(f"[CELERY] Task {task.task_id} completed with {total_issues} issues found")

            db.session.commit()
        
        return {'status': status, 'task_id': task_id}
        
    except Exception as e:
        logger.error(f"[CELERY] Analysis task {task_id} failed: {e}", exc_info=True)
        try:
            task = AnalysisTask.query.get(task_id)
            if task:
                with database_write_lock(f"task_{task_id}_error"):
                    task.status = AnalysisStatus.FAILED
                    task.error_message = str(e)
                    task.completed_at = datetime.now(timezone.utc)
                    db.session.commit()
        except Exception as db_err:
            logger.warning(f"Failed to update task {task_id} status in DB: {db_err}", exc_info=True)
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
        
        # Update main task (with distributed lock)
        with database_write_lock(f"task_{main_task_id}_aggregate"):
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
            with database_write_lock(f"task_{main_task_id}_aggregate_error"):
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
    
    # Resolve target URLs for dynamic/performance analysis
    target_urls = []
    if service_name in ('dynamic-analyzer', 'performance-tester'):
        try:
            from app.services.analyzer_manager_wrapper import get_analyzer_wrapper
            analyzer_mgr = get_analyzer_wrapper().manager
            ports = analyzer_mgr._resolve_app_ports(model_slug, app_number)
            if ports:
                backend_port, frontend_port = ports
                # Use Docker container names for container-to-container communication
                # Container names follow pattern: {model_slug}-app{N}_backend/frontend
                # The containers are on thesis-apps-network, same as analyzers
                # Note: Docker Compose converts underscores to hyphens in container names
                safe_slug = model_slug.replace('_', '-')
                container_prefix = f"{safe_slug}-app{app_number}"
                target_urls = [
                    f"http://{container_prefix}_backend:{backend_port}",
                    f"http://{container_prefix}_frontend:80"  # nginx serves on port 80 inside container
                ]
                logger.info(f"[CELERY] Resolved target URLs for {service_name}: {target_urls}")
            else:
                logger.warning(f"[CELERY] Could not resolve ports for {model_slug}/app{app_number}")
        except Exception as e:
            logger.warning(f"[CELERY] Error resolving ports: {e}")

    # Resolve AI config for ai-analyzer (template_slug, ports)
    ai_config = None
    if service_name == 'ai-analyzer':
        try:
            from app.services.analyzer_manager_wrapper import get_analyzer_wrapper
            analyzer_mgr = get_analyzer_wrapper().manager
            ai_config = analyzer_mgr._resolve_ai_config(model_slug, app_number, tools)
            if ai_config:
                logger.info(f"[CELERY] Resolved AI config for {service_name}: template={ai_config.get('template_slug')}")
            else:
                logger.warning(f"[CELERY] Could not resolve AI config for {model_slug}/app{app_number}")
        except Exception as e:
            logger.warning(f"[CELERY] Error resolving AI config: {e}")

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
        
        # Add target_urls for dynamic/performance analysis
        if target_urls:
            req['target_urls'] = target_urls
            # Legacy support for performance-tester
            if service_name == 'performance-tester':
                req['target_url'] = target_urls[0]
            logger.info(f"[CELERY] Added target_urls to {service_name} request: {target_urls}")
        
        # Add AI analyzer config (template_slug, ports, etc.)
        if service_name == 'ai-analyzer' and ai_config:
            req['config'] = ai_config
            logger.info(f"[CELERY] Added AI config to request: template_slug={ai_config.get('template_slug')}")
        
        logger.info(f"[CELERY] Connecting to {service_name} at {uri}...")
        
        try:
            async with websockets.connect(
                uri,
                open_timeout=10,
                close_timeout=10,
                ping_interval=None,
                ping_timeout=None,
                max_size=100 * 1024 * 1024,  # 100MB to match server
            ) as ws:
                await ws.send(json.dumps(req))
                
                deadline = time.time() + timeout
                terminal_result = None
                
                while time.time() < deadline:
                    try:
                        resp = await asyncio.wait_for(ws.recv(), timeout=10.0)  # Increased from 5s to 10s
                        frame = json.loads(resp)

                        # Check for terminal frame
                        ftype = str(frame.get('type', '')).lower()
                        has_analysis = isinstance(frame.get('analysis'), dict)
                        fstatus = str(frame.get('status', '')).lower()

                        # Ignore non-terminal messages (status updates, progress)
                        if ftype in ('status_update', 'progress_update', 'progress'):
                            logger.debug(f"[CELERY] Received {ftype}: {frame.get('message', 'N/A')}")
                            continue

                        # Terminal detection: result frames OR frames with analysis data
                        is_terminal = (
                            ('analysis_result' in ftype) or
                            ('_result' in ftype and has_analysis) or
                            (ftype.endswith('_analysis') and has_analysis) or
                            (fstatus in ('success', 'completed') and has_analysis) or
                            (ftype == 'result' and has_analysis)
                        )

                        if is_terminal:
                            terminal_result = {
                                'status': frame.get('status', 'success'),
                                'payload': frame.get('analysis', frame),
                                'error': frame.get('error')
                            }
                            logger.info(f"[CELERY] Received terminal result from {service_name}")
                            break
                    except asyncio.TimeoutError:
                        # No message in 10 seconds - continue waiting
                        continue
                    except ConnectionClosed as cc:
                        # Close code 1000 means normal closure - this is OK
                        if cc.code == 1000 and terminal_result:
                            break
                        elif cc.code == 1000:
                            # Normal close but no result yet - might be in the close reason
                            logger.warning(f"Connection closed normally (1000) before receiving result")
                            break
                        else:
                            return {'status': 'error', 'error': f'Connection closed with code {cc.code}: {cc.reason}'}
                
                if terminal_result:
                    return terminal_result
                return {'status': 'timeout', 'error': 'Analysis timed out waiting for result'}
                
        except ConnectionClosed as cc:
            # Handle close during handshake or initial communication
            if cc.code == 1000:
                logger.warning(f"Connection closed normally during {service_name} analysis")
                return {'status': 'error', 'error': 'Connection closed before result received'}
            return {'status': 'error', 'error': f'WebSocket closed with code {cc.code}: {cc.reason}'}
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
