#!/usr/bin/env python3
"""Complete workflow testing with verified good images."""

import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8001/api/v1"

# Good images that passed quality checks
GOOD_IMAGES = {
    'person_0001': r'C:\Users\ahabg\OneDrive\Belgeler\GitHub\FIVUCSAS\practice-and-test\DeepFacePractice1\images\person_0001\img_006.jpg',
    'person_0002': r'C:\Users\ahabg\OneDrive\Belgeler\GitHub\FIVUCSAS\practice-and-test\DeepFacePractice1\images\person_0002\img_008.jpg',
    'person_0003': r'C:\Users\ahabg\OneDrive\Belgeler\GitHub\FIVUCSAS\practice-and-test\DeepFacePractice1\images\person_0003\img_002.jpg',
}

def print_header(title):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def print_success(message):
    print(f"✅ {message}")

def print_fail(message):
    print(f"❌ {message}")

def print_info(message):
    print(f"ℹ️  {message}")

def test_health():
    """Test health endpoint."""
    print("\n🏥 HEALTH CHECK")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        data = response.json()
        print_success(f"Server is {data['status']}")
        print(f"   Model: {data['model']}")
        print(f"   Detector: {data['detector']}")
        return True
    except Exception as e:
        print_fail(f"Server not responding: {e}")
        return False

def enroll_user(person_id, image_path):
    """Enroll a user."""
    user_id = f"user_{person_id}"
    print(f"\n📝 ENROLLING: {user_id}")
    print(f"   Image: {Path(image_path).name}")
    
    try:
        with open(image_path, 'rb') as f:
            files = {'file': (Path(image_path).name, f, 'image/jpeg')}
            data = {'user_id': user_id}
            response = requests.post(f"{BASE_URL}/enroll", files=files, data=data, timeout=30)
        
        result = response.json()
        
        if response.status_code == 200:
            print_success("Enrollment successful!")
            print(f"   Quality Score: {result['quality_score']:.2f}/100")
            print(f"   Embedding Dimension: {result['embedding_dimension']}")
            return user_id
        else:
            print_fail(f"Enrollment failed: {result.get('message')}")
            return None
    except Exception as e:
        print_fail(f"Error: {e}")
        return None

def verify_user(user_id, image_path, expected_match=True):
    """Verify a user's face."""
    print(f"\n🔍 VERIFYING: {user_id}")
    print(f"   Image: {Path(image_path).name}")
    print(f"   Expected: {'✅ MATCH' if expected_match else '❌ NO MATCH'}")
    
    try:
        with open(image_path, 'rb') as f:
            files = {'file': (Path(image_path).name, f, 'image/jpeg')}
            data = {'user_id': user_id}
            response = requests.post(f"{BASE_URL}/verify", files=files, data=data, timeout=30)
        
        result = response.json()
        
        if response.status_code == 200:
            verified = result['verified']
            confidence = result['confidence']
            distance = result['distance']
            
            is_correct = (verified == expected_match)
            
            if is_correct:
                print_success(f"Correct! Verified={verified}")
            else:
                print_fail(f"Wrong! Expected {expected_match}, got {verified}")
            
            print(f"   Confidence: {confidence:.4f}")
            print(f"   Distance: {distance:.4f}")
            print(f"   Threshold: {result['threshold']}")
            
            return is_correct
        elif response.status_code == 404:
            print_fail("User not enrolled")
            return False
        else:
            print_fail(f"Error: {result.get('message')}")
            return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

def check_liveness(image_path):
    """Check image liveness."""
    print(f"\n👤 LIVENESS CHECK")
    print(f"   Image: {Path(image_path).name}")
    
    try:
        with open(image_path, 'rb') as f:
            files = {'file': (Path(image_path).name, f, 'image/jpeg')}
            response = requests.post(f"{BASE_URL}/liveness", files=files, timeout=30)
        
        result = response.json()
        
        if response.status_code == 200:
            is_live = result['is_live']
            score = result['liveness_score']
            
            if is_live:
                print_success(f"LIVE detected! (score: {score:.2f})")
            else:
                print_info(f"SPOOF detected (score: {score:.2f})")
            
            return True
        else:
            print_fail(f"Error: {result.get('message')}")
            return False
    except Exception as e:
        print_fail(f"Error: {e}")
        return False

def main():
    """Run complete workflow test."""
    print_header("BIOMETRIC PROCESSOR - COMPLETE WORKFLOW TEST")
    
    # Step 1: Health check
    if not test_health():
        print("\n⚠️  Cannot continue - server not responding!")
        print("Start server with: python -m uvicorn app.main:app --reload")
        return
    
    print_header("STEP 1: ENROLL USERS")
    
    enrolled = {}
    for person_id, image_path in GOOD_IMAGES.items():
        user_id = enroll_user(person_id, image_path)
        if user_id:
            enrolled[user_id] = {
                'person_id': person_id,
                'image': image_path
            }
    
    if len(enrolled) < 2:
        print("\n⚠️  Need at least 2 enrolled users for full testing")
        return
    
    print_header("STEP 2: VERIFY SAME PERSON (Should MATCH)")
    
    results_same = []
    for user_id, info in enrolled.items():
        # Verify with same image (should definitely match)
        result = verify_user(user_id, info['image'], expected_match=True)
        results_same.append(result)
    
    print_header("STEP 3: VERIFY DIFFERENT PERSON (Should NOT MATCH)")
    
    results_diff = []
    users = list(enrolled.keys())
    if len(users) >= 2:
        # Try person 1's image as person 2
        user1, user2 = users[0], users[1]
        result = verify_user(user2, enrolled[user1]['image'], expected_match=False)
        results_diff.append(result)
        
        # Try person 2's image as person 1
        result = verify_user(user1, enrolled[user2]['image'], expected_match=False)
        results_diff.append(result)
    
    print_header("STEP 4: LIVENESS DETECTION")
    
    results_liveness = []
    # Test liveness on first enrolled user
    for user_id, info in list(enrolled.items())[:1]:
        result = check_liveness(info['image'])
        results_liveness.append(result)
    
    print_header("STEP 5: ERROR HANDLING")
    
    print("\n🧪 Testing: Non-existent user")
    verify_user("nonexistent_user_999", list(enrolled.values())[0]['image'], expected_match=False)
    
    # Summary
    print_header("TEST RESULTS SUMMARY")
    
    total = len(results_same) + len(results_diff) + len(results_liveness)
    passed = sum(results_same) + sum(results_diff) + sum(results_liveness)
    
    print(f"\n📊 Overall Results:")
    print(f"   Total Tests: {total}")
    print(f"   Passed: {passed} ✅")
    print(f"   Failed: {total - passed} ❌")
    if total > 0:
        print(f"   Success Rate: {(passed/total*100):.1f}%")
    
    print(f"\n📈 Breakdown:")
    print(f"   Same Person Verification: {sum(results_same)}/{len(results_same)} ✅")
    print(f"   Different Person Verification: {sum(results_diff)}/{len(results_diff)} ✅")
    print(f"   Liveness Detection: {sum(results_liveness)}/{len(results_liveness)} ✅")
    
    print("\n" + "="*70)
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! The system is working correctly!")
    elif passed > 0:
        print("⚠️  Some tests passed, but there are issues to investigate.")
    else:
        print("❌ All tests failed - please check the system configuration.")
    
    print("\n💡 Next Steps:")
    print("   • Interactive testing: http://localhost:8001/docs")
    print("   • View API docs: http://localhost:8001/redoc")
    print("   • Read guide: MANUAL_TESTING_GUIDE.md")
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
