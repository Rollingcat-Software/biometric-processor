#!/bin/bash
set -e

echo "======================================"
echo "Building Biometric Processor"
echo "======================================"

# Build frontend
echo ""
echo "Building Next.js frontend..."
cd demo-ui
npm ci
npm run build
cd ..
echo "✓ Frontend built successfully"

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install -r requirements.txt
echo "✓ Python dependencies installed"

echo ""
echo "======================================"
echo "Build complete!"
echo "======================================"
echo ""
echo "To run locally:"
echo "  python -m uvicorn app.main:app --host 0.0.0.0 --port 8001"
echo ""
