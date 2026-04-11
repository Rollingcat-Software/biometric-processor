#!/usr/bin/env python3
"""
Proctoring API Workflow Test Script
Tests complete proctoring workflow with real images
"""

import base64
import json
import os
import time
from pathlib import Path
from typing import Dict, Any
import requests

# Configuration
BASE_URL = "http://localhost:8001/api/v1"
TENANT_ID = "test-tenant-001"
IMAGE_DIR = Path(r"C:\Users\ahabg\OneDrive\Belgeler\GitHub\FIVUCSAS\biometric-processor\tests\fixtures\images")

# Results storage
test_results = {
    "sessions": {},
    "incidents": {},
    "errors": []
}


def encode_image(image_path: Path) -> str:
    """Encode image to base64."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def api_call(method: str, endpoint: str, data: Dict = None) -> Dict[str, Any]:
    """Make API call with proper headers."""
    headers = {
        "X-Tenant-ID": TENANT_ID,
        "Content-Type": "application/json"
    }

    url = f"{BASE_URL}{endpoint}"

    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        else:
            raise ValueError(f"Unsupported method: {method}")

        response.raise_for_status()
        return response.json()
    except Exception as e:
        error_msg = f"API call failed: {method} {endpoint} - {str(e)}"
        print(f"ERROR: {error_msg}")
        test_results["errors"].append(error_msg)
        if hasattr(e, 'response') and e.response is not None:
            try:
                print(f"Response: {e.response.text}")
            except:
                pass
        return None


def print_section(title: str):
    """Print section header."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def print_result(label: str, data: Any):
    """Print result data."""
    print(f"\n{label}:")
    if isinstance(data, dict):
        print(json.dumps(data, indent=2, default=str))
    else:
        print(data)


# ============================================================================
# TEST EXECUTION
# ============================================================================

print("=" * 80)
print("PROCTORING API WORKFLOW TEST")
print("=" * 80)

# Step 1: Create sessions
print_section("Step 1: Creating proctoring sessions for afuat, aga, and ahab")

sessions = {}

print("\nCreating session for afuat...")
afuat_session = api_call("POST", "/proctoring/sessions", {
    "exam_id": "EXAM-2025-001",
    "user_id": "afuat",
    "config": {
        "verification_threshold": 0.6,
        "max_verification_failures": 3,
        "enable_object_detection": True,
        "enable_multi_face_detection": True
    },
    "metadata": {
        "exam_name": "Final Exam",
        "subject": "Mathematics"
    }
})
if afuat_session:
    sessions["afuat"] = afuat_session["session_id"]
    print_result("Afuat Session", {"session_id": afuat_session["session_id"], "status": afuat_session["status"]})

print("\nCreating session for aga...")
aga_session = api_call("POST", "/proctoring/sessions", {
    "exam_id": "EXAM-2025-002",
    "user_id": "aga",
    "config": {
        "verification_threshold": 0.6,
        "max_verification_failures": 3
    }
})
if aga_session:
    sessions["aga"] = aga_session["session_id"]
    print_result("Aga Session", {"session_id": aga_session["session_id"], "status": aga_session["status"]})

print("\nCreating session for ahab...")
ahab_session = api_call("POST", "/proctoring/sessions", {
    "exam_id": "EXAM-2025-003",
    "user_id": "ahab",
    "config": {
        "verification_threshold": 0.6,
        "max_verification_failures": 3
    }
})
if ahab_session:
    sessions["ahab"] = ahab_session["session_id"]
    print_result("Ahab Session", {"session_id": ahab_session["session_id"], "status": ahab_session["status"]})

test_results["sessions"] = sessions

# Step 2: List sessions
print_section("Step 2: List all sessions")
all_sessions = api_call("GET", "/proctoring/sessions")
if all_sessions:
    print_result("All Sessions", {
        "total": all_sessions.get("total", 0),
        "count": len(all_sessions.get("sessions", []))
    })
    for sess in all_sessions.get("sessions", []):
        print(f"  - {sess['user_id']}: {sess['id']} (Status: {sess['status']})")

# Step 3: Start sessions with baseline images
print_section("Step 3: Start sessions with baseline images")

if "afuat" in sessions:
    print("\nStarting afuat's session with baseline image...")
    afuat_baseline = encode_image(IMAGE_DIR / "afuat" / "3.jpg")
    start_result = api_call("POST", f"/proctoring/sessions/{sessions['afuat']}/start", {
        "baseline_image_base64": afuat_baseline
    })
    if start_result:
        print_result("Afuat Started", {
            "status": start_result["status"],
            "has_baseline": start_result["has_baseline"],
            "started_at": start_result["started_at"]
        })

if "aga" in sessions:
    print("\nStarting aga's session with baseline image...")
    aga_baseline = encode_image(IMAGE_DIR / "aga" / "DSC_8476.jpg")
    start_result = api_call("POST", f"/proctoring/sessions/{sessions['aga']}/start", {
        "baseline_image_base64": aga_baseline
    })
    if start_result:
        print_result("Aga Started", {
            "status": start_result["status"],
            "has_baseline": start_result["has_baseline"],
            "started_at": start_result["started_at"]
        })

if "ahab" in sessions:
    print("\nStarting ahab's session with baseline image...")
    ahab_baseline = encode_image(IMAGE_DIR / "ahab" / "1679744618228.jpg")
    start_result = api_call("POST", f"/proctoring/sessions/{sessions['ahab']}/start", {
        "baseline_image_base64": ahab_baseline
    })
    if start_result:
        print_result("Ahab Started", {
            "status": start_result["status"],
            "has_baseline": start_result["has_baseline"],
            "started_at": start_result["started_at"]
        })

# Step 4: Submit correct frames
print_section("Step 4: Submit frames for verification (CORRECT person images)")

# Afuat - correct images
if "afuat" in sessions:
    print("\nSubmitting afuat's correct images...")
    afuat_images = ["4.jpg", "h02.jpg", "indir.jpg"]
    for idx, img_name in enumerate(afuat_images, 1):
        img_path = IMAGE_DIR / "afuat" / img_name
        if img_path.exists():
            print(f"  Frame {idx}: {img_name}")
            frame_data = encode_image(img_path)
            result = api_call("POST", f"/proctoring/sessions/{sessions['afuat']}/frames", {
                "frame_base64": frame_data,
                "frame_number": idx
            })
            if result:
                print(f"    Risk: {result['risk_score']:.3f}, Face: {result['face_detected']}, "
                      f"Matched: {result['face_matched']}, Incidents: {result['incidents_created']}, "
                      f"Time: {result['processing_time_ms']:.1f}ms")
            time.sleep(0.5)

# Aga - correct images
if "aga" in sessions:
    print("\nSubmitting aga's correct images...")
    aga_images = ["DSC_8681.jpg", "DSC_8693.jpg", "h03.jpg"]
    for idx, img_name in enumerate(aga_images, 1):
        img_path = IMAGE_DIR / "aga" / img_name
        if img_path.exists():
            print(f"  Frame {idx}: {img_name}")
            frame_data = encode_image(img_path)
            result = api_call("POST", f"/proctoring/sessions/{sessions['aga']}/frames", {
                "frame_base64": frame_data,
                "frame_number": idx
            })
            if result:
                print(f"    Risk: {result['risk_score']:.3f}, Face: {result['face_detected']}, "
                      f"Matched: {result['face_matched']}, Incidents: {result['incidents_created']}, "
                      f"Time: {result['processing_time_ms']:.1f}ms")
            time.sleep(0.5)

# Ahab - correct image
if "ahab" in sessions:
    print("\nSubmitting ahab's correct image...")
    img_path = IMAGE_DIR / "ahab" / "foto.jpg"
    if img_path.exists():
        print(f"  Frame 1: foto.jpg")
        frame_data = encode_image(img_path)
        result = api_call("POST", f"/proctoring/sessions/{sessions['ahab']}/frames", {
            "frame_base64": frame_data,
            "frame_number": 1
        })
        if result:
            print(f"    Risk: {result['risk_score']:.3f}, Face: {result['face_detected']}, "
                  f"Matched: {result['face_matched']}, Incidents: {result['incidents_created']}, "
                  f"Time: {result['processing_time_ms']:.1f}ms")

# Step 5: Submit wrong person images
print_section("Step 5: Submit WRONG person images (should detect incidents)")

time.sleep(1)

# Submit aga's image to afuat's session
if "afuat" in sessions:
    print("\nSubmitting aga's image to afuat's session (IMPERSONATION TEST)...")
    wrong_frame = encode_image(IMAGE_DIR / "aga" / "DSC_8476.jpg")
    result = api_call("POST", f"/proctoring/sessions/{sessions['afuat']}/frames", {
        "frame_base64": wrong_frame,
        "frame_number": 10
    })
    if result:
        print_result("Impersonation Detection", {
            "risk_score": result["risk_score"],
            "face_detected": result["face_detected"],
            "face_matched": result["face_matched"],
            "incidents_created": result["incidents_created"],
            "incidents": result.get("incidents", [])
        })

time.sleep(0.5)

# Submit ahab's image to aga's session
if "aga" in sessions:
    print("\nSubmitting ahab's image to aga's session (IMPERSONATION TEST)...")
    wrong_frame = encode_image(IMAGE_DIR / "ahab" / "1679744618228.jpg")
    result = api_call("POST", f"/proctoring/sessions/{sessions['aga']}/frames", {
        "frame_base64": wrong_frame,
        "frame_number": 10
    })
    if result:
        print_result("Impersonation Detection", {
            "risk_score": result["risk_score"],
            "face_detected": result["face_detected"],
            "face_matched": result["face_matched"],
            "incidents_created": result["incidents_created"],
            "incidents": result.get("incidents", [])
        })

time.sleep(0.5)

# Submit afuat's image to ahab's session
if "ahab" in sessions:
    print("\nSubmitting afuat's image to ahab's session (IMPERSONATION TEST)...")
    wrong_frame = encode_image(IMAGE_DIR / "afuat" / "3.jpg")
    result = api_call("POST", f"/proctoring/sessions/{sessions['ahab']}/frames", {
        "frame_base64": wrong_frame,
        "frame_number": 10
    })
    if result:
        print_result("Impersonation Detection", {
            "risk_score": result["risk_score"],
            "face_detected": result["face_detected"],
            "face_matched": result["face_matched"],
            "incidents_created": result["incidents_created"],
            "incidents": result.get("incidents", [])
        })

# Step 6: Check incidents
print_section("Step 6: Check incidents for each session")

for user_id, session_id in sessions.items():
    print(f"\n{user_id.upper()}'s incidents:")
    incidents = api_call("GET", f"/proctoring/sessions/{session_id}/incidents")
    if incidents and incidents.get("incidents"):
        test_results["incidents"][user_id] = incidents["incidents"]
        for inc in incidents["incidents"]:
            print(f"  - {inc['incident_type']}: Severity={inc['severity']}, "
                  f"Confidence={inc['confidence']:.2f}, Time={inc['timestamp']}")
    else:
        print("  No incidents")

# Step 7: Get session details
print_section("Step 7: Get session details")

for user_id, session_id in sessions.items():
    print(f"\n{user_id.upper()}'s session:")
    session_details = api_call("GET", f"/proctoring/sessions/{session_id}")
    if session_details:
        print_result("Session Details", {
            "id": session_details["id"],
            "user_id": session_details["user_id"],
            "status": session_details["status"],
            "risk_score": session_details["risk_score"],
            "verification_count": session_details["verification_count"],
            "verification_failures": session_details["verification_failures"],
            "incident_count": session_details["incident_count"],
            "verification_success_rate": f"{session_details['verification_success_rate']:.1%}"
        })

# Step 8: End sessions
print_section("Step 8: End all sessions")

for user_id, session_id in sessions.items():
    print(f"\nEnding {user_id}'s session...")
    end_result = api_call("POST", f"/proctoring/sessions/{session_id}/end", {
        "reason": "normal"
    })
    if end_result:
        print_result(f"{user_id.upper()} Session Ended", {
            "status": end_result["status"],
            "duration_seconds": end_result["duration_seconds"],
            "final_risk_score": end_result["final_risk_score"],
            "total_incidents": end_result["total_incidents"],
            "termination_reason": end_result["termination_reason"]
        })

# Step 9: Final session reports
print_section("Step 9: Final session reports")

for user_id, session_id in sessions.items():
    print(f"\n{user_id.upper()}'s final session details:")
    session_details = api_call("GET", f"/proctoring/sessions/{session_id}")
    if session_details:
        print_result("Final Details", {
            "user_id": session_details["user_id"],
            "status": session_details["status"],
            "duration_seconds": session_details["duration_seconds"],
            "risk_score": session_details["risk_score"],
            "verification_count": session_details["verification_count"],
            "verification_failures": session_details["verification_failures"],
            "incident_count": session_details["incident_count"],
            "termination_reason": session_details["termination_reason"]
        })

# Final Summary
print_section("TEST SUMMARY")

print(f"\nTotal sessions created: {len(sessions)}")
print(f"Total errors encountered: {len(test_results['errors'])}")

if test_results["errors"]:
    print("\nErrors:")
    for error in test_results["errors"]:
        print(f"  - {error}")

print("\nIncident Summary:")
for user_id, incidents in test_results["incidents"].items():
    print(f"  {user_id.upper()}: {len(incidents)} incidents")
    severity_counts = {}
    for inc in incidents:
        severity = inc["severity"]
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
    for severity, count in severity_counts.items():
        print(f"    - {severity}: {count}")

print("\n" + "=" * 80)
print("TEST COMPLETED")
print("=" * 80)
