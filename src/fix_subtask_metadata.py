#!/usr/bin/env python3
"""
Script to add proper metadata to subtasks so they can be executed.
"""
import sys

# Add src to path for imports
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from app.constants import AnalysisStatus
from app.extensions import db

# Tool mappings for each service
SERVICE_TOOLS = {
    'static-analyzer': [
        'bandit', 'pylint', 'eslint', 'safety', 'semgrep', 'mypy',
        'vulture', 'ruff', 'pip-audit', 'npm-audit', 'flake8', 'stylelint', 'jshint'
    ],
    'dynamic-analyzer': [
        'zap', 'curl', 'nmap'
    ],
    'performance-tester': [
        'locust', 'ab', 'aiohttp', 'artillery'
    ],
    'ai-analyzer': [
        'requirements-scanner', 'curl-endpoint-tester', 'code-quality-analyzer'
    ]
}

def main():
    """Main execution function."""
    import argparse
    parser = argparse.ArgumentParser(description='Fix metadata for subtasks')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()

    app = create_app()

    with app.app_context():
        # Get all subtasks with status CREATED
        subtasks = AnalysisTask.query.filter_by(
            is_main_task=False,
            status=AnalysisStatus.CREATED
        ).all()

        if not subtasks:
            print("No subtasks need fixing!")
            return 0

        print(f"Found {len(subtasks)} subtasks with status=CREATED")
        print("=" * 80)

        # Group by service
        from collections import defaultdict
        by_service = defaultdict(list)
        for subtask in subtasks:
            by_service[subtask.service_name].append(subtask)

        print("\nSubtasks to fix:")
        for service in sorted(by_service.keys()):
            tasks = by_service[service]
            print(f"  {service}: {len(tasks)} subtasks")

        print("\n" + "=" * 80)

        if not args.yes:
            response = input(f"\nFix metadata for {len(subtasks)} subtasks? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted.")
                return 0
        else:
            print(f"\nProceeding to fix {len(subtasks)} subtasks (--yes flag provided)")

        # Fix metadata
        print("\nFixing subtasks...")
        print("=" * 80)

        fixed_count = 0
        for subtask in subtasks:
            try:
                # Get current metadata
                meta = subtask.get_metadata()
                custom_options = meta.get('custom_options', {})

                # Set required fields
                custom_options['service_name'] = subtask.service_name
                custom_options['parent_task_id'] = subtask.parent_task_id
                custom_options['unified_analysis'] = True

                # Set tool names based on service
                if subtask.service_name in SERVICE_TOOLS:
                    custom_options['tool_names'] = SERVICE_TOOLS[subtask.service_name]
                else:
                    print(f"  ⚠ Unknown service: {subtask.service_name}, using empty tool list")
                    custom_options['tool_names'] = []

                meta['custom_options'] = custom_options

                # Update metadata
                subtask.set_metadata(meta)
                db.session.commit()

                fixed_count += 1
                if fixed_count % 10 == 0:
                    print(f"  Fixed {fixed_count}/{len(subtasks)} subtasks...")
            except Exception as e:
                print(f"✗ Failed to fix subtask {subtask.task_id}: {e}")
                db.session.rollback()

        print(f"\n✓ Fixed {fixed_count}/{len(subtasks)} subtasks")
        print("\n" + "=" * 80)
        print("\nSubtasks now have proper metadata with tool_names.")
        print("Main tasks can now be retried.")

        return 0

if __name__ == '__main__':
    sys.exit(main())
