#!/usr/bin/env python3
"""
Container Management Examples
=============================

This script demonstrates how to use the container utilities for creating
and managing Docker containers for AI-generated applications.

Usage:
    python container_examples.py [command] [options]

Commands:
    info                    - Show system information
    create <model> <app>    - Create container from template
    start <model> <app>     - Start container
    stop <model> <app>      - Stop container  
    restart <model> <app>   - Restart container
    health <model> <app>    - Check container health
    logs <model> <app>      - Show container logs
    bulk-start              - Start multiple containers
    bulk-stop               - Stop multiple containers
"""

import sys
import argparse
from pathlib import Path

# Add src directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from container_utils import (
    get_container_utils, create_container, start_container, stop_container,
    restart_container, get_container_logs, check_container_health,
    bulk_start_containers, bulk_stop_containers, get_container_info
)


def show_system_info():
    """Show Docker system information."""
    utils = get_container_utils()
    info = utils.get_system_info()
    
    print("Docker System Information")
    print("=" * 30)
    print(f"Docker Available: {info.get('docker_available', 'Unknown')}")
    print(f"Docker Version: {info.get('docker_version', 'Unknown')}")
    print(f"Compose Version: {info.get('compose_version', 'Unknown')}")
    print(f"Templates Loaded: {info.get('templates_loaded', 0)}")
    print(f"Available Templates: {', '.join(info.get('available_templates', []))}")


def create_container_example(model: str, app_num: int, template: str = 'flask_backend'):
    """Create a container from template."""
    print(f"Creating container for {model}/app{app_num} using template '{template}'...")
    
    result = create_container(model, app_num, template)
    
    if result.success:
        print(f"✅ Success: {result.message}")
        print(f"   Duration: {result.duration:.2f}s")
        print(f"   Compose Path: {result.container_info.compose_path}")
    else:
        print(f"❌ Failed: {result.error}")


def start_container_example(model: str, app_num: int):
    """Start a container."""
    print(f"Starting container for {model}/app{app_num}...")
    
    result = start_container(model, app_num, wait_for_health=True)
    
    if result.success:
        print(f"✅ Success: {result.message}")
        print(f"   Duration: {result.duration:.2f}s")
        if result.output:
            print(f"   Output: {result.output[:200]}...")
    else:
        print(f"❌ Failed: {result.error}")
        if result.output:
            print(f"   Output: {result.output[:200]}...")


def stop_container_example(model: str, app_num: int):
    """Stop a container."""
    print(f"Stopping container for {model}/app{app_num}...")
    
    result = stop_container(model, app_num)
    
    if result.success:
        print(f"✅ Success: {result.message}")
        print(f"   Duration: {result.duration:.2f}s")
    else:
        print(f"❌ Failed: {result.error}")


def restart_container_example(model: str, app_num: int):
    """Restart a container."""
    print(f"Restarting container for {model}/app{app_num}...")
    
    result = restart_container(model, app_num, wait_for_health=True)
    
    if result.success:
        print(f"✅ Success: {result.message}")
        print(f"   Duration: {result.duration:.2f}s")
    else:
        print(f"❌ Failed: {result.error}")


def show_container_health(model: str, app_num: int):
    """Show container health status."""
    print(f"Checking health for {model}/app{app_num}...")
    
    health = check_container_health(model, app_num)
    
    print(f"Overall Health: {health['overall_health'].upper()}")
    
    if health['issues']:
        print("Issues Found:")
        for issue in health['issues']:
            print(f"  ⚠️  {issue}")
    
    print("\nContainer Details:")
    for container_type, details in health['containers'].items():
        status_icon = "🟢" if details['running'] else "🔴"
        print(f"  {status_icon} {container_type}: {details['state']} (health: {details['health']})")


def show_container_logs(model: str, app_num: int, container_type: str = 'backend'):
    """Show container logs."""
    print(f"Getting logs for {model}/app{app_num}/{container_type}...")
    
    logs = get_container_logs(model, app_num, container_type, tail=50)
    
    print(f"\n--- {container_type.upper()} LOGS ---")
    print(logs)
    print("--- END LOGS ---")


def show_container_info(model: str, app_num: int):
    """Show detailed container information."""
    print(f"Getting container info for {model}/app{app_num}...")
    
    containers = get_container_info(model, app_num)
    
    if not containers:
        print("No containers found.")
        return
    
    for container in containers:
        print(f"\n--- {container.container_type.upper()} CONTAINER ---")
        print(f"Name: {container.name}")
        print(f"State: {container.state.value}")
        print(f"Health: {container.health}")
        print(f"Project: {container.project_name}")
        print(f"Compose Path: {container.compose_path}")
        
        if container.ports:
            print(f"Ports: {container.ports}")
        
        if container.metadata:
            print(f"Metadata: {container.metadata}")


def bulk_start_example():
    """Start multiple containers in parallel."""
    targets = [
        ('openai_gpt-4', 1),
        ('openai_gpt-4', 2),
        ('anthropic_claude-3-5-sonnet', 1)
    ]
    
    print(f"Starting {len(targets)} containers in parallel...")
    
    result = bulk_start_containers(targets, max_workers=2)
    
    print(f"Bulk Start Results:")
    print(f"  Total: {result.total}")
    print(f"  Successful: {result.successful}")
    print(f"  Failed: {result.failed}")
    print(f"  Duration: {result.duration:.2f}s")
    
    # Show individual results
    for op_result in result.results:
        status_icon = "✅" if op_result.success else "❌"
        model = op_result.container_info.model
        app_num = op_result.container_info.app_num
        print(f"  {status_icon} {model}/app{app_num}: {op_result.message or op_result.error}")


def bulk_stop_example():
    """Stop multiple containers in parallel."""
    targets = [
        ('openai_gpt-4', 1),
        ('openai_gpt-4', 2),
        ('anthropic_claude-3-5-sonnet', 1)
    ]
    
    print(f"Stopping {len(targets)} containers in parallel...")
    
    result = bulk_stop_containers(targets, max_workers=2)
    
    print(f"Bulk Stop Results:")
    print(f"  Total: {result.total}")
    print(f"  Successful: {result.successful}")
    print(f"  Failed: {result.failed}")
    print(f"  Duration: {result.duration:.2f}s")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Container Management Examples")
    parser.add_argument('command', help='Command to execute')
    parser.add_argument('model', nargs='?', help='Model name (e.g., openai_gpt-4)')
    parser.add_argument('app_num', nargs='?', type=int, help='App number (e.g., 1)')
    parser.add_argument('--template', default='flask_backend', help='Template name for create command')
    parser.add_argument('--container-type', default='backend', help='Container type for logs command')
    
    args = parser.parse_args()
    
    try:
        if args.command == 'info':
            show_system_info()
            
        elif args.command == 'create':
            if not args.model or not args.app_num:
                print("Error: create command requires model and app_num")
                return
            create_container_example(args.model, args.app_num, args.template)
            
        elif args.command == 'start':
            if not args.model or not args.app_num:
                print("Error: start command requires model and app_num")
                return
            start_container_example(args.model, args.app_num)
            
        elif args.command == 'stop':
            if not args.model or not args.app_num:
                print("Error: stop command requires model and app_num")
                return
            stop_container_example(args.model, args.app_num)
            
        elif args.command == 'restart':
            if not args.model or not args.app_num:
                print("Error: restart command requires model and app_num")
                return
            restart_container_example(args.model, args.app_num)
            
        elif args.command == 'health':
            if not args.model or not args.app_num:
                print("Error: health command requires model and app_num")
                return
            show_container_health(args.model, args.app_num)
            
        elif args.command == 'logs':
            if not args.model or not args.app_num:
                print("Error: logs command requires model and app_num")
                return
            show_container_logs(args.model, args.app_num, args.container_type)
            
        elif args.command == 'info-container':
            if not args.model or not args.app_num:
                print("Error: info-container command requires model and app_num")
                return
            show_container_info(args.model, args.app_num)
            
        elif args.command == 'bulk-start':
            bulk_start_example()
            
        elif args.command == 'bulk-stop':
            bulk_stop_example()
            
        else:
            print(f"Unknown command: {args.command}")
            print("Available commands: info, create, start, stop, restart, health, logs, info-container, bulk-start, bulk-stop")
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
