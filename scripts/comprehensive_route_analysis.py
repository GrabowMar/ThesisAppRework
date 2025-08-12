#!/usr/bin/env python3
"""
Comprehensive Route Analysis Script
==================================

Analyzes all route files for conflicts, duplications, and organizational issues.
"""

import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

def extract_routes_from_file(file_path: Path) -> Dict[str, List[str]]:
    """Extract routes from a Python file with their blueprints."""
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # Find blueprint definition
        blueprint_match = re.search(r'(\w+)\s*=\s*Blueprint\([\'"](\w+)[\'"],.*?url_prefix=[\'"]([^\'"]*)[\'"]', content)
        if not blueprint_match:
            blueprint_match = re.search(r'(\w+)\s*=\s*Blueprint\([\'"](\w+)[\'"]', content)
        
        blueprint_var = blueprint_match.group(1) if blueprint_match else 'unknown'
        blueprint_name = blueprint_match.group(2) if blueprint_match else 'unknown'
        url_prefix = blueprint_match.group(3) if blueprint_match and len(blueprint_match.groups()) > 2 else ''
        
        # Find all route decorators
        route_pattern = r'@' + re.escape(blueprint_var) + r'\.route\([\'"]([^\'"]+)[\'"](?:,\s*methods=\[[^\]]+\])?\)'
        routes = re.findall(route_pattern, content)
        
        # Combine prefix with routes
        full_routes = []
        for route in routes:
            if url_prefix:
                full_route = url_prefix + route
            else:
                full_route = route
            full_routes.append(full_route)
        
        return {
            'blueprint_var': blueprint_var,
            'blueprint_name': blueprint_name,
            'url_prefix': url_prefix,
            'routes': full_routes,
            'raw_routes': routes
        }
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return {'routes': [], 'blueprint_var': 'error', 'blueprint_name': 'error', 'url_prefix': ''}

def normalize_route(route: str) -> str:
    """Normalize route for comparison by removing parameters."""
    # Replace dynamic segments with wildcards
    normalized = re.sub(r'<[^>]+>', '*', route)
    # Remove trailing slashes for comparison
    normalized = normalized.rstrip('/')
    return normalized

def find_conflicts(all_routes: Dict[str, Dict]) -> Dict[str, List]:
    """Find route conflicts across files."""
    conflicts = defaultdict(list)
    route_to_files = defaultdict(list)
    
    # Map each route to the files that define it
    for file_name, file_data in all_routes.items():
        for route in file_data['routes']:
            normalized = normalize_route(route)
            route_to_files[normalized].append((file_name, route, file_data))
    
    # Find conflicts
    for normalized_route, file_list in route_to_files.items():
        if len(file_list) > 1:
            conflicts[normalized_route] = file_list
    
    return dict(conflicts)

def analyze_file_purposes(all_routes: Dict[str, Dict]) -> Dict[str, str]:
    """Analyze the purpose of each route file."""
    purposes = {}
    
    for file_name, file_data in all_routes.items():
        routes = file_data['routes']
        blueprint_name = file_data['blueprint_name']
        
        # Categorize based on routes and blueprint name
        api_routes = [r for r in routes if '/api/' in r]
        page_routes = [r for r in routes if '/api/' not in r and not r.endswith('.json')]
        
        if file_name == 'api.py':
            purposes[file_name] = "API endpoints (mixed functionality)"
        elif file_name == 'main.py':
            purposes[file_name] = "Main dashboard and core pages"
        elif len(api_routes) > 0 and len(page_routes) > 0:
            purposes[file_name] = f"MIXED: {len(page_routes)} pages + {len(api_routes)} API routes"
        elif len(api_routes) > 0:
            purposes[file_name] = f"API-only: {len(api_routes)} endpoints"
        elif len(page_routes) > 0:
            purposes[file_name] = f"Pages-only: {len(page_routes)} routes"
        else:
            purposes[file_name] = "Utility/other"
    
    return purposes

def check_api_organization(all_routes: Dict[str, Dict]) -> Dict[str, List]:
    """Check API route organization issues."""
    issues = defaultdict(list)
    
    for file_name, file_data in all_routes.items():
        routes = file_data['routes']
        
        # Check for mixed concerns
        api_routes = [r for r in routes if '/api/' in r]
        page_routes = [r for r in routes if '/api/' not in r and r != '/']
        
        if api_routes and page_routes and file_name != 'main.py':
            issues['mixed_concerns'].append(f"{file_name}: {len(page_routes)} pages + {len(api_routes)} API routes")
        
        # Check for API routes in non-API files
        if api_routes and file_name not in ['api.py'] and 'api' not in file_name:
            issues['api_in_wrong_file'].append(f"{file_name}: {len(api_routes)} API routes")
        
        # Check for overly large files
        if len(routes) > 20:
            issues['large_files'].append(f"{file_name}: {len(routes)} routes")
    
    return dict(issues)

def main():
    print("=== COMPREHENSIVE ROUTE ANALYSIS ===\n")
    
    # Find all route files
    routes_dir = Path("src/app/routes")
    api_dir = routes_dir / "api"
    
    route_files = []
    
    # Main route files
    for py_file in routes_dir.glob("*.py"):
        if py_file.name != "__init__.py":
            route_files.append(py_file)
    
    # API route files
    if api_dir.exists():
        for py_file in api_dir.glob("*.py"):
            if py_file.name != "__init__.py":
                route_files.append(py_file)
    
    print(f"📁 Found {len(route_files)} route files:")
    for f in route_files:
        print(f"  - {f.relative_to(Path('.'))}")
    print()
    
    # Extract routes from all files
    all_routes = {}
    total_routes = 0
    
    for file_path in route_files:
        file_name = file_path.name
        if file_path.parent.name == "api":
            file_name = f"api/{file_name}"
        
        routes_data = extract_routes_from_file(file_path)
        all_routes[file_name] = routes_data
        total_routes += len(routes_data['routes'])
        
        print(f"📄 {file_name}:")
        print(f"   Blueprint: {routes_data['blueprint_name']} (prefix: '{routes_data['url_prefix']}')")
        print(f"   Routes: {len(routes_data['routes'])}")
        for route in routes_data['routes'][:5]:  # Show first 5 routes
            print(f"     • {route}")
        if len(routes_data['routes']) > 5:
            print(f"     ... and {len(routes_data['routes']) - 5} more")
        print()
    
    print(f"📊 TOTAL ROUTES FOUND: {total_routes}\n")
    
    # Find conflicts
    print("🔍 CHECKING FOR ROUTE CONFLICTS...\n")
    conflicts = find_conflicts(all_routes)
    
    if conflicts:
        print("⚠️  ROUTE CONFLICTS FOUND:")
        for normalized_route, file_list in conflicts.items():
            print(f"\n🚨 Conflict on route pattern: {normalized_route}")
            for file_name, actual_route, file_data in file_list:
                print(f"   📁 {file_name}: {actual_route} (blueprint: {file_data['blueprint_name']})")
    else:
        print("✅ No direct route conflicts found!")
    
    # Analyze file purposes
    print("\n" + "="*60)
    print("📋 FILE PURPOSE ANALYSIS")
    print("="*60)
    
    purposes = analyze_file_purposes(all_routes)
    for file_name, purpose in purposes.items():
        print(f"📄 {file_name}: {purpose}")
    
    # Check API organization
    print("\n" + "="*60)
    print("🏗️  API ORGANIZATION ISSUES")
    print("="*60)
    
    org_issues = check_api_organization(all_routes)
    
    if org_issues:
        for issue_type, issues in org_issues.items():
            print(f"\n🔸 {issue_type.replace('_', ' ').title()}:")
            for issue in issues:
                print(f"   • {issue}")
    else:
        print("✅ No major organization issues found!")
    
    # Specific analysis for problematic patterns
    print("\n" + "="*60)
    print("🎯 SPECIFIC ISSUE ANALYSIS")
    print("="*60)
    
    # Check statistics duplication
    stats_files = [f for f in all_routes.keys() if 'statistics' in f.lower()]
    if len(stats_files) > 1:
        print(f"\n📊 Statistics Route Duplication:")
        for file_name in stats_files:
            routes = all_routes[file_name]['routes']
            print(f"   📁 {file_name}: {len(routes)} routes")
            for route in routes:
                print(f"     • {route}")
    
    # Check analysis duplication  
    analysis_routes = defaultdict(list)
    for file_name, file_data in all_routes.items():
        for route in file_data['routes']:
            if 'analysis' in route.lower():
                analysis_routes[file_name].append(route)
    
    if len(analysis_routes) > 1:
        print(f"\n🔬 Analysis Route Distribution:")
        for file_name, routes in analysis_routes.items():
            print(f"   📁 {file_name}: {len(routes)} analysis routes")
            for route in routes[:3]:
                print(f"     • {route}")
            if len(routes) > 3:
                print(f"     ... and {len(routes) - 3} more")
    
    # Summary and recommendations
    print("\n" + "="*60)
    print("💡 RECOMMENDATIONS")
    print("="*60)
    
    recommendations = []
    
    if conflicts:
        recommendations.append("🔧 Resolve route conflicts by consolidating or renaming duplicate routes")
    
    mixed_files = [f for f, p in purposes.items() if "MIXED" in p]
    if mixed_files:
        recommendations.append(f"🏗️  Separate concerns in mixed files: {', '.join(mixed_files)}")
    
    if len(stats_files) > 1:
        recommendations.append("📊 Consolidate statistics routes into a single, well-organized module")
    
    if len(analysis_routes) > 1:
        recommendations.append("🔬 Review analysis route distribution for potential consolidation")
    
    large_files = [f for f, data in all_routes.items() if len(data['routes']) > 20]
    if large_files:
        recommendations.append(f"📦 Consider breaking down large files: {', '.join(large_files)}")
    
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")
    else:
        print("✅ Route organization looks good overall!")

if __name__ == "__main__":
    main()
