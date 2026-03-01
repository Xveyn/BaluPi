#!/bin/bash
# BaluPi One-Click Install Script for Raspberry Pi
set -euo pipefail

INSTALL_DIR="/opt/balupi"
REPO_URL="https://github.com/Xveyn/BaluPi.git"
PYTHON_MIN="3.11"

echo "=== BaluPi Installer ==="
echo ""

# Check Python version
python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $python_version"

if python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"; then
    echo "Python >= $PYTHON_MIN OK"
else
    echo "ERROR: Python >= $PYTHON_MIN required (found $python_version)"
    exit 1
fi

# Install system dependencies
echo ""
echo "Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq git python3-venv python3-pip nginx

# Clone or update repo
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull --ff-only
else
    echo "Cloning repository..."
    sudo mkdir -p "$INSTALL_DIR"
    sudo chown "$USER:$USER" "$INSTALL_DIR"
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# Create virtual environment
echo ""
echo "Setting up Python venv..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -e "./backend[dev]"

# Create data directories
mkdir -p data/{cache/files,cache/thumbnails,logs}

# Create .env if not exists
if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    # Generate secret key
    secret=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    sed -i "s/change-me-in-prod-generate-with-python-secrets/$secret/" .env
    echo "IMPORTANT: Edit .env to configure NAS URL, Tapo credentials, etc."
fi

# Install systemd service
echo ""
echo "Installing systemd service..."
sudo cp deploy/balupi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable balupi

# Configure nginx reverse proxy
echo ""
echo "Configuring nginx..."
sudo cp deploy/nginx.conf /etc/nginx/sites-available/balupi
sudo ln -sf /etc/nginx/sites-available/balupi /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

echo ""
echo "=== Installation complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit /opt/balupi/.env"
echo "  2. sudo systemctl start balupi"
echo "  3. Check: curl http://localhost/api/health"
echo ""
