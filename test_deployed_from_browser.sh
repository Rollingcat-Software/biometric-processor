#!/bin/bash
# Quick Test Script for Deployed API
# Run this from your local machine where you have access to the deployment

API_URL="https://biometric-api-902542798396.europe-west1.run.app/api/v1"

echo "=========================================="
echo "Testing Deployed Biometric API"
echo "=========================================="
echo ""

# Test 1: Health Check
echo "1. Testing Health Endpoint..."
curl -s "$API_URL/health" | jq '.' || curl -s "$API_URL/health"
echo -e "\n"

# Test 2: Quality Analysis (requires an image)
echo "2. Testing Quality Analysis..."
echo "Run this command with your own image:"
echo "  curl -X POST $API_URL/quality/analyze -F \"file=@your-image.jpg\""
echo ""

# Test 3: Face Detection
echo "3. Testing Face Detection..."
echo "Run this command with your own image:"
echo "  curl -X POST $API_URL/face/detect -F \"file=@your-image.jpg\""
echo ""

# Test 4: Demographics
echo "4. Testing Demographics Analysis..."
echo "Run this command with your own image:"
echo "  curl -X POST $API_URL/demographics/analyze -F \"file=@your-image.jpg\""
echo ""

# Test 5: Liveness Check
echo "5. Testing Liveness Check..."
echo "Run this command with your own image:"
echo "  curl -X POST $API_URL/liveness/check -F \"file=@your-image.jpg\""
echo ""

echo "=========================================="
echo "For comprehensive testing, use:"
echo "  python test_deployed_api.py"
echo "=========================================="
