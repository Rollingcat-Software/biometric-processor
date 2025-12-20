# Manual API Testing Script
# Usage: .\test_api.ps1

$baseUrl = "http://localhost:8001/api/v1"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Biometric Processor API - Manual Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Health Check
Write-Host "[1] Testing Health Endpoint..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$baseUrl/health" -Method Get
    Write-Host "✓ Health Check: " -ForegroundColor Green -NoNewline
    Write-Host "$($response.status)" -ForegroundColor White
    Write-Host "  Model: $($response.model)" -ForegroundColor Gray
    Write-Host "  Detector: $($response.detector)" -ForegroundColor Gray
    Write-Host ""
} catch {
    Write-Host "✗ Health Check Failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
}

# 2. Root Endpoint
Write-Host "[2] Testing Root Endpoint..." -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8001/" -Method Get
    Write-Host "✓ Root Endpoint: " -ForegroundColor Green -NoNewline
    Write-Host "$($response.status)" -ForegroundColor White
    Write-Host "  Service: $($response.service)" -ForegroundColor Gray
    Write-Host "  Version: $($response.version)" -ForegroundColor Gray
    Write-Host ""
} catch {
    Write-Host "✗ Root Endpoint Failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
}

# 3. Test with Image (if provided)
$testImagePath = Read-Host "Enter path to test image (or press Enter to skip)"

if ($testImagePath -and (Test-Path $testImagePath)) {
    Write-Host ""
    Write-Host "[3] Testing Enrollment Endpoint..." -ForegroundColor Yellow
    
    try {
        # Create multipart form data
        $boundary = [System.Guid]::NewGuid().ToString()
        $LF = "`r`n"
        
        # Read image file
        $imageBytes = [System.IO.File]::ReadAllBytes($testImagePath)
        $imageFileName = Split-Path $testImagePath -Leaf
        
        # Build multipart form body
        $bodyLines = @(
            "--$boundary",
            "Content-Disposition: form-data; name=`"user_id`"$LF",
            "test_user_manual_$(Get-Date -Format 'yyyyMMddHHmmss')",
            "--$boundary",
            "Content-Disposition: form-data; name=`"file`"; filename=`"$imageFileName`"",
            "Content-Type: image/jpeg$LF"
        ) -join $LF
        
        $bodyLines += $LF
        
        # Combine text and binary data
        $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyLines)
        $bodyBytes += $imageBytes
        $bodyBytes += [System.Text.Encoding]::UTF8.GetBytes("$LF--$boundary--$LF")
        
        # Make request
        $response = Invoke-RestMethod `
            -Uri "$baseUrl/enroll" `
            -Method Post `
            -ContentType "multipart/form-data; boundary=$boundary" `
            -Body $bodyBytes
        
        Write-Host "✓ Enrollment Success!" -ForegroundColor Green
        Write-Host "  User ID: $($response.user_id)" -ForegroundColor Gray
        Write-Host "  Quality Score: $($response.quality_score)" -ForegroundColor Gray
        Write-Host "  Embedding Dimension: $($response.embedding_dimension)" -ForegroundColor Gray
        Write-Host ""
        
        # Save user_id for verification test
        $enrolledUserId = $response.user_id
        
        # 4. Test Verification
        Write-Host "[4] Testing Verification Endpoint..." -ForegroundColor Yellow
        
        Start-Sleep -Seconds 1
        
        # Build verification request
        $bodyLines = @(
            "--$boundary",
            "Content-Disposition: form-data; name=`"user_id`"$LF",
            $enrolledUserId,
            "--$boundary",
            "Content-Disposition: form-data; name=`"file`"; filename=`"$imageFileName`"",
            "Content-Type: image/jpeg$LF"
        ) -join $LF
        
        $bodyLines += $LF
        $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyLines)
        $bodyBytes += $imageBytes
        $bodyBytes += [System.Text.Encoding]::UTF8.GetBytes("$LF--$boundary--$LF")
        
        $response = Invoke-RestMethod `
            -Uri "$baseUrl/verify" `
            -Method Post `
            -ContentType "multipart/form-data; boundary=$boundary" `
            -Body $bodyBytes
        
        Write-Host "✓ Verification Complete!" -ForegroundColor Green
        Write-Host "  Verified: $($response.verified)" -ForegroundColor Gray
        Write-Host "  Confidence: $($response.confidence)" -ForegroundColor Gray
        Write-Host "  Distance: $($response.distance)" -ForegroundColor Gray
        Write-Host ""
        
    } catch {
        Write-Host "✗ Failed: $($_.Exception.Message)" -ForegroundColor Red
        if ($_.ErrorDetails) {
            Write-Host "  Details: $($_.ErrorDetails.Message)" -ForegroundColor Red
        }
        Write-Host ""
    }
} else {
    Write-Host ""
    Write-Host "[INFO] Skipping image tests - no image provided" -ForegroundColor Gray
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Test Complete! API Docs: http://localhost:8001/docs" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
