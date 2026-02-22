#!/bin/bash
# BaluPi Auto-Update Script
set -euo pipefail

INSTALL_DIR="/opt/balupi"

echo "=== BaluPi Update ==="

cd "$INSTALL_DIR"

# Pull latest changes
echo "Pulling latest changes..."
git fetch origin
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "Already up to date."
    exit 0
fi

git pull --ff-only origin main

# Update dependencies
echo "Updating dependencies..."
source .venv/bin/activate
pip install -e "./backend" --quiet

# Restart service
echo "Restarting service..."
sudo systemctl restart balupi

echo "Update complete. New version:"
git log --oneline -1
