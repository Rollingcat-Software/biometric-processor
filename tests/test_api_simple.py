#!/usr/bin/env python3
"""Simple manual API testing script."""

import requests
import json
import sys
from pathlib import Path

BASE_URL = "http://localhost:8001/api/v1"

def print_separator():
    print("\n" + "="*60 + "\n")

def test_health():
    """Test health endpoint."""
    print("🔍 Testing Health Endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"✅ Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def test_root():
    """Test root endpoint."""
    print("🔍 Testing Root Endpoint...")
    try:
        response = requests.get("http://localhost:8001/", timeout=5)
        print(f"✅ Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def test_enroll(image_path, user_id="test_user_python"):
    """Test enrollment endpoint."""
    print(f"🔍 Testing Enrollment for user: {user_id}...")
    
    if not Path(image_path).exists():
        print(f"❌ Image not found: {image_path}")
        return None
    
    try:
        with open(image_path, "rb") as f:
            files = {"file": (Path(image_path).name, f, "image/jpeg")}
            data = {"user_id": user_id}
            response = requests.post(
                f"{BASE_URL}/enroll", 
                files=files, 
                data=data,
                timeout=30
            )
            
        print(f"✅ Status: {response.status_code}")
        result = response.json()
        print(json.dumps(result, indent=2))
        
        if response.status_code == 200:
            return result.get("user_id")
        return None
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        return None

def test_verify(image_path, user_id):
    """Test verification endpoint."""
    print(f"🔍 Testing Verification for user: {user_id}...")
    
    if not Path(image_path).exists():
        print(f"❌ Image not found: {image_path}")
        return False
    
    try:
        with open(image_path, "rb") as f:
            files = {"file": (Path(image_path).name, f, "image/jpeg")}
            data = {"user_id": user_id}
            response = requests.post(
                f"{BASE_URL}/verify", 
                files=files, 
                data=data,
                timeout=30
            )
            
        print(f"✅ Status: {response.status_code}")
        result = response.json()
        print(json.dumps(result, indent=2))
        return response.status_code == 200
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def test_liveness(image_path):
    """Test liveness endpoint."""
    print("🔍 Testing Liveness Detection...")
    
    if not Path(image_path).exists():
        print(f"❌ Image not found: {image_path}")
        return False
    
    try:
        with open(image_path, "rb") as f:
            files = {"file": (Path(image_path).name, f, "image/jpeg")}
            response = requests.post(
                f"{BASE_URL}/liveness", 
                files=files,
                timeout=30
            )
            
        print(f"✅ Status: {response.status_code}")
        result = response.json()
        print(json.dumps(result, indent=2))
        return response.status_code == 200
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def main():
    """Main test runner."""
    print("="*60)
    print("  Biometric Processor API - Manual Test (Python)")
    print("="*60)
    
    # Test health and root
    print_separator()
    health_ok = test_health()
    
    print_separator()
    root_ok = test_root()
    
    if not (health_ok and root_ok):
        print("\n⚠️  Server not responding properly. Make sure it's running!")
        print("   Start with: python -m uvicorn app.main:app --reload")
        return
    
    # Ask for image path
    print_separator()
    print("To test with images, provide a path to a face photo.")
    print("Press Enter to skip image tests.\n")
    
    image_path = input("Enter path to test image: ").strip().strip('"')
    
    if not image_path:
        print("\n✅ Basic tests passed! Image tests skipped.")
        print("\n📚 Docs: http://localhost:8001/docs")
        return
    
    # Test enrollment
    print_separator()
    enrolled_user = test_enroll(image_path)
    
    if enrolled_user:
        # Test verification with same image
        print_separator()
        test_verify(image_path, enrolled_user)
        
        # Test liveness
        print_separator()
        test_liveness(image_path)
    
    # Summary
    print_separator()
    print("✅ Testing Complete!")
    print("\n📚 API Documentation: http://localhost:8001/docs")
    print("📖 Full guide: See MANUAL_TESTING_GUIDE.md")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
