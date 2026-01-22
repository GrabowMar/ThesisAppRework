#!/bin/bash
# Start Docker services - run on remote server

set -e

cd /opt/thesisapp

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker ubuntu
    rm get-docker.sh
    echo "Docker installed. Please log out and log back in for group changes to take effect."
    echo "Then run this script again."
    exit 0
fi

# Start Docker if not running
sudo systemctl start docker
sudo systemctl enable docker

# Build and start containers
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
docker compose down 2>/dev/null || true
docker compose build --parallel
docker compose up -d

echo "Waiting for services to start..."
sleep 10

docker compose ps
echo "✓ Services started"
