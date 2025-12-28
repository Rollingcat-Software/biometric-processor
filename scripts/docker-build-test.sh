#!/bin/bash
# Local Docker Build Test Script
# Run this before pushing to GCP to catch dependency issues early

set -e

IMAGE_NAME="biometric-api-test"
CONTAINER_NAME="biometric-api-test-container"

echo "=========================================="
echo "Biometric API - Local Docker Build Test"
echo "=========================================="

# Cleanup any existing test containers
echo "[1/5] Cleaning up existing test containers..."
docker rm -f $CONTAINER_NAME 2>/dev/null || true
docker rmi -f $IMAGE_NAME 2>/dev/null || true

# Build the image
echo "[2/5] Building Docker image..."
docker build -t $IMAGE_NAME .

if [ $? -ne 0 ]; then
    echo "ERROR: Docker build failed!"
    exit 1
fi

echo "SUCCESS: Docker image built successfully"

# Test the container starts and responds
echo "[3/5] Starting container for health check..."
docker run -d --name $CONTAINER_NAME -p 8081:8080 \
    -e DATABASE_URL="postgresql://test:test@localhost/test" \
    -e REDIS_URL="redis://localhost:6379" \
    -e SECRET_KEY="test-secret-key" \
    $IMAGE_NAME

# Wait for container to start
echo "[4/5] Waiting for container to be ready (max 60s)..."
for i in {1..30}; do
    if curl -s http://localhost:8081/api/v1/health > /dev/null 2>&1; then
        echo "SUCCESS: Container is healthy!"
        HEALTH_RESPONSE=$(curl -s http://localhost:8081/api/v1/health)
        echo "Health response: $HEALTH_RESPONSE"
        break
    fi

    # Check if container is still running
    if ! docker ps | grep -q $CONTAINER_NAME; then
        echo "ERROR: Container exited unexpectedly!"
        echo "Container logs:"
        docker logs $CONTAINER_NAME
        docker rm -f $CONTAINER_NAME 2>/dev/null || true
        exit 1
    fi

    echo "  Waiting... ($i/30)"
    sleep 2
done

# Final health check
if ! curl -s http://localhost:8081/api/v1/health > /dev/null 2>&1; then
    echo "ERROR: Container failed health check after 60 seconds!"
    echo "Container logs:"
    docker logs $CONTAINER_NAME
    docker rm -f $CONTAINER_NAME 2>/dev/null || true
    exit 1
fi

# Cleanup
echo "[5/5] Cleaning up..."
docker rm -f $CONTAINER_NAME

echo "=========================================="
echo "ALL TESTS PASSED!"
echo "Safe to deploy to GCP Cloud Run"
echo "=========================================="
