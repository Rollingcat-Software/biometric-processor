#!/bin/bash

# Batch Processing Endpoints Test Script
# Tests batch enrollment and verification endpoints with comprehensive scenarios

BASE_URL="http://localhost:8001/api/v1"
IMAGE_DIR="C:/Users/ahabg/OneDrive/Belgeler/GitHub/FIVUCSAS/biometric-processor/tests/fixtures/images"
RESULTS_FILE="batch_test_results.txt"

echo "======================================" | tee $RESULTS_FILE
echo "BATCH PROCESSING ENDPOINTS TEST" | tee -a $RESULTS_FILE
echo "Started at: $(date)" | tee -a $RESULTS_FILE
echo "======================================" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper function to print test header
print_test() {
    echo -e "\n${YELLOW}TEST $1: $2${NC}" | tee -a $RESULTS_FILE
    echo "----------------------------------------" | tee -a $RESULTS_FILE
}

# Helper function to print success
print_success() {
    echo -e "${GREEN}SUCCESS: $1${NC}" | tee -a $RESULTS_FILE
}

# Helper function to print error
print_error() {
    echo -e "${RED}ERROR: $1${NC}" | tee -a $RESULTS_FILE
}

# Test 1: Batch Enroll - Single Person (Afuat) with 5 images
print_test "1" "Batch Enroll - Afuat (5 images)"
START_TIME=$(date +%s%3N)

curl -X POST "$BASE_URL/batch/enroll" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@$IMAGE_DIR/afuat/3.jpg" \
  -F "files=@$IMAGE_DIR/afuat/4.jpg" \
  -F "files=@$IMAGE_DIR/afuat/h02.jpg" \
  -F "files=@$IMAGE_DIR/afuat/indir.jpg" \
  -F "files=@$IMAGE_DIR/afuat/DSC_8476.jpg" \
  -F 'items=[{"user_id":"afuat_test","tenant_id":"test_tenant"},{"user_id":"afuat_test","tenant_id":"test_tenant"},{"user_id":"afuat_test","tenant_id":"test_tenant"},{"user_id":"afuat_test","tenant_id":"test_tenant"},{"user_id":"afuat_test","tenant_id":"test_tenant"}]' \
  -F "skip_duplicates=false" \
  -s -w "\nHTTP_CODE: %{http_code}\nTIME_TOTAL: %{time_total}s\n" \
  -o /tmp/test1_response.json

END_TIME=$(date +%s%3N)
ELAPSED=$((END_TIME - START_TIME))
echo "Response time: ${ELAPSED}ms" | tee -a $RESULTS_FILE
cat /tmp/test1_response.json | jq '.' | tee -a $RESULTS_FILE

# Test 2: Batch Enroll - Single Person (Aga) with 4 images
print_test "2" "Batch Enroll - Aga (4 images)"
START_TIME=$(date +%s%3N)

curl -X POST "$BASE_URL/batch/enroll" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@$IMAGE_DIR/aga/DSC_8476.jpg" \
  -F "files=@$IMAGE_DIR/aga/DSC_8681.jpg" \
  -F "files=@$IMAGE_DIR/aga/h03.jpg" \
  -F "files=@$IMAGE_DIR/aga/indir.jpg" \
  -F 'items=[{"user_id":"aga_test","tenant_id":"test_tenant"},{"user_id":"aga_test","tenant_id":"test_tenant"},{"user_id":"aga_test","tenant_id":"test_tenant"},{"user_id":"aga_test","tenant_id":"test_tenant"}]' \
  -F "skip_duplicates=false" \
  -s -w "\nHTTP_CODE: %{http_code}\nTIME_TOTAL: %{time_total}s\n" \
  -o /tmp/test2_response.json

END_TIME=$(date +%s%3N)
ELAPSED=$((END_TIME - START_TIME))
echo "Response time: ${ELAPSED}ms" | tee -a $RESULTS_FILE
cat /tmp/test2_response.json | jq '.' | tee -a $RESULTS_FILE

# Test 3: Batch Enroll - Single Person (Ahab) with 2 images
print_test "3" "Batch Enroll - Ahab (2 images)"
START_TIME=$(date +%s%3N)

curl -X POST "$BASE_URL/batch/enroll" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@$IMAGE_DIR/ahab/1679744618228.jpg" \
  -F "files=@$IMAGE_DIR/ahab/foto.jpg" \
  -F 'items=[{"user_id":"ahab_test","tenant_id":"test_tenant"},{"user_id":"ahab_test","tenant_id":"test_tenant"}]' \
  -F "skip_duplicates=false" \
  -s -w "\nHTTP_CODE: %{http_code}\nTIME_TOTAL: %{time_total}s\n" \
  -o /tmp/test3_response.json

END_TIME=$(date +%s%3N)
ELAPSED=$((END_TIME - START_TIME))
echo "Response time: ${ELAPSED}ms" | tee -a $RESULTS_FILE
cat /tmp/test3_response.json | jq '.' | tee -a $RESULTS_FILE

# Test 4: Batch Enroll - Mixed Persons (all 3 persons)
print_test "4" "Batch Enroll - Mixed Persons (all 3)"
START_TIME=$(date +%s%3N)

curl -X POST "$BASE_URL/batch/enroll" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@$IMAGE_DIR/afuat/DSC_8681.jpg" \
  -F "files=@$IMAGE_DIR/aga/DSC_8693.jpg" \
  -F "files=@$IMAGE_DIR/ahab/foto.jpg" \
  -F 'items=[{"user_id":"afuat_mixed","tenant_id":"test_tenant"},{"user_id":"aga_mixed","tenant_id":"test_tenant"},{"user_id":"ahab_mixed","tenant_id":"test_tenant"}]' \
  -F "skip_duplicates=false" \
  -s -w "\nHTTP_CODE: %{http_code}\nTIME_TOTAL: %{time_total}s\n" \
  -o /tmp/test4_response.json

END_TIME=$(date +%s%3N)
ELAPSED=$((END_TIME - START_TIME))
echo "Response time: ${ELAPSED}ms" | tee -a $RESULTS_FILE
cat /tmp/test4_response.json | jq '.' | tee -a $RESULTS_FILE

# Test 5: Batch Enroll - Test skip_duplicates=true
print_test "5" "Batch Enroll - Skip Duplicates (re-enroll afuat_test)"
START_TIME=$(date +%s%3N)

curl -X POST "$BASE_URL/batch/enroll" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@$IMAGE_DIR/afuat/DSC_8719.jpg" \
  -F "files=@$IMAGE_DIR/afuat/profileImage_1200.jpg" \
  -F 'items=[{"user_id":"afuat_test","tenant_id":"test_tenant"},{"user_id":"afuat_test","tenant_id":"test_tenant"}]' \
  -F "skip_duplicates=true" \
  -s -w "\nHTTP_CODE: %{http_code}\nTIME_TOTAL: %{time_total}s\n" \
  -o /tmp/test5_response.json

END_TIME=$(date +%s%3N)
ELAPSED=$((END_TIME - START_TIME))
echo "Response time: ${ELAPSED}ms" | tee -a $RESULTS_FILE
cat /tmp/test5_response.json | jq '.' | tee -a $RESULTS_FILE

# Wait a bit for enrollments to be indexed
sleep 2

# Test 6: Batch Verify - Single Person (Afuat) with correct images
print_test "6" "Batch Verify - Afuat (correct images)"
START_TIME=$(date +%s%3N)

curl -X POST "$BASE_URL/batch/verify" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@$IMAGE_DIR/afuat/spring21_veda1.png" \
  -F "files=@$IMAGE_DIR/afuat/504494494_4335957489965886_7910713263520300979_n.jpg" \
  -F 'items=[{"item_id":"verify_afuat_1","user_id":"afuat_test","tenant_id":"test_tenant"},{"item_id":"verify_afuat_2","user_id":"afuat_test","tenant_id":"test_tenant"}]' \
  -F "threshold=0.6" \
  -s -w "\nHTTP_CODE: %{http_code}\nTIME_TOTAL: %{time_total}s\n" \
  -o /tmp/test6_response.json

END_TIME=$(date +%s%3N)
ELAPSED=$((END_TIME - START_TIME))
echo "Response time: ${ELAPSED}ms" | tee -a $RESULTS_FILE
cat /tmp/test6_response.json | jq '.' | tee -a $RESULTS_FILE

# Test 7: Batch Verify - Multiple Persons (mixed)
print_test "7" "Batch Verify - Multiple Persons (mixed)"
START_TIME=$(date +%s%3N)

curl -X POST "$BASE_URL/batch/verify" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@$IMAGE_DIR/afuat/3.jpg" \
  -F "files=@$IMAGE_DIR/aga/spring21_veda1.png" \
  -F "files=@$IMAGE_DIR/ahab/1679744618228.jpg" \
  -F 'items=[{"item_id":"verify_mix_1","user_id":"afuat_mixed","tenant_id":"test_tenant"},{"item_id":"verify_mix_2","user_id":"aga_mixed","tenant_id":"test_tenant"},{"item_id":"verify_mix_3","user_id":"ahab_mixed","tenant_id":"test_tenant"}]' \
  -F "threshold=0.6" \
  -s -w "\nHTTP_CODE: %{http_code}\nTIME_TOTAL: %{time_total}s\n" \
  -o /tmp/test7_response.json

END_TIME=$(date +%s%3N)
ELAPSED=$((END_TIME - START_TIME))
echo "Response time: ${ELAPSED}ms" | tee -a $RESULTS_FILE
cat /tmp/test7_response.json | jq '.' | tee -a $RESULTS_FILE

# Test 8: Batch Verify - Cross-person verification (should fail)
print_test "8" "Batch Verify - Cross-person (should fail verification)"
START_TIME=$(date +%s%3N)

curl -X POST "$BASE_URL/batch/verify" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@$IMAGE_DIR/afuat/3.jpg" \
  -F "files=@$IMAGE_DIR/aga/h03.jpg" \
  -F 'items=[{"item_id":"cross_1","user_id":"aga_test","tenant_id":"test_tenant"},{"item_id":"cross_2","user_id":"afuat_test","tenant_id":"test_tenant"}]' \
  -F "threshold=0.6" \
  -s -w "\nHTTP_CODE: %{http_code}\nTIME_TOTAL: %{time_total}s\n" \
  -o /tmp/test8_response.json

END_TIME=$(date +%s%3N)
ELAPSED=$((END_TIME - START_TIME))
echo "Response time: ${ELAPSED}ms" | tee -a $RESULTS_FILE
cat /tmp/test8_response.json | jq '.' | tee -a $RESULTS_FILE

# Test 9: Error Handling - Mismatched files and items count
print_test "9" "Error Handling - Mismatched files/items count"
START_TIME=$(date +%s%3N)

curl -X POST "$BASE_URL/batch/enroll" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@$IMAGE_DIR/afuat/3.jpg" \
  -F "files=@$IMAGE_DIR/afuat/4.jpg" \
  -F 'items=[{"user_id":"test_user1","tenant_id":"test_tenant"}]' \
  -F "skip_duplicates=false" \
  -s -w "\nHTTP_CODE: %{http_code}\nTIME_TOTAL: %{time_total}s\n" \
  -o /tmp/test9_response.json

END_TIME=$(date +%s%3N)
ELAPSED=$((END_TIME - START_TIME))
echo "Response time: ${ELAPSED}ms" | tee -a $RESULTS_FILE
cat /tmp/test9_response.json | jq '.' | tee -a $RESULTS_FILE

# Test 10: Error Handling - Invalid JSON in items
print_test "10" "Error Handling - Invalid JSON"
START_TIME=$(date +%s%3N)

curl -X POST "$BASE_URL/batch/enroll" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@$IMAGE_DIR/afuat/3.jpg" \
  -F 'items=INVALID_JSON' \
  -F "skip_duplicates=false" \
  -s -w "\nHTTP_CODE: %{http_code}\nTIME_TOTAL: %{time_total}s\n" \
  -o /tmp/test10_response.json

END_TIME=$(date +%s%3N)
ELAPSED=$((END_TIME - START_TIME))
echo "Response time: ${ELAPSED}ms" | tee -a $RESULTS_FILE
cat /tmp/test10_response.json | jq '.' | tee -a $RESULTS_FILE

# Test 11: Performance Comparison - Batch vs Individual Requests
print_test "11" "Performance - Batch vs Individual (3 enrollments)"

# Individual requests
echo "Individual Requests:" | tee -a $RESULTS_FILE
INDIVIDUAL_START=$(date +%s%3N)

for i in 1 2 3; do
    curl -X POST "$BASE_URL/enroll" \
      -H "Content-Type: multipart/form-data" \
      -F "file=@$IMAGE_DIR/afuat/DSC_847$i.jpg" \
      -F "user_id=perf_test_individual_$i" \
      -F "tenant_id=test_tenant" \
      -s > /dev/null
done

INDIVIDUAL_END=$(date +%s%3N)
INDIVIDUAL_TIME=$((INDIVIDUAL_END - INDIVIDUAL_START))
echo "Total time for 3 individual requests: ${INDIVIDUAL_TIME}ms" | tee -a $RESULTS_FILE

# Batch request
echo "Batch Request:" | tee -a $RESULTS_FILE
BATCH_START=$(date +%s%3N)

curl -X POST "$BASE_URL/batch/enroll" \
  -H "Content-Type: multipart/form-data" \
  -F "files=@$IMAGE_DIR/afuat/DSC_8476.jpg" \
  -F "files=@$IMAGE_DIR/afuat/DSC_8681.jpg" \
  -F "files=@$IMAGE_DIR/afuat/DSC_8719.jpg" \
  -F 'items=[{"user_id":"perf_test_batch_1","tenant_id":"test_tenant"},{"user_id":"perf_test_batch_2","tenant_id":"test_tenant"},{"user_id":"perf_test_batch_3","tenant_id":"test_tenant"}]' \
  -F "skip_duplicates=false" \
  -s > /dev/null

BATCH_END=$(date +%s%3N)
BATCH_TIME=$((BATCH_END - BATCH_START))
echo "Total time for 1 batch request (3 items): ${BATCH_TIME}ms" | tee -a $RESULTS_FILE

# Calculate improvement
IMPROVEMENT=$(echo "scale=2; ($INDIVIDUAL_TIME - $BATCH_TIME) * 100 / $INDIVIDUAL_TIME" | bc)
echo "Batch performance improvement: ${IMPROVEMENT}%" | tee -a $RESULTS_FILE

# Summary
echo "" | tee -a $RESULTS_FILE
echo "======================================" | tee -a $RESULTS_FILE
echo "TEST SUMMARY" | tee -a $RESULTS_FILE
echo "======================================" | tee -a $RESULTS_FILE
echo "Completed at: $(date)" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE
echo "All tests completed. Results saved to: $RESULTS_FILE" | tee -a $RESULTS_FILE
echo "Individual test responses saved to: /tmp/test*_response.json" | tee -a $RESULTS_FILE

# Parse and display success rates
echo "" | tee -a $RESULTS_FILE
echo "DETAILED RESULTS:" | tee -a $RESULTS_FILE
echo "" | tee -a $RESULTS_FILE

for i in {1..10}; do
    if [ -f /tmp/test${i}_response.json ]; then
        echo "Test $i:" | tee -a $RESULTS_FILE
        if command -v jq &> /dev/null; then
            jq -r 'if .total_items then "  Total: \(.total_items), Success: \(.successful), Failed: \(.failed), Skipped: \(.skipped // 0)" else "  " + (.message // .detail // "See JSON response") end' /tmp/test${i}_response.json | tee -a $RESULTS_FILE
        else
            echo "  (jq not available - see /tmp/test${i}_response.json)" | tee -a $RESULTS_FILE
        fi
    fi
done

echo "" | tee -a $RESULTS_FILE
echo "Test execution complete!" | tee -a $RESULTS_FILE
