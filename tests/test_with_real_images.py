#!/usr/bin/env python3
"""Comprehensive manual testing with real face images."""

import requests
import json
from pathlib import Path
from datetime import datetime

BASE_URL = "http://localhost:8001/api/v1"
IMAGE_DIR = Path(r"C:\Users\ahabg\OneDrive\Belgeler\GitHub\FIVUCSAS\practice-and-test\DeepFacePractice1\images")

def print_header(title):
    """Print formatted header."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def print_result(success, message):
    """Print formatted result."""
    status = "✅" if success else "❌"
    print(f"{status} {message}")

def test_health():
    """Test health endpoint."""
    print("\n🔍 Testing Health Endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        data = response.json()
        print_result(True, f"Status: {data['status']}")
        print(f"   Model: {data['model']}")
        print(f"   Detector: {data['detector']}")
        print(f"   Version: {data['version']}")
        return True
    except Exception as e:
        print_result(False, f"Health check failed: {e}")
        return False

def enroll_face(image_path, user_id):
    """Enroll a face."""
    print(f"\n📝 Enrolling: {user_id}")
    print(f"   Image: {image_path.name}")
    
    try:
        with open(image_path, "rb") as f:
            files = {"file": (image_path.name, f, "image/jpeg")}
            data = {"user_id": user_id}
            response = requests.post(
                f"{BASE_URL}/enroll",
                files=files,
                data=data,
                timeout=30
            )
        
        result = response.json()
        
        if response.status_code == 200:
            print_result(True, "Enrollment successful")
            print(f"   Quality Score: {result.get('quality_score'):.2f}")
            print(f"   Embedding Dimension: {result.get('embedding_dimension')}")
            return True
        else:
            print_result(False, f"Enrollment failed: {result.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        print_result(False, f"Error: {e}")
        return False

def verify_face(image_path, user_id, expected_match=True):
    """Verify a face."""
    print(f"\n🔍 Verifying: {user_id}")
    print(f"   Image: {image_path.name}")
    print(f"   Expected: {'MATCH' if expected_match else 'NO MATCH'}")
    
    try:
        with open(image_path, "rb") as f:
            files = {"file": (image_path.name, f, "image/jpeg")}
            data = {"user_id": user_id}
            response = requests.post(
                f"{BASE_URL}/verify",
                files=files,
                data=data,
                timeout=30
            )
        
        result = response.json()
        
        if response.status_code == 200:
            verified = result.get('verified')
            confidence = result.get('confidence', 0)
            distance = result.get('distance', 0)
            
            match_correct = (verified == expected_match)
            print_result(match_correct, f"Verification: {result.get('message')}")
            print(f"   Verified: {verified}")
            print(f"   Confidence: {confidence:.4f}")
            print(f"   Distance: {distance:.4f}")
            
            return match_correct
        elif response.status_code == 404:
            print_result(False, "User not enrolled")
            return False
        else:
            print_result(False, f"Error: {result.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        print_result(False, f"Error: {e}")
        return False

def check_liveness(image_path):
    """Check liveness."""
    print(f"\n👤 Liveness Check")
    print(f"   Image: {image_path.name}")
    
    try:
        with open(image_path, "rb") as f:
            files = {"file": (image_path.name, f, "image/jpeg")}
            response = requests.post(
                f"{BASE_URL}/liveness",
                files=files,
                timeout=30
            )
        
        result = response.json()
        
        if response.status_code == 200:
            is_live = result.get('is_live')
            score = result.get('liveness_score', 0)
            print_result(True, f"Liveness: {'LIVE' if is_live else 'SPOOF'}")
            print(f"   Score: {score:.2f}")
            return True
        else:
            print_result(False, f"Error: {result.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        print_result(False, f"Error: {e}")
        return False

def main():
    """Run comprehensive tests."""
    print_header("Biometric Processor API - Real Image Testing")
    
    # Check server health
    if not test_health():
        print("\n⚠️  Server not responding! Make sure it's running.")
        print("   Start with: python -m uvicorn app.main:app --reload")
        return
    
    # Check if images exist
    if not IMAGE_DIR.exists():
        print(f"\n⚠️  Image directory not found: {IMAGE_DIR}")
        return
    
    # Get person directories
    person_dirs = sorted([d for d in IMAGE_DIR.iterdir() if d.is_dir()])
    
    if not person_dirs:
        print(f"\n⚠️  No person directories found in: {IMAGE_DIR}")
        return
    
    print(f"\n📁 Found {len(person_dirs)} person directories")
    for dir in person_dirs:
        images = list(dir.glob("*.jpg")) + list(dir.glob("*.png"))
        print(f"   {dir.name}: {len(images)} images")
    
    # TEST 1: Enrollment
    print_header("TEST 1: Face Enrollment")
    
    enrolled_users = {}
    for person_dir in person_dirs[:2]:  # Test first 2 persons
        images = sorted(list(person_dir.glob("*.jpg")) + list(person_dir.glob("*.png")))
        if images:
            user_id = f"user_{person_dir.name}"
            if enroll_face(images[0], user_id):
                enrolled_users[user_id] = {
                    'dir': person_dir,
                    'enroll_image': images[0],
                    'other_images': images[1:]
                }
    
    if not enrolled_users:
        print("\n⚠️  No users enrolled successfully. Cannot continue testing.")
        return
    
    # TEST 2: Verification (Same Person - Should Match)
    print_header("TEST 2: Verification - Same Person (Should MATCH)")
    
    same_person_results = []
    for user_id, info in enrolled_users.items():
        if info['other_images']:
            # Verify with different image of same person
            test_image = info['other_images'][0]
            result = verify_face(test_image, user_id, expected_match=True)
            same_person_results.append(result)
    
    # TEST 3: Verification (Different Person - Should NOT Match)
    print_header("TEST 3: Verification - Different Person (Should NOT MATCH)")
    
    different_person_results = []
    if len(enrolled_users) >= 2:
        users = list(enrolled_users.keys())
        # Try to verify person 1's image as person 2
        user1, user2 = users[0], users[1]
        test_image = enrolled_users[user1]['other_images'][0] if enrolled_users[user1]['other_images'] else enrolled_users[user1]['enroll_image']
        result = verify_face(test_image, user2, expected_match=False)
        different_person_results.append(result)
    else:
        print("\n⚠️  Need at least 2 enrolled users for this test")
    
    # TEST 4: Liveness Detection
    print_header("TEST 4: Liveness Detection")
    
    liveness_results = []
    for user_id, info in enrolled_users.items():
        result = check_liveness(info['enroll_image'])
        liveness_results.append(result)
        break  # Test only one for now
    
    # TEST 5: Error Handling - User Not Enrolled
    print_header("TEST 5: Error Handling - User Not Enrolled")
    
    if enrolled_users:
        first_user = list(enrolled_users.values())[0]
        verify_face(first_user['enroll_image'], "nonexistent_user_123", expected_match=False)
    
    # Summary
    print_header("TEST SUMMARY")
    
    total_tests = len(same_person_results) + len(different_person_results) + len(liveness_results)
    passed_tests = sum(same_person_results + different_person_results + liveness_results)
    
    print(f"\n📊 Results:")
    print(f"   Total Tests: {total_tests}")
    print(f"   Passed: {passed_tests}")
    print(f"   Failed: {total_tests - passed_tests}")
    print(f"   Success Rate: {(passed_tests/total_tests*100):.1f}%" if total_tests > 0 else "N/A")
    
    print(f"\n📈 Breakdown:")
    print(f"   ✅ Same Person Verification: {sum(same_person_results)}/{len(same_person_results)}")
    print(f"   ✅ Different Person Verification: {sum(different_person_results)}/{len(different_person_results)}")
    print(f"   ✅ Liveness Detection: {sum(liveness_results)}/{len(liveness_results)}")
    
    print("\n" + "="*70)
    print("📚 Interactive Testing: http://localhost:8001/docs")
    print("📖 Full Guide: MANUAL_TESTING_GUIDE.md")
    print("="*70 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
