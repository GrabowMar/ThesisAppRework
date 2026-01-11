"""
Log Cleanup Script
==================

Provides log cleanup functionality for startup and maintenance.
"""

import logging
import sys
from pathlib import Path

# Add src directory to path for imports
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))


def cleanup_logs_startup(days_to_keep: int = 7):
    """
    Clean up old log files at startup.
    
    Args:
        days_to_keep: Number of days of logs to retain (default: 7)
    """
    try:
        from app.utils.logging_config import get_logging_config
        config = get_logging_config()
        config.cleanup_old_logs(days_to_keep=days_to_keep)
    except Exception as e:
        # Silently fail - this is a best-effort cleanup
        logging.getLogger(__name__).debug(f"Log cleanup skipped: {e}")


def cleanup_logs_manual(days_to_keep: int = 7, verbose: bool = False):
    """
    Clean up old log files manually with verbose output.
    
    Args:
        days_to_keep: Number of days of logs to retain (default: 7)
        verbose: Print cleanup status
    """
    from datetime import datetime
    
    log_dir = Path(__file__).parent.parent / "logs"
    
    if not log_dir.exists():
        if verbose:
            print(f"Log directory does not exist: {log_dir}")
        return 0
    
    cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 3600)
    deleted_count = 0
    
    for log_file in log_dir.glob("*.log*"):
        try:
            if log_file.stat().st_mtime < cutoff_time:
                if verbose:
                    print(f"Deleting old log: {log_file.name}")
                log_file.unlink()
                deleted_count += 1
        except Exception as e:
            if verbose:
                print(f"Failed to delete {log_file.name}: {e}")
    
    if verbose:
        print(f"Cleaned up {deleted_count} old log files")
    
    return deleted_count


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up old log files")
    parser.add_argument(
        "--days", 
        type=int, 
        default=7, 
        help="Number of days of logs to keep (default: 7)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print verbose output"
    )
    
    args = parser.parse_args()
    cleanup_logs_manual(days_to_keep=args.days, verbose=args.verbose or True)
