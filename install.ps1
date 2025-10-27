# FastAPI Installation Script
# Run this to install all dependencies

Write-Host "🔧 Installing FastAPI Biometric Processor Dependencies" -ForegroundColor Cyan
Write-Host ""

# Check Python version
Write-Host "Checking Python version..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
Write-Host "Found: $pythonVersion" -ForegroundColor Gray

if ($pythonVersion -match "3\.(11|12|13)") {
    Write-Host "✓ Python version OK" -ForegroundColor Green
} else {
    Write-Host "⚠ Warning: Recommended Python 3.11 or 3.12" -ForegroundColor Yellow
}

Write-Host ""

# Navigate to biometric-processor
Set-Location -Path $PSScriptRoot

# Remove old venv if exists
if (Test-Path "venv") {
    Write-Host "Removing old virtual environment..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force venv
}

# Create new venv
Write-Host "Creating virtual environment..." -ForegroundColor Cyan
python -m venv venv

# Activate venv
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& ".\venv\Scripts\Activate.ps1"

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip setuptools wheel

# Install packages one by one to avoid conflicts
Write-Host ""
Write-Host "Installing dependencies (this takes 5-10 minutes)..." -ForegroundColor Cyan
Write-Host ""

$packages = @(
    "fastapi",
    "uvicorn[standard]",
    "python-multipart",
    "pillow",
    "numpy<2.0",
    "opencv-python",
    "pydantic",
    "python-dotenv",
    "tf-keras",
    "deepface"
)

foreach ($package in $packages) {
    Write-Host "Installing $package..." -ForegroundColor Yellow
    python -m pip install $package --only-binary=:all: 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ⚠ Failed with binary, trying from source..." -ForegroundColor Yellow
        python -m pip install $package
    }
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ $package installed" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Failed to install $package" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host ""
Write-Host "✅ Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To start the server:" -ForegroundColor Cyan
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "  python -m uvicorn app.main:app --reload --port 8001" -ForegroundColor White
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
