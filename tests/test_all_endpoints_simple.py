#!/usr/bin/env python3
"""Comprehensive API endpoint testing script - Simple version."""

import asyncio
import json
import sys
from pathlib import Path

import httpx

API_BASE_URL = "http://localhost:8001/api/v1"
TIMEOUT = 30.0


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
        print(f"[{status_symbol}] {test_name:45} | {endpoint:25} | {details}")

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

    async def test_quality_analyze(self, image_path: str, expected_status: int, test_name: str):
        """Test quality analysis endpoint."""
        try:
            if not Path(image_path).exists():
                self.print_result(test_name, "/quality/analyze", "warn", f"Image not found")
                return

            with open(image_path, "rb") as f:
                files = {"file": (Path(image_path).name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/quality/analyze", files=files)

            if response.status_code == expected_status:
                data = response.json()
                if response.status_code == 200:
                    score = data.get("overall_score", 0)
                    self.print_result(test_name, "/quality/analyze", "pass", f"Score: {score:.1f}%")
                else:
                    error_code = data.get("error_code", "UNKNOWN")
                    self.print_result(test_name, "/quality/analyze", "pass", f"Error: {error_code}")
            else:
                self.print_result(test_name, "/quality/analyze", "fail",
                              f"Expected {expected_status}, got {response.status_code}")
        except Exception as e:
            self.print_result(test_name, "/quality/analyze", "fail", str(e)[:50])

    async def test_demographics_analyze(self, image_path: str, expected_status: int, test_name: str):
        """Test demographics analysis endpoint."""
        try:
            if not Path(image_path).exists():
                self.print_result(test_name, "/demographics/analyze", "warn", "Image not found")
                return

            with open(image_path, "rb") as f:
                files = {"file": (Path(image_path).name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/demographics/analyze", files=files)

            if response.status_code == expected_status:
                data = response.json()
                if response.status_code == 200:
                    age = data.get("age")
                    gender = data.get("gender")
                    self.print_result(test_name, "/demographics/analyze", "pass", f"Age: {age}, Gender: {gender}")
                else:
                    error_code = data.get("error_code", "UNKNOWN")
                    message = data.get("message", "")[:40]
                    self.print_result(test_name, "/demographics/analyze", "pass", f"Error: {error_code}")
            else:
                data = response.json() if response.status_code != 500 else {"error": "Server error"}
                error_info = data.get('error_code', data.get('message', 'Unknown'))[:40]
                self.print_result(test_name, "/demographics/analyze", "fail",
                              f"Expected {expected_status}, got {response.status_code}: {error_info}")
        except Exception as e:
            self.print_result(test_name, "/demographics/analyze", "fail", str(e)[:50])

    async def test_face_detect(self, image_path: str, expected_status: int, test_name: str):
        """Test face detection endpoint."""
        try:
            if not Path(image_path).exists():
                self.print_result(test_name, "/face/detect", "warn", "Image not found")
                return

            with open(image_path, "rb") as f:
                files = {"file": (Path(image_path).name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/face/detect", files=files)

            if response.status_code == expected_status:
                data = response.json()
                if response.status_code == 200:
                    confidence = data.get("confidence", 0)
                    self.print_result(test_name, "/face/detect", "pass", f"Confidence: {confidence:.2f}")
                else:
                    error_code = data.get("error_code", "UNKNOWN")
                    self.print_result(test_name, "/face/detect", "pass", f"Error: {error_code}")
            else:
                self.print_result(test_name, "/face/detect", "fail",
                              f"Expected {expected_status}, got {response.status_code}")
        except Exception as e:
            self.print_result(test_name, "/face/detect", "fail", str(e)[:50])

    async def test_liveness_check(self, image_path: str, expected_status: int, test_name: str):
        """Test liveness check endpoint."""
        try:
            if not Path(image_path).exists():
                self.print_result(test_name, "/liveness/check", "warn", "Image not found")
                return

            with open(image_path, "rb") as f:
                files = {"file": (Path(image_path).name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/liveness/check", files=files)

            if response.status_code == expected_status:
                data = response.json()
                if response.status_code == 200:
                    is_live = data.get("is_live", False)
                    confidence = data.get("confidence", 0)
                    self.print_result(test_name, "/liveness/check", "pass", f"Live: {is_live}, Conf: {confidence:.2f}")
                else:
                    error_code = data.get("error_code", "UNKNOWN")
                    self.print_result(test_name, "/liveness/check", "pass", f"Error: {error_code}")
            else:
                self.print_result(test_name, "/liveness/check", "fail",
                              f"Expected {expected_status}, got {response.status_code}")
        except Exception as e:
            self.print_result(test_name, "/liveness/check", "fail", str(e)[:50])

    async def test_landmarks_detect(self, image_path: str, expected_status: int, test_name: str):
        """Test landmarks detection endpoint."""
        try:
            if not Path(image_path).exists():
                self.print_result(test_name, "/landmarks/detect", "warn", "Image not found")
                return

            with open(image_path, "rb") as f:
                files = {"file": (Path(image_path).name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/landmarks/detect", files=files)

            if response.status_code == expected_status:
                data = response.json()
                if response.status_code == 200:
                    num_landmarks = len(data.get("landmarks", {}))
                    self.print_result(test_name, "/landmarks/detect", "pass", f"Landmarks: {num_landmarks}")
                else:
                    error_code = data.get("error_code", "UNKNOWN")
                    self.print_result(test_name, "/landmarks/detect", "pass", f"Error: {error_code}")
            else:
                self.print_result(test_name, "/landmarks/detect", "fail",
                              f"Expected {expected_status}, got {response.status_code}")
        except Exception as e:
            self.print_result(test_name, "/landmarks/detect", "fail", str(e)[:50])

    async def test_enrollment(self, image_path: str, user_id: str, expected_status: int, test_name: str):
        """Test enrollment endpoint."""
        try:
            if not Path(image_path).exists():
                self.print_result(test_name, "/enroll", "warn", "Image not found")
                return

            with open(image_path, "rb") as f:
                files = {"file": (Path(image_path).name, f, "image/jpeg")}
                data = {"user_id": user_id}
                response = await self.client.post(f"{self.base_url}/enroll", files=files, data=data)

            if response.status_code == expected_status:
                response_data = response.json()
                if response.status_code == 200:
                    embedding_id = response_data.get("embedding_id", "")
                    self.print_result(test_name, "/enroll", "pass", f"Enrolled: {embedding_id[:16]}...")
                else:
                    error_code = response_data.get("error_code", "UNKNOWN")
                    self.print_result(test_name, "/enroll", "pass", f"Error: {error_code}")
            else:
                self.print_result(test_name, "/enroll", "fail",
                              f"Expected {expected_status}, got {response.status_code}")
        except Exception as e:
            self.print_result(test_name, "/enroll", "fail", str(e)[:50])

    def print_summary(self):
        """Print test summary."""
        total = self.passed + self.failed + self.warned
        print("\n" + "=" * 120)
        print(f"SUMMARY: {total} tests | PASSED: {self.passed} | FAILED: {self.failed} | WARNINGS: {self.warned}")
        print("=" * 120)


async def main():
    """Run comprehensive API tests."""
    print("=" * 120)
    print("COMPREHENSIVE API ENDPOINT TESTING")
    print("=" * 120)
    print()

    tester = APITester(API_BASE_URL)

    try:
        # 1. Health check
        print("Testing health endpoint...")
        await tester.test_health()
        print()

        # 2. Quality analysis tests
        print("Testing quality analysis endpoints...")
        await tester.test_quality_analyze("3.jpg", 200, "Quality: Good Image (3.jpg)")
        await tester.test_quality_analyze("DSC_8681.jpg", 400, "Quality: No Face (DSC_8681.jpg)")
        await tester.test_quality_analyze("indir.jpg", 200, "Quality: Small Face (indir.jpg)")
        await tester.test_quality_analyze("profileImage_1200.jpg", 200, "Quality: Large Image (profileImage_1200.jpg)")
        print()

        # 3. Demographics tests
        print("Testing demographics analysis endpoints...")
        await tester.test_demographics_analyze("profileImage_1200.jpg", 200, "Demographics: Good Image (profileImage_1200.jpg)")
        await tester.test_demographics_analyze("3.jpg", 400, "Demographics: Small Image (3.jpg)")
        await tester.test_demographics_analyze("DSC_8681.jpg", 400, "Demographics: No Face (DSC_8681.jpg)")
        await tester.test_demographics_analyze("indir.jpg", 400, "Demographics: Tiny Image (indir.jpg)")
        print()

        # 4. Face detection tests
        print("Testing face detection endpoints...")
        await tester.test_face_detect("profileImage_1200.jpg", 200, "Face Detect: Good Image")
        await tester.test_face_detect("DSC_8681.jpg", 400, "Face Detect: No Face")
        await tester.test_face_detect("3.jpg", 200, "Face Detect: Small Image")
        print()

        # 5. Liveness tests
        print("Testing liveness check endpoints...")
        await tester.test_liveness_check("profileImage_1200.jpg", 200, "Liveness: Good Image")
        await tester.test_liveness_check("DSC_8681.jpg", 400, "Liveness: No Face")
        await tester.test_liveness_check("3.jpg", 200, "Liveness: Small Image")
        print()

        # 6. Landmarks tests
        print("Testing landmarks detection endpoints...")
        await tester.test_landmarks_detect("profileImage_1200.jpg", 200, "Landmarks: Good Image")
        await tester.test_landmarks_detect("DSC_8681.jpg", 400, "Landmarks: No Face")
        await tester.test_landmarks_detect("3.jpg", 200, "Landmarks: Small Image")
        print()

        # 7. Enrollment tests
        print("Testing enrollment endpoints...")
        await tester.test_enrollment("profileImage_1200.jpg", "test-user-auto-1", 200, "Enrollment: New User")
        await tester.test_enrollment("profileImage_1200.jpg", "test-user-auto-1", 409, "Enrollment: Duplicate User")
        await tester.test_enrollment("DSC_8681.jpg", "test-user-no-face", 400, "Enrollment: No Face")
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
