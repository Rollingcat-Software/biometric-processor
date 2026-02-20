#!/bin/bash
# =============================================================================
# Biometric Processor - WSL2 Setup Script
# =============================================================================
# Run this in WSL2 Ubuntu to set up the biometric processor with GPU support.
#
# Prerequisites (from Windows):
#   - WSL2 with Ubuntu
#   - NVIDIA drivers installed (GPU passes through automatically)
#
# Usage:
#   sudo bash setup-wsl.sh
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[+]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[x]${NC} $1"; exit 1; }

# Pre-flight
if [ "$EUID" -ne 0 ]; then
    error "Please run as root: sudo bash setup-wsl.sh"
fi

# Detect if running in WSL
if ! grep -qi microsoft /proc/version; then
    warn "Not running in WSL2. This script is designed for WSL2 Ubuntu."
fi

# Check GPU
if nvidia-smi &>/dev/null; then
    log "GPU detected: $(nvidia-smi --query-gpu=name --format=csv,noheader)"
else
    error "No GPU detected. Ensure NVIDIA drivers are installed on Windows."
fi

log "Starting Biometric Processor WSL2 setup..."

# =============================================================================
# 1. System packages
# =============================================================================
log "Installing system packages..."
apt-get update
apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1 \
    curl \
    git

# =============================================================================
# 2. Create biometric user (optional in WSL)
# =============================================================================
APP_DIR="/opt/biometric-processor"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

if [ -d "$APP_DIR" ]; then
    log "Updating existing installation..."
else
    log "Creating application directory..."
    mkdir -p "$APP_DIR"
fi

# =============================================================================
# 3. Copy application code
# =============================================================================
log "Copying application code from repo..."
cp -r "$REPO_DIR"/* "$APP_DIR/" 2>/dev/null || {
    warn "Could not copy from repo. Assuming code is already in place."
}

# =============================================================================
# 4. Python virtual environment + GPU dependencies
# =============================================================================
log "Setting up Python environment..."
cd "$APP_DIR"

python3.11 -m venv venv
VENV="$APP_DIR/venv/bin"

# Install in correct order
"$VENV/pip" install --upgrade pip
"$VENV/pip" install "numpy>=1.26.0,<2.0"
"$VENV/pip" install opencv-python-headless>=4.8.0
"$VENV/pip" install tensorflow==2.15.0
"$VENV/pip" install --no-deps "deepface>=0.0.79"
"$VENV/pip" install lightphe

# Install remaining GPU requirements if file exists
if [ -f requirements-laptop-gpu.txt ]; then
    "$VENV/pip" install -r requirements-laptop-gpu.txt
elif [ -f requirements.txt ]; then
    warn "requirements-laptop-gpu.txt not found, falling back to requirements.txt"
    "$VENV/pip" install -r requirements.txt
fi

# Force headless opencv
"$VENV/pip" uninstall -y opencv-python opencv-contrib-python 2>/dev/null || true
"$VENV/pip" install --force-reinstall opencv-python-headless>=4.8.0

# =============================================================================
# 5. Verify GPU TensorFlow
# =============================================================================
log "Verifying TensorFlow GPU..."
"$VENV/python" -c "
import tensorflow as tf
gpus = tf.config.list_physical_devices('GPU')
print(f'TensorFlow {tf.__version__}')
print(f'GPUs found: {len(gpus)}')
for gpu in gpus:
    print(f'  - {gpu.name}')
if not gpus:
    print('WARNING: No GPU detected by TensorFlow.')
"

# =============================================================================
# 6. Environment configuration
# =============================================================================
if [ ! -f "$APP_DIR/.env" ]; then
    log "Creating .env from template..."
    cp "$APP_DIR/deploy/laptop-gpu/.env.laptop" "$APP_DIR/.env"

    # Generate API key
    API_KEY=$("$VENV/python" -c "import secrets; print(secrets.token_urlsafe(32))")
    sed -i "s|API_KEY=<CHANGE-THIS-TO-A-STRONG-KEY>|API_KEY=$API_KEY|" "$APP_DIR/.env"

    # Update CORS for your domain
    sed -i "s|api.yourdomain.com|bpa-fivucsas.rollingcatsoftware.com|g" "$APP_DIR/.env"

    chmod 600 "$APP_DIR/.env"
    warn "Created .env with auto-generated API key. Review settings!"
else
    log ".env already exists — skipping"
fi

# =============================================================================
# 7. Install Cloudflare Tunnel
# =============================================================================
if ! command -v cloudflared &>/dev/null; then
    log "Installing cloudflared..."
    curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb \
        -o /tmp/cloudflared.deb
    dpkg -i /tmp/cloudflared.deb
    rm /tmp/cloudflared.deb
fi
log "cloudflared: $(cloudflared --version)"

# =============================================================================
# Done
# =============================================================================
echo ""
echo "============================================================================="
echo -e "${GREEN}  WSL2 Setup Complete!${NC}"
echo "============================================================================="
echo ""
echo "  Start the API:"
echo "    cd /opt/biometric-processor"
echo "    source venv/bin/activate"
echo "    uvicorn app.main:app --host 0.0.0.0 --port 8001"
echo ""
echo "  Set up Cloudflare Tunnel (as your regular user):"
echo "    cloudflared tunnel login"
echo "    cloudflared tunnel create biometric-api"
echo "    cloudflared tunnel route dns biometric-api bpa-fivucsas.rollingcatsoftware.com"
echo ""
echo "  Configure tunnel (~/.cloudflared/config.yml):"
echo "    tunnel: <TUNNEL_ID>"
echo "    credentials-file: ~/.cloudflared/<TUNNEL_ID>.json"
echo "    ingress:"
echo "      - hostname: bpa-fivucsas.rollingcatsoftware.com"
echo "        service: http://localhost:8001"
echo "      - service: http_status:404"
echo ""
echo "  Run tunnel:"
echo "    cloudflared tunnel run biometric-api"
echo ""
echo "  Test:"
echo "    curl http://localhost:8001/api/v1/health"
echo "    curl https://bpa-fivucsas.rollingcatsoftware.com/api/v1/health"
echo ""
echo "============================================================================="
