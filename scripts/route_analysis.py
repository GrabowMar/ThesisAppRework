import re
import os

def extract_routes(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all route definitions
        route_pattern = r'@\w+\.route\([\'\"](.*?)[\'\"]'
        routes = re.findall(route_pattern, content)
        return routes
    except Exception as e:
        return []

# Main routes
main_routes = {
    'advanced.py': extract_routes('src/app/routes/advanced.py'),
    'api.py': extract_routes('src/app/routes/api.py'),
    'analysis.py': extract_routes('src/app/routes/analysis.py'),
    'batch.py': extract_routes('src/app/routes/batch.py'),
}

# API folder routes
api_routes = {
    'api/core.py': extract_routes('src/app/routes/api/core.py'),
    'api/models.py': extract_routes('src/app/routes/api/models.py'),
    'api/analysis.py': extract_routes('src/app/routes/api/analysis.py'),
    'api/statistics.py': extract_routes('src/app/routes/api/statistics.py'),
    'api/dashboard.py': extract_routes('src/app/routes/api/dashboard.py'),
    'api/applications.py': extract_routes('src/app/routes/api/applications.py'),
    'api/system.py': extract_routes('src/app/routes/api/system.py'),
}

print('=== ROUTE OVERLAP ANALYSIS ===\n')

# Collect all API routes for comparison
all_main_api_routes = set()
all_new_api_routes = set()

# Main routes that start with /api
for file, routes in main_routes.items():
    for route in routes:
        if route.startswith('/api/'):
            all_main_api_routes.add(route)

# New modular API routes (these will have /api prefix from blueprint registration)
for file, routes in api_routes.items():
    for route in routes:
        # Add /api prefix since these are registered with url_prefix='/api'
        full_route = f'/api{route}' if not route.startswith('/api') else route
        all_new_api_routes.add(full_route)

print('DIRECT OVERLAPS:')
overlaps = all_main_api_routes.intersection(all_new_api_routes)
if overlaps:
    for overlap in sorted(overlaps):
        print(f'  ⚠️  {overlap}')
else:
    print('  ✅ No direct route overlaps found')

print('\nMAIN ROUTES WITH /api PREFIX:')
for route in sorted(all_main_api_routes):
    print(f'  📍 {route}')

print('\nNEW MODULAR API ROUTES:')
for route in sorted(all_new_api_routes):
    print(f'  🆕 {route}')

print('\n=== DETAILED BREAKDOWN BY FILE ===')

print('\n📁 ADVANCED.PY API ROUTES:')
for route in main_routes['advanced.py']:
    if route.startswith('/api/'):
        print(f'  {route}')

print('\n📁 OLD API.PY ROUTES:')
for route in main_routes['api.py']:
    if route.startswith('/'):
        print(f'  /api{route}')

print('\n📁 ANALYSIS.PY ROUTES:')
for route in main_routes['analysis.py']:
    print(f'  /analysis{route}')

print('\n📁 BATCH.PY ROUTES:')
for route in main_routes['batch.py']:
    print(f'  /batch{route}')
