#!/bin/sh
set -e
# ThesisApp Container Start Script

# Ensure data directory exists
mkdir -p /app/src/data

# Wait for Docker socket to be accessible (if mounted)
if [ -S /var/run/docker.sock ]; then
    echo "Waiting for Docker socket to be accessible..."
    max_wait=30
    waited=0
    while [ $waited -lt $max_wait ]; do
        if docker info >/dev/null 2>&1; then
            echo "Docker socket accessible after ${waited}s"
            break
        fi
        echo "Docker socket not yet accessible... (${waited}/${max_wait}s)"
        sleep 1
        waited=$((waited + 1))
    done

    if [ $waited -ge $max_wait ]; then
        echo "WARNING: Docker socket not accessible after ${max_wait}s - continuing anyway"
        echo "Docker operations may fail and trigger static-only analysis fallback"
    fi
else
    echo "Docker socket not mounted - skipping Docker availability check"
fi

# Run the Flask application
echo "Starting ThesisApp..."
exec python src/main.py
