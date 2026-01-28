#!/bin/bash
set -e

echo "=== Deployment Agent ==="
echo "Updating system..."
sudo apt-get update -qq
sudo apt-get install -y unzip -qq

echo "Unzipping application..."
unzip -o deploy.zip

echo "Setting permissions..."
chmod +x start.sh

echo "Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo "Docker not found. Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    echo "Adding user to docker group..."
    sudo usermod -aG docker ubuntu
    echo "Docker installed. You may need to reconnect for group changes to take effect."
    # We can try to run with newgrp or just fail and ask for retry.
    # But often on a fresh install we want to just proceed.
    # executing checking script via sudo if group not active
else
    echo "Docker is installed."
fi

echo "Starting Application..."
# Check if we can run docker
if ! docker info &>/dev/null; then
    echo "Docker permission denied or daemon not running. Trying with sudo..."
    sudo ./start.sh start
else
    ./start.sh start
fi

echo "Deployment finished."
