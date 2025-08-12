#!/usr/bin/env python3
"""
API Route Migration Script
==========================

This script migrates routes from the monolithic legacy api.py file
to the appropriate modular API files in the /api/ folder structure.

Migration Strategy:
- Core routes (/, health) -> core.py ✓ (already done)
- Dashboard/HTMX routes -> dashboard.py (needs migration)
- Application management -> applications.py (needs migration)
- System health/metrics -> system.py ✓ (already done)
- Analysis operations -> analysis.py (needs migration)  
- Statistics endpoints -> statistics.py ✓ (already done)
- Model operations -> models.py (needs migration)

This analysis helps identify which routes need to be migrated and removed from legacy api.py
"""

import os
import re
from pathlib import Path

def analyze_legacy_routes():
    """Analyze the legacy api.py file to categorize routes for migration."""
    
    legacy_file = Path("src/app/routes/api.py")
    if not legacy_file.exists():
        print(f"Legacy file {legacy_file} not found!")
        return
    
    print("🔍 ANALYZING LEGACY API.PY FILE")
    print("=" * 50)
    
    with open(legacy_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract all route definitions
    route_pattern = r'@api_bp\.route\([\'"]([^\'"]+)[\'"](?:,\s*methods=\[([^\]]+)\])?\)'
    routes = re.findall(route_pattern, content)
    
    # Categorize routes by functionality
    categories = {
        'core': [],
        'dashboard': [],
        'applications': [],
        'system': [],
        'analysis': [],
        'statistics': [],
        'models': [],
        'htmx': [],
        'background_tasks': [],
        'analyzer': [],
        'container_management': [],
        'notifications': [],
        'misc': []
    }
    
    # Categorization rules
    for route, methods in routes:
        route_lower = route.lower()
        
        if route in ['/', '/health']:
            categories['core'].append((route, methods))
        elif 'dashboard' in route_lower:
            categories['dashboard'].append((route, methods))
        elif 'application' in route_lower or 'apps' in route_lower or '/app/' in route_lower:
            categories['applications'].append((route, methods))
        elif 'system' in route_lower or 'health' in route_lower:
            categories['system'].append((route, methods))
        elif 'analysis' in route_lower or 'security' in route_lower or 'performance' in route_lower or 'batch' in route_lower:
            categories['analysis'].append((route, methods))
        elif 'stats' in route_lower or 'statistics' in route_lower:
            categories['statistics'].append((route, methods))
        elif 'model' in route_lower:
            categories['models'].append((route, methods))
        elif 'analyzer' in route_lower:
            categories['analyzer'].append((route, methods))
        elif 'container' in route_lower or 'docker' in route_lower:
            categories['container_management'].append((route, methods))
        elif 'task' in route_lower or 'background' in route_lower:
            categories['background_tasks'].append((route, methods))
        elif 'notification' in route_lower:
            categories['notifications'].append((route, methods))
        elif any(htmx_indicator in route_lower for htmx_indicator in [
            'sidebar', 'recent_activity', 'realtime', 'quick_search'
        ]):
            categories['htmx'].append((route, methods))
        else:
            categories['misc'].append((route, methods))
    
    # Display categorization
    total_routes = sum(len(routes) for routes in categories.values())
    print(f"📊 FOUND {total_routes} ROUTES TO CATEGORIZE")
    print()
    
    for category, route_list in categories.items():
        if route_list:
            print(f"📁 {category.upper()} ({len(route_list)} routes):")
            for route, methods in route_list:
                method_str = f" [{methods}]" if methods else " [GET]"
                print(f"   • {route}{method_str}")
            print()
    
    return categories

def create_migration_plan():
    """Create a detailed migration plan."""
    
    print("📋 MIGRATION PLAN")
    print("=" * 50)
    
    plan = {
        'dashboard.py': [
            '# Dashboard HTMX and realtime endpoints',
            '/dashboard/recent-models',
            '/dashboard/system-status', 
            '/dashboard/activity',
            '/dashboard/stats',
            '/dashboard/system-health',
            '/dashboard/analyzer-status',
            '/dashboard/docker-status',
            '/realtime/dashboard',
            '/sidebar_stats',
            '/recent_activity',
            '/recent_activity_detailed',
            '/system_status_detailed',
            '/models_overview_summary',
            '/performance_chart_data',
            '/security_distribution_data',
            '/system_status',
            '# HTMX dashboard widgets and components'
        ],
        
        'applications.py': [
            '# Application management and container operations',
            '/apps/grid',
            '/applications/<int:app_id>/start',
            '/applications/<int:app_id>/stop', 
            '/applications/<int:app_id>/restart',
            '/applications/<int:app_id>/details',
            '/applications/<int:app_id>/logs',
            '/applications/<int:app_id>/logs_modal',
            '/applications/<int:app_id>',  # DELETE method
            '/logs/application/<int:app_id>',
            '# App container status and management'
        ],
        
        'analysis.py': [
            '# Analysis configuration and execution',
            '/analysis/configure/<int:app_id>',
            '/analysis/start/<int:app_id>',
            '/analysis/security/<int:app_id>',
            '/analysis/performance/<int:app_id>',
            '/analysis/zap/<int:app_id>', 
            '/analysis/ai/<int:app_id>',
            '/batch/create',
            '/batch/<batch_id>/start',
            '/batch/active',
            '# Analysis orchestration and batch operations'
        ],
        
        'system.py': [
            '# System monitoring and health',
            '/system_health',
            '/system/health',
            '/system_status_detailed',
            '/system_health_detailed', 
            '/analyzer/status',
            '/analyzer/ping',
            '/analyzer/start',
            '/analyzer/stop',
            '# System health monitoring and analyzer management'
        ],
        
        'models.py': [
            '# Model container and app management',
            '/model/<model_slug>/container-status',
            '/model/<model_slug>/running-count',
            '/app/<model_slug>/<int:app_num>/status',
            '/app/<model_slug>/<int:app_num>/logs',
            '/models/stats/total',
            '/models/stats/providers',
            '/models/stats/performance',
            '/models/stats/last-updated',
            '/models/providers',
            '/models/list',
            '# Model and app-specific operations'
        ],
        
        'statistics.py': [
            '# Statistics and metrics endpoints (already done)',
            '# Most statistics routes were already migrated',
            '# Remaining HTMX stats endpoints to migrate',
            '/stats_total_models',
            '/stats_models_trend', 
            '/stats_total_apps',
            '/stats_security_tests',
            '/stats_performance_tests',
            '/stats_container_status',
            '/stats_completed_analyses',
            '/stats_analysis_trend',
            '/stats_system_health',
            '/stats_uptime',
            '/stats_running_containers'
        ]
    }
    
    for file_name, routes in plan.items():
        print(f"📄 {file_name}:")
        for route in routes:
            if route.startswith('#'):
                print(f"   {route}")
            else:
                print(f"   • {route}")
        print()
    
    return plan

def show_migration_summary():
    """Show summary of what needs to be done."""
    
    print("🎯 MIGRATION SUMMARY")
    print("=" * 50)
    print("""
Current Status:
✅ core.py - Basic API endpoints (/, health) 
✅ statistics.py - Statistics API endpoints
✅ system.py - System health and metrics
✅ analysis.py - Basic analysis CRUD operations  
✅ applications.py - Application CRUD operations
✅ dashboard.py - Dashboard data endpoints

Need to Migrate:
🔄 Dashboard HTMX endpoints (40+ routes)
🔄 Application container management (15+ routes)  
🔄 Analysis orchestration endpoints (10+ routes)
🔄 System monitoring HTMX endpoints (10+ routes)
🔄 Model container management (8+ routes)
🔄 Statistics HTMX endpoints (15+ routes)

Steps:
1. ✅ Analyze legacy api.py structure
2. 🔄 Migrate dashboard HTMX endpoints  
3. 🔄 Migrate application management endpoints
4. 🔄 Migrate analysis orchestration endpoints
5. 🔄 Migrate system monitoring endpoints
6. 🔄 Migrate model management endpoints
7. 🔄 Migrate remaining statistics endpoints
8. 🔄 Update imports and blueprint registration
9. 🔄 Test all endpoints work in modular structure
10. 🔄 Remove legacy api.py file

Legacy api.py Stats:
- 2,910 lines total
- ~87 route endpoints  
- ~40 HTMX endpoints
- ~20 dashboard widgets
- ~15 container management routes
- Mixed concerns (pages + API + HTMX)
""")

def main():
    """Main migration analysis function."""
    print("🚀 API ROUTE MIGRATION ANALYSIS")
    print("=" * 60)
    print()
    
    # Analyze current structure
    categories = analyze_legacy_routes()
    print()
    
    # Show migration plan  
    plan = create_migration_plan()
    print()
    
    # Show summary
    show_migration_summary()
    
    print("🔧 NEXT STEPS:")
    print("1. Run this script to understand the scope")
    print("2. Use migration functions to move endpoints")
    print("3. Test each module as routes are migrated")
    print("4. Update imports and registrations")
    print("5. Remove legacy api.py when complete")

if __name__ == "__main__":
    main()
