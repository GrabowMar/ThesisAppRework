import traceback
print('Starting import checks...')
try:
    import app.services.docker_manager as dm
    print('docker_manager loaded OK')
except Exception as e:
    print('docker_manager ERROR:', e)
    traceback.print_exc()

try:
    import app.routes.api.api as api
    print('api loaded OK')
except Exception as e:
    print('api ERROR:', e)
    traceback.print_exc()
print('Done.')
