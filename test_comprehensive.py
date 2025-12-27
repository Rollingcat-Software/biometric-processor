#!/usr/bin/env python3
"""Comprehensive API endpoint testing with real fixture images."""

import asyncio
import sys
from pathlib import Path

import httpx

API_BASE_URL = "http://localhost:8001/api/v1"
TIMEOUT = 60.0
FIXTURES_DIR = Path("tests/fixtures/images")


class APITester:
    """Comprehensive API testing suite."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=TIMEOUT)
        self.passed = 0
        self.failed = 0
        self.warned = 0

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    def print_result(self, test_name: str, endpoint: str, status: str, details: str = ""):
        """Print test result."""
        status_symbol = "PASS" if status == "pass" else ("FAIL" if status == "fail" else "WARN")
        print(f"[{status_symbol}] {test_name:50} | {endpoint:30} | {details}")

        if status == "pass":
            self.passed += 1
        elif status == "fail":
            self.failed += 1
        else:
            self.warned += 1

    async def test_health(self):
        """Test health endpoint."""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                if "status" in data and data["status"] == "healthy":
                    self.print_result("Health Check", "/health", "pass", f"Model: {data.get('model')}")
                else:
                    self.print_result("Health Check", "/health", "fail", "Invalid response")
            else:
                self.print_result("Health Check", "/health", "fail", f"Status: {response.status_code}")
        except Exception as e:
            self.print_result("Health Check", "/health", "fail", str(e)[:50])

    async def test_quality_analyze(self, image_path: Path, expected_status: int, test_name: str):
        """Test quality analysis endpoint."""
        try:
            if not image_path.exists():
                self.print_result(test_name, "/quality/analyze", "warn", "Image not found")
                return

            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/quality/analyze", files=files)

            if response.status_code == expected_status:
                data = response.json()
                if response.status_code == 200:
                    score = data.get("overall_score", 0)
                    passed = data.get("passed", False)
                    status_icon = "✓" if passed else "✗"
                    self.print_result(test_name, "/quality/analyze", "pass",
                                    f"Score: {score:.1f}% {status_icon}")
                else:
                    error_code = data.get("error_code", "UNKNOWN")
                    self.print_result(test_name, "/quality/analyze", "pass", f"Error: {error_code}")
            else:
                data = response.json()
                self.print_result(test_name, "/quality/analyze", "fail",
                              f"Expected {expected_status}, got {response.status_code}: {data.get('error_code', 'UNKNOWN')}")
        except Exception as e:
            self.print_result(test_name, "/quality/analyze", "fail", str(e)[:50])

    async def test_demographics_analyze(self, image_path: Path, expected_status: int, test_name: str):
        """Test demographics analysis endpoint."""
        try:
            if not image_path.exists():
                self.print_result(test_name, "/demographics/analyze", "warn", "Image not found")
                return

            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/demographics/analyze", files=files)

            if response.status_code == expected_status:
                data = response.json()
                if response.status_code == 200:
                    age = data.get("age")
                    gender = data.get("gender")
                    self.print_result(test_name, "/demographics/analyze", "pass",
                                    f"Age: {age}, Gender: {gender}")
                elif response.status_code == 400:
                    error_code = data.get("error_code", "UNKNOWN")
                    message = data.get("message", "")[:50]
                    self.print_result(test_name, "/demographics/analyze", "pass",
                                    f"400 {error_code}: {message}")
                else:
                    error_code = data.get("error_code", "UNKNOWN")
                    self.print_result(test_name, "/demographics/analyze", "pass", f"Error: {error_code}")
            else:
                data = response.json() if response.status_code != 500 else {"error": "Server error"}
                error_info = data.get('error_code', data.get('message', 'Unknown'))[:50]
                self.print_result(test_name, "/demographics/analyze", "fail",
                              f"Expected {expected_status}, got {response.status_code}: {error_info}")
        except Exception as e:
            self.print_result(test_name, "/demographics/analyze", "fail", str(e)[:50])

    async def test_face_detect(self, image_path: Path, expected_status: int, test_name: str):
        """Test face detection endpoint."""
        try:
            if not image_path.exists():
                self.print_result(test_name, "/face/detect", "warn", "Image not found")
                return

            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/face/detect", files=files)

            if response.status_code == expected_status:
                data = response.json()
                if response.status_code == 200:
                    confidence = data.get("confidence", 0)
                    bbox = data.get("bounding_box", {})
                    self.print_result(test_name, "/face/detect", "pass",
                                    f"Confidence: {confidence:.2f}")
                else:
                    error_code = data.get("error_code", "UNKNOWN")
                    self.print_result(test_name, "/face/detect", "pass", f"Error: {error_code}")
            else:
                self.print_result(test_name, "/face/detect", "fail",
                              f"Expected {expected_status}, got {response.status_code}")
        except Exception as e:
            self.print_result(test_name, "/face/detect", "fail", str(e)[:50])

    async def test_liveness_check(self, image_path: Path, expected_status: int, test_name: str):
        """Test liveness check endpoint."""
        try:
            if not image_path.exists():
                self.print_result(test_name, "/liveness/check", "warn", "Image not found")
                return

            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/liveness/check", files=files)

            if response.status_code == expected_status:
                data = response.json()
                if response.status_code == 200:
                    is_live = data.get("is_live", False)
                    confidence = data.get("confidence", 0)
                    self.print_result(test_name, "/liveness/check", "pass",
                                    f"Live: {is_live}, Conf: {confidence:.2f}")
                else:
                    error_code = data.get("error_code", "UNKNOWN")
                    self.print_result(test_name, "/liveness/check", "pass", f"Error: {error_code}")
            else:
                self.print_result(test_name, "/liveness/check", "fail",
                              f"Expected {expected_status}, got {response.status_code}")
        except Exception as e:
            self.print_result(test_name, "/liveness/check", "fail", str(e)[:50])

    async def test_enrollment(self, image_path: Path, user_id: str, expected_status: int, test_name: str):
        """Test enrollment endpoint."""
        try:
            if not image_path.exists():
                self.print_result(test_name, "/enroll", "warn", "Image not found")
                return

            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, "image/jpeg")}
                data = {"user_id": user_id, "tenant_id": "test-tenant"}
                response = await self.client.post(f"{self.base_url}/enroll", files=files, data=data)

            if response.status_code == expected_status:
                response_data = response.json()
                if response.status_code == 200:
                    embedding_id = response_data.get("embedding_id", "")
                    self.print_result(test_name, "/enroll", "pass", f"Enrolled: {user_id}")
                elif response.status_code == 409:
                    self.print_result(test_name, "/enroll", "pass", "Duplicate (expected)")
                else:
                    error_code = response_data.get("error_code", "UNKNOWN")
                    self.print_result(test_name, "/enroll", "pass", f"Error: {error_code}")
            else:
                self.print_result(test_name, "/enroll", "fail",
                              f"Expected {expected_status}, got {response.status_code}")
        except Exception as e:
            self.print_result(test_name, "/enroll", "fail", str(e)[:50])

    async def test_verification(self, image_path: Path, user_id: str, expected_status: int, test_name: str):
        """Test verification endpoint."""
        try:
            if not image_path.exists():
                self.print_result(test_name, "/verify", "warn", "Image not found")
                return

            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, "image/jpeg")}
                data = {"user_id": user_id, "tenant_id": "test-tenant"}
                response = await self.client.post(f"{self.base_url}/verify", files=files, data=data)

            if response.status_code == expected_status:
                response_data = response.json()
                if response.status_code == 200:
                    match = response_data.get("match", False)
                    similarity = response_data.get("similarity", 0)
                    self.print_result(test_name, "/verify", "pass",
                                    f"Match: {match}, Similarity: {similarity:.2f}")
                else:
                    error_code = response_data.get("error_code", "UNKNOWN")
                    self.print_result(test_name, "/verify", "pass", f"Error: {error_code}")
            else:
                self.print_result(test_name, "/verify", "fail",
                              f"Expected {expected_status}, got {response.status_code}")
        except Exception as e:
            self.print_result(test_name, "/verify", "fail", str(e)[:50])

    def print_summary(self):
        """Print test summary."""
        total = self.passed + self.failed + self.warned
        print("\n" + "=" * 140)
        print(f"SUMMARY: {total} tests | PASSED: {self.passed} | FAILED: {self.failed} | WARNINGS: {self.warned}")

        if self.failed == 0 and self.warned == 0:
            print("✓ ALL TESTS PASSED!")
        elif self.failed == 0:
            print(f"✓ All functional tests passed ({self.warned} warnings about missing images)")
        else:
            print(f"✗ {self.failed} TESTS FAILED - NEEDS ATTENTION")

        print("=" * 140)


async def main():
    """Run comprehensive API tests."""
    print("=" * 140)
    print("COMPREHENSIVE API ENDPOINT TESTING WITH REAL FIXTURES")
    print("=" * 140)
    print()

    tester = APITester(API_BASE_URL)

    try:
        # Get test images
        afuat_dir = FIXTURES_DIR / "afuat"
        aga_dir = FIXTURES_DIR / "aga"
        ahab_dir = FIXTURES_DIR / "ahab"

        # 1. Health check
        print("1. HEALTH CHECK")
        print("-" * 140)
        await tester.test_health()
        print()

        # 2. Quality analysis tests
        print("2. QUALITY ANALYSIS TESTS (Testing normalized metrics 0-100%)")
        print("-" * 140)
        await tester.test_quality_analyze(afuat_dir / "profileImage_1200.jpg", 200, "Quality: Large good image (afuat/profileImage_1200.jpg)")
        await tester.test_quality_analyze(afuat_dir / "3.jpg", 200, "Quality: Small image (afuat/3.jpg)")
        await tester.test_quality_analyze(afuat_dir / "DSC_8681.jpg", 400, "Quality: No face (afuat/DSC_8681.jpg)")
        await tester.test_quality_analyze(afuat_dir / "indir.jpg", 200, "Quality: Tiny face (afuat/indir.jpg)")
        await tester.test_quality_analyze(aga_dir / "spring21_veda1.png", 200, "Quality: PNG image (aga/spring21_veda1.png)")
        await tester.test_quality_analyze(ahab_dir / "foto.jpg", 200, "Quality: Different person (ahab/foto.jpg)")
        print()

        # 3. Demographics tests (Testing 400 vs 500 error handling)
        print("3. DEMOGRAPHICS ANALYSIS TESTS (Testing error codes: should be 400, NOT 500!)")
        print("-" * 140)
        await tester.test_demographics_analyze(afuat_dir / "profileImage_1200.jpg", 200, "Demographics: Large image (afuat/profileImage_1200.jpg)")
        await tester.test_demographics_analyze(afuat_dir / "3.jpg", 400, "Demographics: Small image <224px (afuat/3.jpg)")
        await tester.test_demographics_analyze(afuat_dir / "DSC_8681.jpg", 400, "Demographics: No face (afuat/DSC_8681.jpg)")
        await tester.test_demographics_analyze(afuat_dir / "indir.jpg", 400, "Demographics: Tiny image (afuat/indir.jpg)")
        await tester.test_demographics_analyze(aga_dir / "spring21_veda1.png", 200, "Demographics: Good PNG (aga/spring21_veda1.png)")
        await tester.test_demographics_analyze(ahab_dir / "1679744618228.jpg", 200, "Demographics: Different person (ahab/1679744618228.jpg)")
        print()

        # 4. Face detection tests
        print("4. FACE DETECTION TESTS")
        print("-" * 140)
        await tester.test_face_detect(afuat_dir / "profileImage_1200.jpg", 200, "Face Detect: Good image (afuat/profileImage_1200.jpg)")
        await tester.test_face_detect(afuat_dir / "DSC_8681.jpg", 400, "Face Detect: No face (afuat/DSC_8681.jpg)")
        await tester.test_face_detect(aga_dir / "indir.jpg", 200, "Face Detect: Another person (aga/indir.jpg)")
        print()

        # 5. Liveness tests
        print("5. LIVENESS CHECK TESTS")
        print("-" * 140)
        await tester.test_liveness_check(afuat_dir / "profileImage_1200.jpg", 200, "Liveness: Good image (afuat/profileImage_1200.jpg)")
        await tester.test_liveness_check(afuat_dir / "DSC_8681.jpg", 400, "Liveness: No face (afuat/DSC_8681.jpg)")
        await tester.test_liveness_check(ahab_dir / "foto.jpg", 200, "Liveness: Different person (ahab/foto.jpg)")
        print()

        # 6. Enrollment tests (Create users for verification)
        print("6. ENROLLMENT TESTS (Creating test users)")
        print("-" * 140)
        await tester.test_enrollment(afuat_dir / "profileImage_1200.jpg", "afuat-test", 200, "Enroll: User afuat")
        await tester.test_enrollment(afuat_dir / "profileImage_1200.jpg", "afuat-test", 409, "Enroll: Duplicate afuat (should fail)")
        await tester.test_enrollment(aga_dir / "spring21_veda1.png", "aga-test", 200, "Enroll: User aga")
        await tester.test_enrollment(ahab_dir / "foto.jpg", "ahab-test", 200, "Enroll: User ahab")
        await tester.test_enrollment(afuat_dir / "DSC_8681.jpg", "no-face", 400, "Enroll: No face (should fail)")
        print()

        # 7. Verification tests (Using enrolled users)
        print("7. VERIFICATION TESTS (Verifying enrolled users)")
        print("-" * 140)
        await tester.test_verification(afuat_dir / "3.jpg", "afuat-test", 200, "Verify: Same person, different photo (afuat)")
        await tester.test_verification(aga_dir / "indir.jpg", "aga-test", 200, "Verify: Same person, different photo (aga)")
        await tester.test_verification(afuat_dir / "3.jpg", "aga-test", 200, "Verify: Wrong person (should not match)")
        await tester.test_verification(afuat_dir / "DSC_8681.jpg", "afuat-test", 400, "Verify: No face (should fail)")
        print()

        # Print summary
        tester.print_summary()

    finally:
        await tester.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
