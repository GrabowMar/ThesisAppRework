Troubleshooting and Fixing Dynamic Analysis Pipeline
This plan addresses the failures in dynamic analysis connectivity and the issues with automatic container cleanup.

Proposed Changes
[Backend Services]
[MODIFY] 
pipeline_execution_service.py
Ensure 
_stop_all_app_containers_for_pipeline
 is called in more places:
In 
_monitor_streaming_analysis
 when transitioning to 
done
.
In any error handlers where a pipeline might prematurely terminate.
Fix the fallback logic in 
_stop_all_app_containers_for_pipeline
 to use the database as a source of truth for which apps were generated if the in-memory tracking is empty.
[MODIFY] 
task_execution_service.py
Improve the finally block in execute_task to attempt container cleanup if stop_after_analysis is TRUE, even if container_started is false, provided we have a valid model and app number. This acts as a safety net for containers that might have been started by a previous task or a failed attempt.
[Analyzer Services]
[MODIFY] 
analyzer_manager.py
Improve URL resolution to use container names by default, but fallback to IPs ONLY if hostname resolution fails or is known to be problematic.
Ensure the health check endpoint is correctly configured (e.g., /health vs /api/health).
Verification Plan
Automated Tests
Run a small pipeline (1 model, 1 app) and verify:
Dynamic analysis succeeds (check 
AnalysisTask
 status).
Containers are stopped immediately after analysis.
Verify the 
nuke
 command (to be performed manually first).
Manual Verification
Perform a full "Wipeout" using the (optionally updated) 
start.ps1
 or manual commands.
Rerun the analysis pipeline and monitor logs for CLEANUP and ANAL tags.