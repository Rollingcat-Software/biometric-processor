#!/bin/bash

# Biometric API Comprehensive Testing Script
# Tests all endpoints with fixture images

BASE_URL="http://localhost:8001/api/v1"
IMAGES_DIR="C:/Users/ahabg/OneDrive/Belgeler/GitHub/FIVUCSAS/biometric-processor/tests/fixtures/images"
LOG_FILE="api_test_results.log"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================" | tee -a $LOG_FILE
echo "Biometric API Comprehensive Test Suite" | tee -a $LOG_FILE
echo "Started at: $(date)" | tee -a $LOG_FILE
echo "========================================" | tee -a $LOG_FILE

# Function to log test results
log_test() {
    local test_name=$1
    local status=$2
    local response=$3
    local time=$4

    echo "" | tee -a $LOG_FILE
    echo "=== TEST: $test_name ===" | tee -a $LOG_FILE
    echo "Status: $status" | tee -a $LOG_FILE
    echo "Response Time: ${time}s" | tee -a $LOG_FILE
    echo "Response: $response" | tee -a $LOG_FILE
    echo "" | tee -a $LOG_FILE
}

# Test 1: ENROLL - Person 1 (afuat) with multiple images
echo -e "${BLUE}>>> TEST 1: Enrolling afuat with multiple images${NC}" | tee -a $LOG_FILE

start_time=$(date +%s.%N)
response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "$BASE_URL/enroll" \
  -F "user_id=afuat" \
  -F "image=@$IMAGES_DIR/afuat/3.jpg" \
  -F "image=@$IMAGES_DIR/afuat/4.jpg" \
  -F "image=@$IMAGES_DIR/afuat/DSC_8476.jpg")
end_time=$(date +%s.%N)
elapsed=$(echo "$end_time - $start_time" | bc)

http_code=$(echo "$response" | tail -2 | head -1)
response_time=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -2)

if [ "$http_code" = "200" ]; then
    log_test "Enroll afuat (multiple images)" "SUCCESS" "$body" "$response_time"
else
    log_test "Enroll afuat (multiple images)" "FAILED (HTTP $http_code)" "$body" "$response_time"
fi

# Test 2: ENROLL - Person 2 (aga) with multiple images
echo -e "${BLUE}>>> TEST 2: Enrolling aga with multiple images${NC}" | tee -a $LOG_FILE

start_time=$(date +%s.%N)
response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "$BASE_URL/enroll" \
  -F "user_id=aga" \
  -F "image=@$IMAGES_DIR/aga/DSC_8476.jpg" \
  -F "image=@$IMAGES_DIR/aga/DSC_8681.jpg" \
  -F "image=@$IMAGES_DIR/aga/h03.jpg")
end_time=$(date +%s.%N)
elapsed=$(echo "$end_time - $start_time" | bc)

http_code=$(echo "$response" | tail -2 | head -1)
response_time=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -2)

if [ "$http_code" = "200" ]; then
    log_test "Enroll aga (multiple images)" "SUCCESS" "$body" "$response_time"
else
    log_test "Enroll aga (multiple images)" "FAILED (HTTP $http_code)" "$body" "$response_time"
fi

# Test 3: ENROLL - Person 3 (ahab) with available images
echo -e "${BLUE}>>> TEST 3: Enrolling ahab with available images${NC}" | tee -a $LOG_FILE

start_time=$(date +%s.%N)
response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "$BASE_URL/enroll" \
  -F "user_id=ahab" \
  -F "image=@$IMAGES_DIR/ahab/1679744618228.jpg" \
  -F "image=@$IMAGES_DIR/ahab/foto.jpg")
end_time=$(date +%s.%N)
elapsed=$(echo "$end_time - $start_time" | bc)

http_code=$(echo "$response" | tail -2 | head -1)
response_time=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -2)

if [ "$http_code" = "200" ]; then
    log_test "Enroll ahab (2 images)" "SUCCESS" "$body" "$response_time"
else
    log_test "Enroll ahab (2 images)" "FAILED (HTTP $http_code)" "$body" "$response_time"
fi

# Test 4: VERIFY - Same person (afuat) with different image
echo -e "${BLUE}>>> TEST 4: Verify afuat with different image${NC}" | tee -a $LOG_FILE

start_time=$(date +%s.%N)
response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "$BASE_URL/verify" \
  -F "user_id=afuat" \
  -F "image=@$IMAGES_DIR/afuat/h02.jpg")
end_time=$(date +%s.%N)
elapsed=$(echo "$end_time - $start_time" | bc)

http_code=$(echo "$response" | tail -2 | head -1)
response_time=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -2)

if [ "$http_code" = "200" ]; then
    log_test "Verify afuat (same person)" "SUCCESS" "$body" "$response_time"
else
    log_test "Verify afuat (same person)" "FAILED (HTTP $http_code)" "$body" "$response_time"
fi

# Test 5: VERIFY - Different person verification (should fail)
echo -e "${BLUE}>>> TEST 5: Verify aga with afuat's image (should fail)${NC}" | tee -a $LOG_FILE

start_time=$(date +%s.%N)
response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "$BASE_URL/verify" \
  -F "user_id=aga" \
  -F "image=@$IMAGES_DIR/afuat/h02.jpg")
end_time=$(date +%s.%N)
elapsed=$(echo "$end_time - $start_time" | bc)

http_code=$(echo "$response" | tail -2 | head -1)
response_time=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -2)

if [ "$http_code" = "200" ]; then
    log_test "Verify aga with afuat's image (negative test)" "SUCCESS" "$body" "$response_time"
else
    log_test "Verify aga with afuat's image (negative test)" "FAILED (HTTP $http_code)" "$body" "$response_time"
fi

# Test 6: VERIFY - aga with own image
echo -e "${BLUE}>>> TEST 6: Verify aga with own image${NC}" | tee -a $LOG_FILE

start_time=$(date +%s.%N)
response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "$BASE_URL/verify" \
  -F "user_id=aga" \
  -F "image=@$IMAGES_DIR/aga/DSC_8693.jpg")
end_time=$(date +%s.%N)
elapsed=$(echo "$end_time - $start_time" | bc)

http_code=$(echo "$response" | tail -2 | head -1)
response_time=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -2)

if [ "$http_code" = "200" ]; then
    log_test "Verify aga (same person)" "SUCCESS" "$body" "$response_time"
else
    log_test "Verify aga (same person)" "FAILED (HTTP $http_code)" "$body" "$response_time"
fi

# Test 7: SEARCH - Search for afuat
echo -e "${BLUE}>>> TEST 7: Search for face (afuat)${NC}" | tee -a $LOG_FILE

start_time=$(date +%s.%N)
response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "$BASE_URL/search" \
  -F "image=@$IMAGES_DIR/afuat/indir.jpg" \
  -F "threshold=0.6")
end_time=$(date +%s.%N)
elapsed=$(echo "$end_time - $start_time" | bc)

http_code=$(echo "$response" | tail -2 | head -1)
response_time=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -2)

if [ "$http_code" = "200" ]; then
    log_test "Search for afuat face" "SUCCESS" "$body" "$response_time"
else
    log_test "Search for afuat face" "FAILED (HTTP $http_code)" "$body" "$response_time"
fi

# Test 8: SEARCH - Search for aga
echo -e "${BLUE}>>> TEST 8: Search for face (aga)${NC}" | tee -a $LOG_FILE

start_time=$(date +%s.%N)
response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "$BASE_URL/search" \
  -F "image=@$IMAGES_DIR/aga/indir.jpg" \
  -F "threshold=0.6")
end_time=$(date +%s.%N)
elapsed=$(echo "$end_time - $start_time" | bc)

http_code=$(echo "$response" | tail -2 | head -1)
response_time=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -2)

if [ "$http_code" = "200" ]; then
    log_test "Search for aga face" "SUCCESS" "$body" "$response_time"
else
    log_test "Search for aga face" "FAILED (HTTP $http_code)" "$body" "$response_time"
fi

# Test 9: LIVENESS - Test on real face image
echo -e "${BLUE}>>> TEST 9: Liveness detection (afuat)${NC}" | tee -a $LOG_FILE

start_time=$(date +%s.%N)
response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "$BASE_URL/liveness" \
  -F "image=@$IMAGES_DIR/afuat/DSC_8476.jpg")
end_time=$(date +%s.%N)
elapsed=$(echo "$end_time - $start_time" | bc)

http_code=$(echo "$response" | tail -2 | head -1)
response_time=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -2)

if [ "$http_code" = "200" ]; then
    log_test "Liveness detection afuat" "SUCCESS" "$body" "$response_time"
else
    log_test "Liveness detection afuat" "FAILED (HTTP $http_code)" "$body" "$response_time"
fi

# Test 10: LIVENESS - Test on another image
echo -e "${BLUE}>>> TEST 10: Liveness detection (aga)${NC}" | tee -a $LOG_FILE

start_time=$(date +%s.%N)
response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "$BASE_URL/liveness" \
  -F "image=@$IMAGES_DIR/aga/h03.jpg")
end_time=$(date +%s.%N)
elapsed=$(echo "$end_time - $start_time" | bc)

http_code=$(echo "$response" | tail -2 | head -1)
response_time=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -2)

if [ "$http_code" = "200" ]; then
    log_test "Liveness detection aga" "SUCCESS" "$body" "$response_time"
else
    log_test "Liveness detection aga" "FAILED (HTTP $http_code)" "$body" "$response_time"
fi

# Test 11: COMPARE - Same person comparison (should match)
echo -e "${BLUE}>>> TEST 11: Compare same person (afuat)${NC}" | tee -a $LOG_FILE

start_time=$(date +%s.%N)
response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "$BASE_URL/compare" \
  -F "image1=@$IMAGES_DIR/afuat/3.jpg" \
  -F "image2=@$IMAGES_DIR/afuat/4.jpg")
end_time=$(date +%s.%N)
elapsed=$(echo "$end_time - $start_time" | bc)

http_code=$(echo "$response" | tail -2 | head -1)
response_time=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -2)

if [ "$http_code" = "200" ]; then
    log_test "Compare same person (afuat)" "SUCCESS" "$body" "$response_time"
else
    log_test "Compare same person (afuat)" "FAILED (HTTP $http_code)" "$body" "$response_time"
fi

# Test 12: COMPARE - Different persons (should not match)
echo -e "${BLUE}>>> TEST 12: Compare different persons (afuat vs aga)${NC}" | tee -a $LOG_FILE

start_time=$(date +%s.%N)
response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "$BASE_URL/compare" \
  -F "image1=@$IMAGES_DIR/afuat/3.jpg" \
  -F "image2=@$IMAGES_DIR/aga/h03.jpg")
end_time=$(date +%s.%N)
elapsed=$(echo "$end_time - $start_time" | bc)

http_code=$(echo "$response" | tail -2 | head -1)
response_time=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -2)

if [ "$http_code" = "200" ]; then
    log_test "Compare different persons (afuat vs aga)" "SUCCESS" "$body" "$response_time"
else
    log_test "Compare different persons (afuat vs aga)" "FAILED (HTTP $http_code)" "$body" "$response_time"
fi

# Test 13: COMPARE - ahab comparison
echo -e "${BLUE}>>> TEST 13: Compare same person (ahab)${NC}" | tee -a $LOG_FILE

start_time=$(date +%s.%N)
response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "$BASE_URL/compare" \
  -F "image1=@$IMAGES_DIR/ahab/1679744618228.jpg" \
  -F "image2=@$IMAGES_DIR/ahab/foto.jpg")
end_time=$(date +%s.%N)
elapsed=$(echo "$end_time - $start_time" | bc)

http_code=$(echo "$response" | tail -2 | head -1)
response_time=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -2)

if [ "$http_code" = "200" ]; then
    log_test "Compare same person (ahab)" "SUCCESS" "$body" "$response_time"
else
    log_test "Compare same person (ahab)" "FAILED (HTTP $http_code)" "$body" "$response_time"
fi

# Test 14: COMPARE - ahab vs afuat
echo -e "${BLUE}>>> TEST 14: Compare different persons (ahab vs afuat)${NC}" | tee -a $LOG_FILE

start_time=$(date +%s.%N)
response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "$BASE_URL/compare" \
  -F "image1=@$IMAGES_DIR/ahab/foto.jpg" \
  -F "image2=@$IMAGES_DIR/afuat/3.jpg")
end_time=$(date +%s.%N)
elapsed=$(echo "$end_time - $start_time" | bc)

http_code=$(echo "$response" | tail -2 | head -1)
response_time=$(echo "$response" | tail -1)
body=$(echo "$response" | head -n -2)

if [ "$http_code" = "200" ]; then
    log_test "Compare different persons (ahab vs afuat)" "SUCCESS" "$body" "$response_time"
else
    log_test "Compare different persons (ahab vs afuat)" "FAILED (HTTP $http_code)" "$body" "$response_time"
fi

echo "" | tee -a $LOG_FILE
echo "========================================" | tee -a $LOG_FILE
echo "Test Suite Completed at: $(date)" | tee -a $LOG_FILE
echo "Results saved to: $LOG_FILE" | tee -a $LOG_FILE
echo "========================================" | tee -a $LOG_FILE
