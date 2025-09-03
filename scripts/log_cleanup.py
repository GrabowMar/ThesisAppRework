"""
Log Cleanup Utility
===================

Utility for cleaning up old log files and managing log directory size.
Can be run as a standalone script or imported for startup cleanup.
"""

import os
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Pattern

# Add src to path for imports when run as standalone script
if __name__ == "__main__":
    script_dir = Path(__file__).parent
    src_dir = script_dir.parent / "src"
    sys.path.insert(0, str(src_dir))

try:
    from app.utils.logging_config import get_logger
    logger = get_logger('log_cleanup')
except ImportError:
    # Fallback for standalone usage
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('log_cleanup')


def cleanup_old_model_setup_logs(logs_dir: Path, days_to_keep: int = 7) -> int:
    """
    Clean up old model setup logs that accumulate over time.
    
    Args:
        logs_dir: Path to logs directory
        days_to_keep: Number of days to keep logs
        
    Returns:
        Number of files cleaned up
    """
    if not logs_dir.exists():
        return 0
    
    # Pattern for setup logs: setup_<model_name>.log
    setup_pattern: Pattern[str] = re.compile(r'^setup_.*\.log$')
    cutoff_time = datetime.now() - timedelta(days=days_to_keep)
    
    cleaned_count = 0
    for log_file in logs_dir.iterdir():
        if log_file.is_file() and setup_pattern.match(log_file.name):
            try:
                file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_time < cutoff_time:
                    log_file.unlink()
                    cleaned_count += 1
                    logger.debug(f"Cleaned up old setup log: {log_file.name}")
            except Exception as e:
                logger.warning(f"Failed to clean up {log_file.name}: {e}")
    
    if cleaned_count > 0:
        logger.info(f"Cleaned up {cleaned_count} old setup log files")
    
    return cleaned_count


def get_log_directory_size(logs_dir: Path) -> tuple[int, int]:
    """
    Get total size and file count of logs directory.
    
    Args:
        logs_dir: Path to logs directory
        
    Returns:
        Tuple of (total_size_bytes, file_count)
    """
    if not logs_dir.exists():
        return 0, 0
    
    total_size = 0
    file_count = 0
    
    for file_path in logs_dir.rglob('*'):
        if file_path.is_file():
            try:
                total_size += file_path.stat().st_size
                file_count += 1
            except Exception:
                pass  # Skip files we can't access
    
    return total_size, file_count


def rotate_large_logs(logs_dir: Path, max_size_mb: int = 50) -> List[str]:
    """
    Rotate log files that exceed size limit.
    
    Args:
        logs_dir: Path to logs directory
        max_size_mb: Maximum size in MB before rotation
        
    Returns:
        List of rotated file names
    """
    if not logs_dir.exists():
        return []
    
    max_size_bytes = max_size_mb * 1024 * 1024
    rotated_files = []
    
    for log_file in logs_dir.glob('*.log'):
        try:
            if log_file.stat().st_size > max_size_bytes:
                # Create backup with timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f"{log_file.stem}_{timestamp}.log.old"
                backup_path = logs_dir / backup_name
                
                # Move current log to backup
                log_file.rename(backup_path)
                
                # Create new empty log file
                log_file.touch()
                
                rotated_files.append(log_file.name)
                logger.info(f"Rotated large log file: {log_file.name} -> {backup_name}")
                
        except Exception as e:
            logger.warning(f"Failed to rotate {log_file.name}: {e}")
    
    return rotated_files


def cleanup_logs_startup():
    """
    Perform log cleanup tasks at application startup.
    """
    # Get logs directory relative to script location
    script_dir = Path(__file__).parent
    logs_dir = script_dir.parent / "logs"
    
    try:
        # Clean up old setup logs (keep only 3 days worth)
        cleanup_count = cleanup_old_model_setup_logs(logs_dir, days_to_keep=3)
        
        # Check directory size
        total_size, file_count = get_log_directory_size(logs_dir)
        size_mb = total_size / (1024 * 1024)
        
        logger.info(f"Log directory status: {file_count} files, {size_mb:.1f} MB total")
        
        # Rotate large files
        rotated = rotate_large_logs(logs_dir, max_size_mb=20)
        
        if cleanup_count > 0 or rotated:
            logger.info("Log cleanup completed at startup")
            
    except Exception as e:
        logger.warning(f"Log cleanup failed: {e}")


def main():
    """Main function for running cleanup as standalone script."""
    script_dir = Path(__file__).parent
    logs_dir = script_dir.parent / "logs"
    
    print(f"Starting log cleanup for: {logs_dir}")
    
    # Clean up old setup logs (keep only 7 days for manual runs)
    cleanup_count = cleanup_old_model_setup_logs(logs_dir, days_to_keep=7)
    print(f"Cleaned up {cleanup_count} old setup log files")
    
    # Check directory size
    total_size, file_count = get_log_directory_size(logs_dir)
    size_mb = total_size / (1024 * 1024)
    print(f"Log directory: {file_count} files, {size_mb:.1f} MB total")
    
    # Rotate large files
    rotated = rotate_large_logs(logs_dir, max_size_mb=50)
    if rotated:
        print(f"Rotated large log files: {', '.join(rotated)}")
    else:
        print("No large log files to rotate")
    
    print("Log cleanup completed!")


if __name__ == "__main__":
    main()
