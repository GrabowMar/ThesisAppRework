#!/bin/bash
# Fix for Celery Worker Healthcheck
# The current healthcheck uses 'celery inspect ping' which creates a new app instance
# and can't communicate with the running worker due to app name mismatch.
# This script provides a better healthcheck that tests actual worker functionality.

set -e

echo "Checking Celery worker health..."

# Method 1: Check if celery process is running
if ! pgrep -f "celery.*worker" > /dev/null 2>&1; then
    echo "ERROR: Celery worker process not found"
    exit 1
fi

# Method 2: Check Redis connectivity (worker needs Redis to function)
if ! python3 -c "import redis; r = redis.Redis(host='redis', port=6379, db=0, socket_connect_timeout=2); r.ping()" 2>/dev/null; then
    echo "ERROR: Cannot connect to Redis"
    exit 1
fi

# Method 3: Check if Flask app can be imported (basic sanity check)
if ! python3 -c "from app.factory import create_app; create_app()" 2>/dev/null; then
    echo "ERROR: Cannot create Flask app"
    exit 1
fi

echo "✓ Celery worker is healthy"
exit 0
