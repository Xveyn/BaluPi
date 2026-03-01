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
else
    git pull --ff-only origin main

    # Update dependencies
    echo "Updating dependencies..."
    source .venv/bin/activate
    pip install -e "./backend" --quiet
fi

# Sync frontend from pre-built branch (no Node.js needed)
echo "Syncing frontend..."
source .venv/bin/activate
python3 sync_frontend.py --from-branch frontend

# Restart service
echo "Restarting service..."
sudo systemctl restart balupi

# Reload nginx (picks up any config changes)
sudo nginx -t && sudo systemctl reload nginx

echo "Update complete. New version:"
git log --oneline -1
