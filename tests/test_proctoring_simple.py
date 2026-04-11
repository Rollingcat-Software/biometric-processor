#!/usr/bin/env python3
"""
Simplified Proctoring API Test
Focus on working endpoints to verify core functionality
"""

import base64
import json
import time
from pathlib import Path
import requests

BASE_URL = "http://localhost:8001/api/v1"
TENANT_ID = "test-tenant-001"
IMAGE_DIR = Path(r"C:\Users\ahabg\OneDrive\Belgeler\GitHub\FIVUCSAS\biometric-processor\tests\fixtures\images")

def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def api_call(method, endpoint, data=None):
    headers = {"X-Tenant-ID": TENANT_ID, "Content-Type": "application/json"}
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"ERROR: {method} {endpoint} - {str(e)}")
        if hasattr(e, 'response') and e.response:
            print(f"  Response: {e.response.text[:200]}")
        return None

print("=" * 80)
print("SIMPLIFIED PROCTORING API TEST")
print("=" * 80)

# Test 1: Create sessions
print("\n1. CREATING SESSIONS")
print("-" * 80)
users = ["afuat", "aga", "ahab"]
sessions = {}

for user_id in users:
    result = api_call("POST", "/proctoring/sessions", {
        "exam_id": f"EXAM-{user_id.upper()}",
        "user_id": user_id,
        "config": {"verification_threshold": 0.6}
    })
    if result:
        sessions[user_id] = result["session_id"]
        print(f"{user_id}: {result['session_id']} (Status: {result['status']})")

# Test 2: List sessions
print("\n2. LISTING ALL SESSIONS")
print("-" * 80)
all_sessions = api_call("GET", "/proctoring/sessions")
if all_sessions:
    print(f"Found {len(all_sessions.get('sessions', []))} sessions")

# Test 3: Start sessions
print("\n3. STARTING SESSIONS WITH BASELINE IMAGES")
print("-" * 80)
baselines = {
    "afuat": "3.jpg",
    "aga": "DSC_8476.jpg",
    "ahab": "1679744618228.jpg"
}

for user_id, img_name in baselines.items():
    if user_id in sessions:
        img_path = IMAGE_DIR / user_id / img_name
        baseline = encode_image(img_path)
        result = api_call("POST", f"/proctoring/sessions/{sessions[user_id]}/start", {
            "baseline_image_base64": baseline
        })
        if result:
            print(f"{user_id}: Started (Baseline: {result.get('has_baseline')})")

# Test 4: Submit ONE frame per session (avoid gaze tracking issues)
print("\n4. SUBMITTING VERIFICATION FRAMES")
print("-" * 80)
test_images = {
    "afuat": "DSC_8476.jpg",  # Using a smaller/different image
    "aga": "h03.jpg",
    "ahab": "foto.jpg"
}

for user_id, img_name in test_images.items():
    if user_id in sessions:
        img_path = IMAGE_DIR / user_id / img_name
        if img_path.exists():
            frame = encode_image(img_path)
            result = api_call("POST", f"/proctoring/sessions/{sessions[user_id]}/frames", {
                "frame_base64": frame,
                "frame_number": 1
            })
            if result:
                print(f"{user_id}: Risk={result.get('risk_score', 0):.3f}, "
                      f"Face={result.get('face_detected')}, "
                      f"Matched={result.get('face_matched')}, "
                      f"Incidents={result.get('incidents_created')}")
            time.sleep(1)

# Test 5: Cross-person verification (impersonation test)
print("\n5. IMPERSONATION TESTS (Submit wrong person's image)")
print("-" * 80)
impersonation_tests = [
    ("afuat", "aga", "DSC_8476.jpg"),  # aga's image to afuat's session
    ("aga", "ahab", "foto.jpg"),        # ahab's image to aga's session
]

for target_user, impostor_user, img_name in impersonation_tests:
    if target_user in sessions:
        img_path = IMAGE_DIR / impostor_user / img_name
        if img_path.exists():
            frame = encode_image(img_path)
            result = api_call("POST", f"/proctoring/sessions/{sessions[target_user]}/frames", {
                "frame_base64": frame,
                "frame_number": 99
            })
            if result:
                print(f"{target_user}'s session + {impostor_user}'s image: "
                      f"Risk={result.get('risk_score', 0):.3f}, "
                      f"Matched={result.get('face_matched')}, "
                      f"Incidents={result.get('incidents_created')}")
            time.sleep(1)

# Test 6: Get session details
print("\n6. SESSION DETAILS")
print("-" * 80)
for user_id in sessions:
    result = api_call("GET", f"/proctoring/sessions/{sessions[user_id]}")
    if result:
        print(f"{user_id}: Status={result['status']}, "
              f"Risk={result['risk_score']:.3f}, "
              f"Incidents={result['incident_count']}, "
              f"Success Rate={result['verification_success_rate']:.1%}")

# Test 7: Get incidents (with error handling)
print("\n7. CHECKING INCIDENTS")
print("-" * 80)
for user_id in sessions:
    print(f"\n{user_id.upper()}:")
    result = api_call("GET", f"/proctoring/sessions/{sessions[user_id]}/incidents")
    if result and result.get("incidents"):
        for inc in result["incidents"][:5]:  # Show first 5
            print(f"  - {inc.get('incident_type', 'UNKNOWN')}: "
                  f"Severity={inc.get('severity', 'N/A')}, "
                  f"Confidence={inc.get('confidence', 0):.2f}")
    else:
        print(f"  No incidents or error retrieving incidents")

# Test 8: End sessions
print("\n8. ENDING SESSIONS")
print("-" * 80)
for user_id in sessions:
    result = api_call("POST", f"/proctoring/sessions/{sessions[user_id]}/end", {
        "reason": "normal"
    })
    if result:
        print(f"{user_id}: Ended (Duration: {result.get('duration_seconds', 0):.1f}s, "
              f"Risk: {result.get('final_risk_score', 0):.3f}, "
              f"Incidents: {result.get('total_incidents', 0)})")

# Final summary
print("\n9. FINAL SESSION REPORTS")
print("-" * 80)
for user_id in sessions:
    result = api_call("GET", f"/proctoring/sessions/{sessions[user_id]}")
    if result:
        print(f"\n{user_id.upper()}:")
        print(f"  Status: {result['status']}")
        print(f"  Duration: {result.get('duration_seconds', 0):.1f}s")
        print(f"  Final Risk Score: {result['risk_score']:.3f}")
        print(f"  Verifications: {result['verification_count']}")
        print(f"  Failures: {result['verification_failures']}")
        print(f"  Incidents: {result['incident_count']}")
        print(f"  Success Rate: {result['verification_success_rate']:.1%}")
        print(f"  Termination: {result.get('termination_reason', 'N/A')}")

print("\n" + "=" * 80)
print("TEST COMPLETED")
print("=" * 80)
