# Local Docker Build Test Script (PowerShell)
# Run this before deployment to catch dependency issues early

$ErrorActionPreference = "Stop"

$IMAGE_NAME = "biometric-api-test"
$CONTAINER_NAME = "biometric-api-test-container"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Biometric API - Local Docker Build Test" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Cleanup any existing test containers
Write-Host "[1/5] Cleaning up existing test containers..." -ForegroundColor Yellow
docker rm -f $CONTAINER_NAME 2>$null
docker rmi -f $IMAGE_NAME 2>$null

# Build the image
Write-Host "[2/5] Building Docker image..." -ForegroundColor Yellow
docker build -t $IMAGE_NAME .

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "SUCCESS: Docker image built successfully" -ForegroundColor Green

# Test the container starts and responds
Write-Host "[3/5] Starting container for health check..." -ForegroundColor Yellow
docker run -d --name $CONTAINER_NAME -p 8081:8080 `
    -e DATABASE_URL="postgresql://test:test@localhost/test" `
    -e REDIS_URL="redis://localhost:6379" `
    -e SECRET_KEY="test-secret-key" `
    $IMAGE_NAME

# Wait for container to start
Write-Host "[4/5] Waiting for container to be ready (max 60s)..." -ForegroundColor Yellow
$healthy = $false
for ($i = 1; $i -le 30; $i++) {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8081/api/v1/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
        Write-Host "SUCCESS: Container is healthy!" -ForegroundColor Green
        Write-Host "Health response: $($response | ConvertTo-Json -Compress)"
        $healthy = $true
        break
    }
    catch {
        # Check if container is still running
        $running = docker ps --filter "name=$CONTAINER_NAME" --format "{{.Names}}"
        if (-not $running) {
            Write-Host "ERROR: Container exited unexpectedly!" -ForegroundColor Red
            Write-Host "Container logs:" -ForegroundColor Red
            docker logs $CONTAINER_NAME
            docker rm -f $CONTAINER_NAME 2>$null
            exit 1
        }

        Write-Host "  Waiting... ($i/30)"
        Start-Sleep -Seconds 2
    }
}

if (-not $healthy) {
    Write-Host "ERROR: Container failed health check after 60 seconds!" -ForegroundColor Red
    Write-Host "Container logs:" -ForegroundColor Red
    docker logs $CONTAINER_NAME
    docker rm -f $CONTAINER_NAME 2>$null
    exit 1
}

# Cleanup
Write-Host "[5/5] Cleaning up..." -ForegroundColor Yellow
docker rm -f $CONTAINER_NAME

Write-Host "==========================================" -ForegroundColor Green
Write-Host "ALL TESTS PASSED!" -ForegroundColor Green
Write-Host "Safe to deploy via Cloudflare Tunnel" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
