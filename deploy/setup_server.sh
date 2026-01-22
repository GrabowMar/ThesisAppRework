#!/bin/bash
# Setup server script - run on remote server

set -e

echo "Setting up ThesisApp on server..."

# Create and setup directory
sudo mkdir -p /opt/thesisapp
sudo chown ubuntu:ubuntu /opt/thesisapp

# Clone or update repository
cd /opt
if [ -d thesisapp/.git ]; then
    echo "Updating existing repository..."
    cd thesisapp
    git fetch origin
    git reset --hard origin/main
else
    echo "Cloning repository..."
    git clone https://github.com/GrabowMar/ThesisAppRework.git thesisapp
fi

echo "✓ Code deployed"
