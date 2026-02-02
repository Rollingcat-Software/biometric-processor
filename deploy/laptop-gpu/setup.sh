#!/usr/bin/env bash
# =============================================================================
# Biometric Processor - Laptop GPU Setup Script
# =============================================================================
# Run this script on a fresh Ubuntu 22.04 laptop with an NVIDIA RTX GPU.
# It installs everything needed to run the biometric API with GPU acceleration
# and exposes it to the internet via Cloudflare Tunnel.
#
# Usage:
#   chmod +x setup.sh
#   sudo ./setup.sh
#
# After running this script:
#   1. Edit /opt/biometric-processor/.env (set DATABASE_URL, CORS_ORIGINS, API_KEY)
#   2. Run: cloudflared tunnel login
#   3. Run: cloudflared tunnel create biometric-api
#   4. Run: cloudflared tunnel route dns biometric-api api.yourdomain.com
#   5. Edit ~/.cloudflared/config.yml (set tunnel ID and hostname)
#   6. Run: sudo cloudflared service install
#   7. Reboot — everything starts automatically
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()   { echo -e "${GREEN}[+]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[x]${NC} $1"; exit 1; }

# =============================================================================
# Pre-flight checks
# =============================================================================

if [ "$EUID" -ne 0 ]; then
    error "Please run as root: sudo ./setup.sh"
fi

if ! lspci | grep -iq nvidia; then
    error "No NVIDIA GPU detected. This script requires an NVIDIA RTX GPU."
fi

log "Starting Biometric Processor laptop GPU setup..."

# =============================================================================
# 1. System packages
# =============================================================================
log "Installing system packages..."
apt-get update
apt-get install -y --no-install-recommends \
    build-essential \
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
    git \
    postgresql \
    postgresql-contrib \
    redis-server

# =============================================================================
# 2. NVIDIA driver (if not already installed)
# =============================================================================
if ! command -v nvidia-smi &>/dev/null; then
    log "Installing NVIDIA drivers..."
    apt-get install -y nvidia-driver-545
    warn "NVIDIA driver installed. A REBOOT is required before continuing."
    warn "After reboot, run this script again — it will skip the driver step."
    exit 0
else
    log "NVIDIA driver already installed: $(nvidia-smi --query-gpu=driver_version --format=csv,noheader)"
fi

# Verify GPU is accessible
nvidia-smi || error "nvidia-smi failed. Check driver installation."

# =============================================================================
# 3. CUDA toolkit (if not already installed)
# =============================================================================
if ! command -v nvcc &>/dev/null; then
    log "Installing CUDA toolkit..."
    apt-get install -y nvidia-cuda-toolkit
fi
log "CUDA: $(nvcc --version | tail -1)"

# =============================================================================
# 4. Create biometric user
# =============================================================================
if ! id -u biometric &>/dev/null; then
    log "Creating 'biometric' system user..."
    useradd --system --create-home --shell /bin/bash biometric
    usermod -aG video biometric  # GPU access
fi

# =============================================================================
# 5. Clone/update the application
# =============================================================================
APP_DIR="/opt/biometric-processor"

if [ -d "$APP_DIR" ]; then
    log "Updating existing installation..."
    cd "$APP_DIR"
    sudo -u biometric git pull origin main 2>/dev/null || warn "Git pull failed — using existing code"
else
    log "Cloning biometric-processor..."
    git clone https://github.com/Rollingcat-Software/biometric-processor.git "$APP_DIR"
    chown -R biometric:biometric "$APP_DIR"
fi

# =============================================================================
# 6. Python virtual environment + GPU dependencies
# =============================================================================
log "Setting up Python environment with GPU support..."
cd "$APP_DIR"

sudo -u biometric python3.11 -m venv venv
VENV="$APP_DIR/venv/bin"

# Install in correct order to avoid dependency conflicts
sudo -u biometric "$VENV/pip" install --upgrade pip
sudo -u biometric "$VENV/pip" install "numpy>=1.26.0,<2.0"
sudo -u biometric "$VENV/pip" install opencv-python-headless>=4.8.0
sudo -u biometric "$VENV/pip" install tensorflow==2.15.0
sudo -u biometric "$VENV/pip" install --no-deps "deepface>=0.0.79"
sudo -u biometric "$VENV/pip" install lightphe
sudo -u biometric "$VENV/pip" install -r requirements-laptop-gpu.txt

# Force headless opencv
sudo -u biometric "$VENV/pip" uninstall -y opencv-python opencv-contrib-python 2>/dev/null || true
sudo -u biometric "$VENV/pip" install --force-reinstall opencv-python-headless>=4.8.0

# Verify GPU TensorFlow
log "Verifying TensorFlow GPU..."
sudo -u biometric "$VENV/python" -c "
import tensorflow as tf
gpus = tf.config.list_physical_devices('GPU')
print(f'TensorFlow {tf.__version__}')
print(f'GPUs found: {len(gpus)}')
for gpu in gpus:
    print(f'  - {gpu.name}')
if not gpus:
    print('WARNING: No GPU detected by TensorFlow. Check CUDA installation.')
"

# =============================================================================
# 7. Environment configuration
# =============================================================================
if [ ! -f "$APP_DIR/.env" ]; then
    log "Creating .env from laptop template..."
    cp "$APP_DIR/deploy/laptop-gpu/.env.laptop" "$APP_DIR/.env"
    chown biometric:biometric "$APP_DIR/.env"
    chmod 600 "$APP_DIR/.env"
    warn "IMPORTANT: Edit /opt/biometric-processor/.env before starting!"
    warn "  - Set DATABASE_URL"
    warn "  - Set CORS_ORIGINS to your Cloudflare domain"
    warn "  - Set API_KEY to a strong random key"
else
    log ".env already exists — skipping"
fi

# =============================================================================
# 8. PostgreSQL setup
# =============================================================================
log "Configuring PostgreSQL..."
systemctl enable postgresql
systemctl start postgresql

# Create database and user (idempotent)
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='biometric'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE USER biometric WITH PASSWORD 'biometric';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='biometric_db'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE biometric_db OWNER biometric;"
sudo -u postgres psql -d biometric_db -c "CREATE EXTENSION IF NOT EXISTS vector;"

log "PostgreSQL ready (biometric_db with pgvector)"

# =============================================================================
# 9. Redis
# =============================================================================
log "Enabling Redis..."
systemctl enable redis-server
systemctl start redis-server

# =============================================================================
# 10. Install systemd service
# =============================================================================
log "Installing systemd service..."
cp "$APP_DIR/deploy/laptop-gpu/biometric-api.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable biometric-api

# =============================================================================
# 11. Install Cloudflare Tunnel
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
# 12. GPU power limit for thermal safety
# =============================================================================
log "Setting GPU power limit to 80W for thermal safety..."
nvidia-smi -pl 80 2>/dev/null || warn "Could not set power limit (may need different value for your GPU)"

# =============================================================================
# Done
# =============================================================================
echo ""
echo "============================================================================="
echo -e "${GREEN}  Setup complete!${NC}"
echo "============================================================================="
echo ""
echo "  Next steps:"
echo ""
echo "  1. Edit the environment file:"
echo "     sudo nano /opt/biometric-processor/.env"
echo ""
echo "  2. Set up Cloudflare Tunnel (as your regular user, not root):"
echo "     cloudflared tunnel login"
echo "     cloudflared tunnel create biometric-api"
echo "     cloudflared tunnel route dns biometric-api api.yourdomain.com"
echo ""
echo "  3. Configure the tunnel:"
echo "     mkdir -p ~/.cloudflared"
echo "     cp /opt/biometric-processor/deploy/laptop-gpu/cloudflared-config.yml ~/.cloudflared/config.yml"
echo "     nano ~/.cloudflared/config.yml  # Fill in tunnel ID and domain"
echo ""
echo "  4. Install cloudflared as a service:"
echo "     sudo cloudflared service install"
echo ""
echo "  5. Start everything:"
echo "     sudo systemctl start biometric-api"
echo "     sudo systemctl start cloudflared"
echo ""
echo "  6. Verify:"
echo "     curl http://localhost:8001/api/v1/health"
echo "     curl https://api.yourdomain.com/api/v1/health"
echo ""
echo "  After reboot, everything starts automatically."
echo "============================================================================="
