#!/bin/sh
set -e
# ThesisApp Container Start Script

# Ensure data directory exists
mkdir -p /app/src/data

# Run the Flask application
echo "Starting ThesisApp..."
exec python src/main.py
