#!/usr/bin/env python3
"""
Test script to demonstrate the new logging improvements.
"""

import sys
import os
from pathlib import Path

# Add src to path
script_dir = Path(__file__).parent
src_dir = script_dir.parent / "src"
sys.path.insert(0, str(src_dir))

from app.utils.logging_config import setup_application_logging, get_logger

def main():
    """Test the new logging features."""
    
    print("🎨 Testing Enhanced Logging System")
    print("=" * 50)
    
    # Setup logging
    logger = setup_application_logging()
    
    # Test different service loggers
    factory_logger = get_logger('factory')
    task_logger = get_logger('task_service')
    analyzer_logger = get_logger('analyzer')
    celery_logger = get_logger('celery')
    websocket_logger = get_logger('websocket')
    security_logger = get_logger('security')
    
    print("\n1. Testing Different Log Levels:")
    logger.debug("Debug message - should be colored cyan")
    logger.info("Info message - should be colored green")
    logger.warning("Warning message - should be colored yellow")
    logger.error("Error message - should be colored red")
    logger.critical("Critical message - should be bright red")
    
    print("\n2. Testing Service-Specific Colors:")
    factory_logger.info("Factory service message - should be blue")
    task_logger.info("Task service message - should be magenta")
    analyzer_logger.info("Analyzer service message - should be cyan")
    celery_logger.info("Celery service message - should be yellow")
    websocket_logger.info("WebSocket service message - should be green")
    security_logger.info("Security service message - should be magenta")
    
    print("\n3. Testing Grouped Messages (simulating spam):")
    for i in range(5):
        logger.info("Scheduler: Sending due task monitor-analyzer-containers (app.tasks.monitor_analyzer_containers)")
    
    print("\n4. Testing Stack Trace Suppression:")
    try:
        raise ValueError("Test error for demonstration")
    except Exception as e:
        logger.error("First error with stack trace", exc_info=True)
        # Simulate same error again (should be suppressed)
        logger.error("Same error again - stack trace should be suppressed", exc_info=True)
    
    print("\n5. Testing Filtered Messages:")
    # These should be filtered out
    logger.info("CPendingDeprecationWarning: The broker_connection_retry configuration setting")
    logger.info("Connection closed by server.")
    logger.info("Redis is loading the dataset in memory.")
    
    print("\n✅ Logging test completed!")
    print("Check that:")
    print("- Messages have appropriate colors")
    print("- Service names are color-coded")
    print("- Grouped messages show [GROUPED] prefix")
    print("- Repetitive stack traces are suppressed")
    print("- Spam messages are filtered out")

if __name__ == "__main__":
    main()
