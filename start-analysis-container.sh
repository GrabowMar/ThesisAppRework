#!/bin/bash

# Analysis Container Startup Script
# Starts the analysis container with all tools

echo "Starting Analysis Container for Thesis Research Platform..."

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Create necessary directories
echo "Creating directories..."
mkdir -p analysis-results
mkdir -p temp
mkdir -p logs

# Build and start the analysis container
echo "Building analysis container..."
docker-compose -f docker-compose.analysis.yml build

echo "Starting analysis container..."
docker-compose -f docker-compose.analysis.yml up -d

# Wait for container to be ready
echo "Waiting for container to be ready..."
sleep 10

# Check container health
echo "Checking container health..."
for i in {1..30}; do
    if curl -f http://localhost:8080/health &> /dev/null; then
        echo "✓ Analysis container is healthy and ready!"
        break
    else
        echo "Waiting for container... ($i/30)"
        sleep 2
    fi
done

# Show container status
echo ""
echo "Container Status:"
docker-compose -f docker-compose.analysis.yml ps

echo ""
echo "Available Analysis Tools:"
curl -s http://localhost:8080/tools | python -m json.tool 2>/dev/null || echo "Container not responding"

echo ""
echo "Analysis container is ready!"
echo "API available at: http://localhost:8080"
echo "Health check: curl http://localhost:8080/health"
echo "Tools list: curl http://localhost:8080/tools"
echo ""
echo "To stop the container: docker-compose -f docker-compose.analysis.yml down"
