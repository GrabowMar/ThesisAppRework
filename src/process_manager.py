"""
Process Manager CLI for Database-Based Process Tracking
========================================================

Replacement for PID file operations in start scripts.

This module provides a command-line interface for managing process tracking
in the database. It replaces traditional PID files with database-backed process
registration, allowing for better process monitoring and coordination across
containerized environments.

Features:
- Register running processes with metadata
- Query process status and PIDs
- Mark processes as stopped
- Clean up dead/stale processes
- Support for service hierarchies (main/worker processes)

Commands:
    register: Register a new process
    pid: Get PID for a service
    running: Check if service is running
    stop: Mark process as stopped
    heartbeat: Update process heartbeat
    status: Get status of services
    cleanup: Remove dead processes

Usage:
    python src/process_manager.py register flask_app --type main --pid 1234
    python src/process_manager.py status
    python src/process_manager.py cleanup
"""
import sys
import argparse
from pathlib import Path

# Add the src directory to the Python path
src_dir = Path(__file__).parent
sys.path.insert(0, str(src_dir))

from app import create_app
from app.services.process_tracking_service import ProcessTrackingService


def register_process(args):
    """Register a process in the database.
    
    Args:
        args: Parsed command-line arguments containing:
            - service: Service name (e.g., flask_app, celery_worker)
            - type: Service type (default: main)
            - pid: Process ID (optional, defaults to current process)
            - host: Host name (optional)
            - port: Port number (optional)
            - command: Command line (optional)
            - metadata: Key=value metadata pairs (optional)
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    app = create_app()
    with app.app_context():
        metadata = {}
        if args.metadata:
            # Parse metadata as key=value pairs
            for item in args.metadata:
                if '=' in item:
                    key, value = item.split('=', 1)
                    metadata[key] = value
        
        result = ProcessTrackingService.register_process(
            service_name=args.service,
            service_type=args.type,
            process_id=args.pid,
            host=args.host,
            port=args.port,
            command_line=args.command,
            metadata=metadata if metadata else None
        )
        
        if result:
            print(f"Registered {args.service}:{args.type} PID {result.process_id}")
            return 0
        else:
            print(f"Failed to register {args.service}:{args.type}", file=sys.stderr)
            return 1


def get_pid(args):
    """Get PID for a service (equivalent to reading PID file).
    
    Args:
        args: Parsed command-line arguments containing:
            - service: Service name
            - type: Service type (default: main)
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    app = create_app()
    with app.app_context():
        pid = ProcessTrackingService.get_process_id(args.service, args.type)
        if pid:
            print(pid)
            return 0
        else:
            return 1


def check_running(args):
    """Check if a service is running.
    
    Args:
        args: Parsed command-line arguments containing:
            - service: Service name
            - type: Service type (default: main)
    
    Returns:
        int: Exit code (0 if running, 1 if not running)
    """
    app = create_app()
    with app.app_context():
        pid = ProcessTrackingService.get_process_id(args.service, args.type)
        if pid:
            print("running")
            return 0
        else:
            print("stopped")
            return 1


def stop_process(args):
    """Mark a process as stopped.
    
    Args:
        args: Parsed command-line arguments containing:
            - service: Service name
            - type: Service type (default: main)
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    app = create_app()
    with app.app_context():
        success = ProcessTrackingService.mark_stopped(args.service, args.type)
        if success:
            print(f"Marked {args.service}:{args.type} as stopped")
            return 0
        else:
            print(f"Failed to mark {args.service}:{args.type} as stopped", file=sys.stderr)
            return 1


def heartbeat(args):
    """Update heartbeat for a service.
    
    Args:
        args: Parsed command-line arguments containing:
            - service: Service name
            - type: Service type (default: main)
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    app = create_app()
    with app.app_context():
        success = ProcessTrackingService.update_heartbeat(args.service, args.type)
        if success:
            return 0
        else:
            return 1


def status(args):
    """Get status of all services or a specific service.
    
    Args:
        args: Parsed command-line arguments containing:
            - service: Service name (optional, shows all if omitted)
            - type: Service type (default: main)
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    app = create_app()
    with app.app_context():
        if args.service:
            process = ProcessTrackingService.get_process(args.service, args.type)
            if process:
                is_running = ProcessTrackingService.is_process_running(process.process_id)
                status_str = "running" if is_running else "stopped"
                print(f"{process.service_name}:{process.service_type} {status_str} PID {process.process_id}")
                return 0 if is_running else 1
            else:
                print(f"{args.service}:{args.type} not found")
                return 1
        else:
            # Show all services
            status_dict = ProcessTrackingService.get_service_status()
            if not status_dict:
                print("No services tracked")
                return 0
            
            for service_key, info in status_dict.items():
                status_str = info['status']
                pid_str = f"PID {info['pid']}" if info['pid'] else "no PID"
                print(f"{info['service_name']}:{info['service_type']} {status_str} {pid_str}")
            
            return 0


def cleanup(args):
    """Clean up dead processes.
    
    Removes database entries for processes that are no longer running.
    
    Returns:
        int: Exit code (0 for success)
    """
    app = create_app()
    with app.app_context():
        cleaned = ProcessTrackingService.cleanup_dead_processes()
        print(f"Cleaned up {cleaned} dead processes")
        return 0


def main():
    """Main entry point for the process manager CLI.
    
    Parses command-line arguments and executes the appropriate command.
    Supports subcommands for process registration, status checking,
    and cleanup operations.
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    
    # Register command
    register_parser = subparsers.add_parser('register', help='Register a process')
    register_parser.add_argument('service', help='Service name (e.g., flask_app, celery_worker, celery_beat)')
    register_parser.add_argument('--type', default='main', help='Service type (default: main)')
    register_parser.add_argument('--pid', type=int, help='Process ID (default: current process)')
    register_parser.add_argument('--host', help='Host name (default: hostname)')
    register_parser.add_argument('--port', type=int, help='Port number')
    register_parser.add_argument('--command', help='Command line')
    register_parser.add_argument('--metadata', nargs='*', help='Metadata as key=value pairs')
    register_parser.set_defaults(func=register_process)
    
    # Get PID command
    pid_parser = subparsers.add_parser('pid', help='Get PID for a service')
    pid_parser.add_argument('service', help='Service name')
    pid_parser.add_argument('--type', default='main', help='Service type (default: main)')
    pid_parser.set_defaults(func=get_pid)
    
    # Check running command
    running_parser = subparsers.add_parser('running', help='Check if service is running')
    running_parser.add_argument('service', help='Service name')
    running_parser.add_argument('--type', default='main', help='Service type (default: main)')
    running_parser.set_defaults(func=check_running)
    
    # Stop command
    stop_parser = subparsers.add_parser('stop', help='Mark process as stopped')
    stop_parser.add_argument('service', help='Service name')
    stop_parser.add_argument('--type', default='main', help='Service type (default: main)')
    stop_parser.set_defaults(func=stop_process)
    
    # Heartbeat command
    heartbeat_parser = subparsers.add_parser('heartbeat', help='Update heartbeat')
    heartbeat_parser.add_argument('service', help='Service name')
    heartbeat_parser.add_argument('--type', default='main', help='Service type (default: main)')
    heartbeat_parser.set_defaults(func=heartbeat)
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Get service status')
    status_parser.add_argument('service', nargs='?', help='Service name (optional, shows all if omitted)')
    status_parser.add_argument('--type', default='main', help='Service type (default: main)')
    status_parser.set_defaults(func=status)
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up dead processes')
    cleanup_parser.set_defaults(func=cleanup)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        return args.func(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
