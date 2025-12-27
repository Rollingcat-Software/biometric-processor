#!/bin/bash

# Proctoring API Workflow Test Script
# Tests complete proctoring workflow with real images

BASE_URL="http://localhost:8001/api/v1"
TENANT_ID="test-tenant-001"
IMAGE_DIR="C:/Users/ahabg/OneDrive/Belgeler/GitHub/FIVUCSAS/biometric-processor/tests/fixtures/images"

echo "========================================="
echo "PROCTORING API WORKFLOW TEST"
echo "========================================="
echo ""

# Helper function to encode image to base64
encode_image() {
    base64 -w 0 "$1"
}

# Helper function to make API calls with proper headers
api_call() {
    local method=$1
    local endpoint=$2
    local data=$3

    if [ -z "$data" ]; then
        curl -s -X "$method" \
            -H "X-Tenant-ID: $TENANT_ID" \
            -H "Content-Type: application/json" \
            "$BASE_URL$endpoint"
    else
        curl -s -X "$method" \
            -H "X-Tenant-ID: $TENANT_ID" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$BASE_URL$endpoint"
    fi
}

echo "Step 1: Creating proctoring sessions for afuat, aga, and ahab"
echo "================================================================"

# Create session for afuat
echo "Creating session for afuat..."
AFUAT_SESSION=$(api_call POST "/proctoring/sessions" '{
    "exam_id": "EXAM-2025-001",
    "user_id": "afuat",
    "config": {
        "verification_threshold": 0.6,
        "max_verification_failures": 3,
        "enable_object_detection": true,
        "enable_multi_face_detection": true
    },
    "metadata": {
        "exam_name": "Final Exam",
        "subject": "Mathematics"
    }
}')
AFUAT_SESSION_ID=$(echo "$AFUAT_SESSION" | jq -r '.session_id')
echo "Afuat Session ID: $AFUAT_SESSION_ID"
echo "$AFUAT_SESSION" | jq '.'
echo ""

# Create session for aga
echo "Creating session for aga..."
AGA_SESSION=$(api_call POST "/proctoring/sessions" '{
    "exam_id": "EXAM-2025-002",
    "user_id": "aga",
    "config": {
        "verification_threshold": 0.6,
        "max_verification_failures": 3
    }
}')
AGA_SESSION_ID=$(echo "$AGA_SESSION" | jq -r '.session_id')
echo "Aga Session ID: $AGA_SESSION_ID"
echo "$AGA_SESSION" | jq '.'
echo ""

# Create session for ahab
echo "Creating session for ahab..."
AHAB_SESSION=$(api_call POST "/proctoring/sessions" '{
    "exam_id": "EXAM-2025-003",
    "user_id": "ahab",
    "config": {
        "verification_threshold": 0.6,
        "max_verification_failures": 3
    }
}')
AHAB_SESSION_ID=$(echo "$AHAB_SESSION" | jq -r '.session_id')
echo "Ahab Session ID: $AHAB_SESSION_ID"
echo "$AHAB_SESSION" | jq '.'
echo ""

echo ""
echo "Step 2: List all sessions"
echo "================================================================"
ALL_SESSIONS=$(api_call GET "/proctoring/sessions")
echo "$ALL_SESSIONS" | jq '.'
echo ""

echo ""
echo "Step 3: Start sessions with baseline images"
echo "================================================================"

# Start afuat's session
echo "Starting afuat's session with baseline image..."
AFUAT_BASELINE=$(encode_image "$IMAGE_DIR/afuat/3.jpg")
START_AFUAT=$(api_call POST "/proctoring/sessions/$AFUAT_SESSION_ID/start" "{
    \"baseline_image_base64\": \"$AFUAT_BASELINE\"
}")
echo "$START_AFUAT" | jq '.'
echo ""

# Start aga's session
echo "Starting aga's session with baseline image..."
AGA_BASELINE=$(encode_image "$IMAGE_DIR/aga/DSC_8476.jpg")
START_AGA=$(api_call POST "/proctoring/sessions/$AGA_SESSION_ID/start" "{
    \"baseline_image_base64\": \"$AGA_BASELINE\"
}")
echo "$START_AGA" | jq '.'
echo ""

# Start ahab's session
echo "Starting ahab's session with baseline image..."
AHAB_BASELINE=$(encode_image "$IMAGE_DIR/ahab/1679744618228.jpg")
START_AHAB=$(api_call POST "/proctoring/sessions/$AHAB_SESSION_ID/start" "{
    \"baseline_image_base64\": \"$AHAB_BASELINE\"
}")
echo "$START_AHAB" | jq '.'
echo ""

echo ""
echo "Step 4: Submit frames for verification (CORRECT person images)"
echo "================================================================"

# Afuat - correct images (should pass)
echo "Submitting afuat's correct images..."
FRAME_NUM=1
for img in "4.jpg" "h02.jpg"; do
    echo "  Frame $FRAME_NUM: $img"
    FRAME_DATA=$(encode_image "$IMAGE_DIR/afuat/$img")
    RESULT=$(api_call POST "/proctoring/sessions/$AFUAT_SESSION_ID/frames" "{
        \"frame_base64\": \"$FRAME_DATA\",
        \"frame_number\": $FRAME_NUM
    }")
    echo "$RESULT" | jq '{frame_number, risk_score, face_detected, face_matched, incidents_created, processing_time_ms}'
    FRAME_NUM=$((FRAME_NUM + 1))
done
echo ""

# Aga - correct images (should pass)
echo "Submitting aga's correct images..."
FRAME_NUM=1
for img in "DSC_8681.jpg" "DSC_8693.jpg"; do
    echo "  Frame $FRAME_NUM: $img"
    FRAME_DATA=$(encode_image "$IMAGE_DIR/aga/$img")
    RESULT=$(api_call POST "/proctoring/sessions/$AGA_SESSION_ID/frames" "{
        \"frame_base64\": \"$FRAME_DATA\",
        \"frame_number\": $FRAME_NUM
    }")
    echo "$RESULT" | jq '{frame_number, risk_score, face_detected, face_matched, incidents_created, processing_time_ms}'
    FRAME_NUM=$((FRAME_NUM + 1))
done
echo ""

# Ahab - correct image (should pass)
echo "Submitting ahab's correct image..."
FRAME_DATA=$(encode_image "$IMAGE_DIR/ahab/foto.jpg")
RESULT=$(api_call POST "/proctoring/sessions/$AHAB_SESSION_ID/frames" "{
    \"frame_base64\": \"$FRAME_DATA\",
    \"frame_number\": 1
}")
echo "$RESULT" | jq '{frame_number, risk_score, face_detected, face_matched, incidents_created, processing_time_ms}'
echo ""

echo ""
echo "Step 5: Submit WRONG person images (should detect incidents)"
echo "================================================================"

# Submit aga's image to afuat's session (should fail)
echo "Submitting aga's image to afuat's session (IMPERSONATION TEST)..."
WRONG_FRAME=$(encode_image "$IMAGE_DIR/aga/DSC_8476.jpg")
RESULT=$(api_call POST "/proctoring/sessions/$AFUAT_SESSION_ID/frames" "{
    \"frame_base64\": \"$WRONG_FRAME\",
    \"frame_number\": 10
}")
echo "$RESULT" | jq '{frame_number, risk_score, face_detected, face_matched, incidents_created, incidents}'
echo ""

# Submit ahab's image to aga's session (should fail)
echo "Submitting ahab's image to aga's session (IMPERSONATION TEST)..."
WRONG_FRAME=$(encode_image "$IMAGE_DIR/ahab/1679744618228.jpg")
RESULT=$(api_call POST "/proctoring/sessions/$AGA_SESSION_ID/frames" "{
    \"frame_base64\": \"$WRONG_FRAME\",
    \"frame_number\": 10
}")
echo "$RESULT" | jq '{frame_number, risk_score, face_detected, face_matched, incidents_created, incidents}'
echo ""

# Submit afuat's image to ahab's session (should fail)
echo "Submitting afuat's image to ahab's session (IMPERSONATION TEST)..."
WRONG_FRAME=$(encode_image "$IMAGE_DIR/afuat/3.jpg")
RESULT=$(api_call POST "/proctoring/sessions/$AHAB_SESSION_ID/frames" "{
    \"frame_base64\": \"$WRONG_FRAME\",
    \"frame_number\": 10
}")
echo "$RESULT" | jq '{frame_number, risk_score, face_detected, face_matched, incidents_created, incidents}'
echo ""

echo ""
echo "Step 6: Check incidents for each session"
echo "================================================================"

echo "Afuat's incidents:"
api_call GET "/proctoring/sessions/$AFUAT_SESSION_ID/incidents" | jq '.incidents[] | {type: .incident_type, severity, confidence, timestamp}'
echo ""

echo "Aga's incidents:"
api_call GET "/proctoring/sessions/$AGA_SESSION_ID/incidents" | jq '.incidents[] | {type: .incident_type, severity, confidence, timestamp}'
echo ""

echo "Ahab's incidents:"
api_call GET "/proctoring/sessions/$AHAB_SESSION_ID/incidents" | jq '.incidents[] | {type: .incident_type, severity, confidence, timestamp}'
echo ""

echo ""
echo "Step 7: Get session details"
echo "================================================================"

echo "Afuat's session:"
api_call GET "/proctoring/sessions/$AFUAT_SESSION_ID" | jq '{id, user_id, status, risk_score, verification_count, verification_failures, incident_count, verification_success_rate}'
echo ""

echo "Aga's session:"
api_call GET "/proctoring/sessions/$AGA_SESSION_ID" | jq '{id, user_id, status, risk_score, verification_count, verification_failures, incident_count, verification_success_rate}'
echo ""

echo "Ahab's session:"
api_call GET "/proctoring/sessions/$AHAB_SESSION_ID" | jq '{id, user_id, status, risk_score, verification_count, verification_failures, incident_count, verification_success_rate}'
echo ""

echo ""
echo "Step 8: End all sessions"
echo "================================================================"

echo "Ending afuat's session..."
api_call POST "/proctoring/sessions/$AFUAT_SESSION_ID/end" '{"reason": "normal"}' | jq '.'
echo ""

echo "Ending aga's session..."
api_call POST "/proctoring/sessions/$AGA_SESSION_ID/end" '{"reason": "normal"}' | jq '.'
echo ""

echo "Ending ahab's session..."
api_call POST "/proctoring/sessions/$AHAB_SESSION_ID/end" '{"reason": "normal"}' | jq '.'
echo ""

echo ""
echo "Step 9: Final session reports"
echo "================================================================"

echo "Afuat's final session details:"
api_call GET "/proctoring/sessions/$AFUAT_SESSION_ID" | jq '{user_id, status, duration_seconds, risk_score, verification_count, verification_failures, incident_count, termination_reason}'
echo ""

echo "Aga's final session details:"
api_call GET "/proctoring/sessions/$AGA_SESSION_ID" | jq '{user_id, status, duration_seconds, risk_score, verification_count, verification_failures, incident_count, termination_reason}'
echo ""

echo "Ahab's final session details:"
api_call GET "/proctoring/sessions/$AHAB_SESSION_ID" | jq '{user_id, status, duration_seconds, risk_score, verification_count, verification_failures, incident_count, termination_reason}'
echo ""

echo ""
echo "========================================="
echo "TEST COMPLETED"
echo "========================================="
