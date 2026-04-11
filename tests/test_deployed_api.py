#!/usr/bin/env python3
"""
Comprehensive API Endpoint Testing with Detailed Report Generation
Tests ALL endpoints and generates a detailed markdown report.
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

import httpx

API_BASE_URL = "https://biometric-api-902542798396.europe-west1.run.app/api/v1"
TIMEOUT = 120.0
FIXTURES_DIR = Path("tests/fixtures/images")
REPORT_FILE = "DEPLOYED_API_TEST_REPORT.md"


class TestResult:
    """Test result data class."""
    def __init__(self, test_name: str, endpoint: str, status: str, details: str = "",
                 status_code: int = 0, response_time: float = 0.0):
        self.test_name = test_name
        self.endpoint = endpoint
        self.status = status  # pass, fail, warn, skip
        self.details = details
        self.status_code = status_code
        self.response_time = response_time


class ComprehensiveAPITester:
    """Comprehensive API testing suite with report generation."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=TIMEOUT)
        self.results: List[TestResult] = []
        self.start_time = datetime.now()

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    def add_result(self, result: TestResult):
        """Add test result."""
        self.results.append(result)
        status_symbol = {"pass": "✓", "fail": "✗", "warn": "⚠", "skip": "○"}[result.status]
        print(f"[{status_symbol}] {result.test_name:60} | {result.endpoint:35} | {result.details[:50]}")

    async def test_health(self):
        """Test health endpoint."""
        try:
            start = asyncio.get_event_loop().time()
            response = await self.client.get(f"{self.base_url}/health")
            elapsed = asyncio.get_event_loop().time() - start

            if response.status_code == 200:
                data = response.json()
                if "status" in data and data["status"] == "healthy":
                    self.add_result(TestResult(
                        "Health Check", "/health", "pass",
                        f"Model: {data.get('model', 'N/A')}, Version: {data.get('version', 'N/A')}",
                        200, elapsed
                    ))
                else:
                    self.add_result(TestResult(
                        "Health Check", "/health", "fail",
                        "Invalid response structure", response.status_code, elapsed
                    ))
            else:
                self.add_result(TestResult(
                    "Health Check", "/health", "fail",
                    f"Status: {response.status_code}", response.status_code, elapsed
                ))
        except Exception as e:
            self.add_result(TestResult(
                "Health Check", "/health", "fail", str(e)[:100]
            ))

    async def test_quality_analyze(self, image_path: Path, expected_status: int, test_name: str):
        """Test quality analysis endpoint."""
        try:
            if not image_path.exists():
                self.add_result(TestResult(test_name, "/quality/analyze", "skip", "Image not found"))
                return

            start = asyncio.get_event_loop().time()
            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/quality/analyze", files=files)
            elapsed = asyncio.get_event_loop().time() - start

            data = response.json()
            if response.status_code == expected_status:
                if response.status_code == 200:
                    score = data.get("overall_score", 0)
                    passed = data.get("passed", False)
                    details = f"Score: {score:.1f}%, Passed: {passed}"
                else:
                    error = data.get("error_code", "UNKNOWN")
                    details = f"Error: {error}"
                self.add_result(TestResult(test_name, "/quality/analyze", "pass", details, response.status_code, elapsed))
            else:
                self.add_result(TestResult(
                    test_name, "/quality/analyze", "fail",
                    f"Expected {expected_status}, got {response.status_code}: {data.get('error_code', 'UNKNOWN')}",
                    response.status_code, elapsed
                ))
        except Exception as e:
            self.add_result(TestResult(test_name, "/quality/analyze", "fail", str(e)[:100]))

    async def test_demographics_analyze(self, image_path: Path, expected_status: int, test_name: str):
        """Test demographics analysis endpoint."""
        try:
            if not image_path.exists():
                self.add_result(TestResult(test_name, "/demographics/analyze", "skip", "Image not found"))
                return

            start = asyncio.get_event_loop().time()
            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/demographics/analyze", files=files)
            elapsed = asyncio.get_event_loop().time() - start

            data = response.json() if response.status_code != 500 else {"error": "Server error"}
            if response.status_code == expected_status:
                if response.status_code == 200:
                    age = data.get("age", {}).get("value", "N/A")
                    gender = data.get("gender", {}).get("value", "N/A")
                    emotion = data.get("emotion", {}).get("dominant", "N/A")
                    details = f"Age: {age}, Gender: {gender}, Emotion: {emotion}"
                else:
                    error = data.get("error_code", data.get("message", "UNKNOWN"))[:50]
                    details = f"Error: {error}"
                self.add_result(TestResult(test_name, "/demographics/analyze", "pass", details, response.status_code, elapsed))
            else:
                self.add_result(TestResult(
                    test_name, "/demographics/analyze", "fail",
                    f"Expected {expected_status}, got {response.status_code}",
                    response.status_code, elapsed
                ))
        except Exception as e:
            self.add_result(TestResult(test_name, "/demographics/analyze", "fail", str(e)[:100]))

    async def test_face_detect(self, image_path: Path, expected_status: int, test_name: str):
        """Test face detection endpoint."""
        try:
            if not image_path.exists():
                self.add_result(TestResult(test_name, "/face/detect", "skip", "Image not found"))
                return

            start = asyncio.get_event_loop().time()
            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/face/detect", files=files)
            elapsed = asyncio.get_event_loop().time() - start

            data = response.json()
            if response.status_code == expected_status:
                if response.status_code == 200:
                    confidence = data.get("confidence", 0)
                    details = f"Confidence: {confidence:.2f}"
                else:
                    error = data.get("error_code", "UNKNOWN")
                    details = f"Error: {error}"
                self.add_result(TestResult(test_name, "/face/detect", "pass", details, response.status_code, elapsed))
            else:
                self.add_result(TestResult(
                    test_name, "/face/detect", "fail",
                    f"Expected {expected_status}, got {response.status_code}",
                    response.status_code, elapsed
                ))
        except Exception as e:
            self.add_result(TestResult(test_name, "/face/detect", "fail", str(e)[:100]))

    async def test_landmarks_detect(self, image_path: Path, expected_status: int, test_name: str):
        """Test landmarks detection endpoint."""
        try:
            if not image_path.exists():
                self.add_result(TestResult(test_name, "/landmarks/detect", "skip", "Image not found"))
                return

            start = asyncio.get_event_loop().time()
            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/landmarks/detect", files=files)
            elapsed = asyncio.get_event_loop().time() - start

            data = response.json()
            if response.status_code == expected_status:
                if response.status_code == 200:
                    landmarks = data.get("landmarks", [])
                    details = f"Landmarks: {len(landmarks)} points"
                else:
                    error = data.get("error_code", "UNKNOWN")
                    details = f"Error: {error}"
                self.add_result(TestResult(test_name, "/landmarks/detect", "pass", details, response.status_code, elapsed))
            else:
                self.add_result(TestResult(
                    test_name, "/landmarks/detect", "fail",
                    f"Expected {expected_status}, got {response.status_code}",
                    response.status_code, elapsed
                ))
        except Exception as e:
            self.add_result(TestResult(test_name, "/landmarks/detect", "fail", str(e)[:100]))

    async def test_liveness_check(self, image_path: Path, expected_status: int, test_name: str):
        """Test liveness check endpoint."""
        try:
            if not image_path.exists():
                self.add_result(TestResult(test_name, "/liveness/check", "skip", "Image not found"))
                return

            start = asyncio.get_event_loop().time()
            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/liveness/check", files=files)
            elapsed = asyncio.get_event_loop().time() - start

            data = response.json()
            if response.status_code == expected_status:
                if response.status_code == 200:
                    is_live = data.get("is_live", False)
                    confidence = data.get("confidence", 0)
                    details = f"Live: {is_live}, Confidence: {confidence:.2f}"
                else:
                    error = data.get("error_code", "UNKNOWN")
                    details = f"Error: {error}"
                self.add_result(TestResult(test_name, "/liveness/check", "pass", details, response.status_code, elapsed))
            else:
                self.add_result(TestResult(
                    test_name, "/liveness/check", "fail",
                    f"Expected {expected_status}, got {response.status_code}",
                    response.status_code, elapsed
                ))
        except Exception as e:
            self.add_result(TestResult(test_name, "/liveness/check", "fail", str(e)[:100]))

    async def test_enrollment(self, image_path: Path, user_id: str, expected_status: int, test_name: str):
        """Test enrollment endpoint."""
        try:
            if not image_path.exists():
                self.add_result(TestResult(test_name, "/enroll", "skip", "Image not found"))
                return

            start = asyncio.get_event_loop().time()
            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, "image/jpeg")}
                data = {"user_id": user_id, "tenant_id": "test-tenant"}
                response = await self.client.post(f"{self.base_url}/enroll", files=files, data=data)
            elapsed = asyncio.get_event_loop().time() - start

            response_data = response.json()
            if response.status_code == expected_status:
                if response.status_code == 200:
                    details = f"Enrolled: {user_id}"
                elif response.status_code == 409:
                    details = "Duplicate (expected)"
                else:
                    error = response_data.get("error_code", "UNKNOWN")
                    details = f"Error: {error}"
                self.add_result(TestResult(test_name, "/enroll", "pass", details, response.status_code, elapsed))
            else:
                self.add_result(TestResult(
                    test_name, "/enroll", "fail",
                    f"Expected {expected_status}, got {response.status_code}",
                    response.status_code, elapsed
                ))
        except Exception as e:
            self.add_result(TestResult(test_name, "/enroll", "fail", str(e)[:100]))

    async def test_verification(self, image_path: Path, user_id: str, expected_status: int, test_name: str):
        """Test verification endpoint."""
        try:
            if not image_path.exists():
                self.add_result(TestResult(test_name, "/verify", "skip", "Image not found"))
                return

            start = asyncio.get_event_loop().time()
            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, "image/jpeg")}
                data = {"user_id": user_id, "tenant_id": "test-tenant"}
                response = await self.client.post(f"{self.base_url}/verify", files=files, data=data)
            elapsed = asyncio.get_event_loop().time() - start

            response_data = response.json()
            if response.status_code == expected_status:
                if response.status_code == 200:
                    match = response_data.get("match", False)
                    similarity = response_data.get("similarity", 0)
                    details = f"Match: {match}, Similarity: {similarity:.2f}"
                else:
                    error = response_data.get("error_code", "UNKNOWN")
                    details = f"Error: {error}"
                self.add_result(TestResult(test_name, "/verify", "pass", details, response.status_code, elapsed))
            else:
                self.add_result(TestResult(
                    test_name, "/verify", "fail",
                    f"Expected {expected_status}, got {response.status_code}",
                    response.status_code, elapsed
                ))
        except Exception as e:
            self.add_result(TestResult(test_name, "/verify", "fail", str(e)[:100]))

    async def test_search(self, image_path: Path, expected_status: int, test_name: str):
        """Test search endpoint."""
        try:
            if not image_path.exists():
                self.add_result(TestResult(test_name, "/search", "skip", "Image not found"))
                return

            start = asyncio.get_event_loop().time()
            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, "image/jpeg")}
                data = {"tenant_id": "test-tenant", "max_results": "5"}
                response = await self.client.post(f"{self.base_url}/search", files=files, data=data)
            elapsed = asyncio.get_event_loop().time() - start

            response_data = response.json()
            if response.status_code == expected_status:
                if response.status_code == 200:
                    matches = response_data.get("matches", [])
                    details = f"Found {len(matches)} matches"
                else:
                    error = response_data.get("error_code", "UNKNOWN")
                    details = f"Error: {error}"
                self.add_result(TestResult(test_name, "/search", "pass", details, response.status_code, elapsed))
            else:
                self.add_result(TestResult(
                    test_name, "/search", "fail",
                    f"Expected {expected_status}, got {response.status_code}",
                    response.status_code, elapsed
                ))
        except Exception as e:
            self.add_result(TestResult(test_name, "/search", "fail", str(e)[:100]))

    async def test_compare(self, image1_path: Path, image2_path: Path, expected_status: int, test_name: str):
        """Test compare endpoint."""
        try:
            if not image1_path.exists() or not image2_path.exists():
                self.add_result(TestResult(test_name, "/compare", "skip", "Image not found"))
                return

            start = asyncio.get_event_loop().time()
            with open(image1_path, "rb") as f1, open(image2_path, "rb") as f2:
                files = [
                    ("file1", (image1_path.name, f1, "image/jpeg")),
                    ("file2", (image2_path.name, f2, "image/jpeg"))
                ]
                response = await self.client.post(f"{self.base_url}/compare", files=files)
            elapsed = asyncio.get_event_loop().time() - start

            response_data = response.json()
            if response.status_code == expected_status:
                if response.status_code == 200:
                    is_match = response_data.get("is_match", False)
                    similarity = response_data.get("similarity", 0)
                    details = f"Match: {is_match}, Similarity: {similarity:.2f}"
                else:
                    error = response_data.get("error_code", "UNKNOWN")
                    details = f"Error: {error}"
                self.add_result(TestResult(test_name, "/compare", "pass", details, response.status_code, elapsed))
            else:
                self.add_result(TestResult(
                    test_name, "/compare", "fail",
                    f"Expected {expected_status}, got {response.status_code}",
                    response.status_code, elapsed
                ))
        except Exception as e:
            self.add_result(TestResult(test_name, "/compare", "fail", str(e)[:100]))

    async def test_multi_face_detect(self, image_path: Path, expected_status: int, test_name: str):
        """Test multi-face detection endpoint."""
        try:
            if not image_path.exists():
                self.add_result(TestResult(test_name, "/faces/detect-all", "skip", "Image not found"))
                return

            start = asyncio.get_event_loop().time()
            with open(image_path, "rb") as f:
                files = {"file": (image_path.name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/faces/detect-all", files=files)
            elapsed = asyncio.get_event_loop().time() - start

            response_data = response.json()
            if response.status_code == expected_status:
                if response.status_code == 200:
                    faces = response_data.get("faces", [])
                    details = f"Detected {len(faces)} faces"
                else:
                    error = response_data.get("error_code", "UNKNOWN")
                    details = f"Error: {error}"
                self.add_result(TestResult(test_name, "/faces/detect-all", "pass", details, response.status_code, elapsed))
            else:
                self.add_result(TestResult(
                    test_name, "/faces/detect-all", "fail",
                    f"Expected {expected_status}, got {response.status_code}",
                    response.status_code, elapsed
                ))
        except Exception as e:
            self.add_result(TestResult(test_name, "/faces/detect-all", "fail", str(e)[:100]))

    def generate_report(self):
        """Generate comprehensive markdown report."""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()

        # Count results
        passed = sum(1 for r in self.results if r.status == "pass")
        failed = sum(1 for r in self.results if r.status == "fail")
        warned = sum(1 for r in self.results if r.status == "warn")
        skipped = sum(1 for r in self.results if r.status == "skip")
        total = len(self.results)

        # Group by endpoint
        by_endpoint: Dict[str, List[TestResult]] = {}
        for result in self.results:
            if result.endpoint not in by_endpoint:
                by_endpoint[result.endpoint] = []
            by_endpoint[result.endpoint].append(result)

        # Generate report
        report = f"""# Comprehensive API Test Report

**Generated:** {end_time.strftime("%Y-%m-%d %H:%M:%S")}
**Duration:** {duration:.2f} seconds
**Base URL:** {self.base_url}

---

## Executive Summary

| Metric | Count | Percentage |
|--------|-------|------------|
| **Total Tests** | {total} | 100% |
| **✓ Passed** | {passed} | {(passed/total*100) if total > 0 else 0:.1f}% |
| **✗ Failed** | {failed} | {(failed/total*100) if total > 0 else 0:.1f}% |
| **⚠ Warnings** | {warned} | {(warned/total*100) if total > 0 else 0:.1f}% |
| **○ Skipped** | {skipped} | {(skipped/total*100) if total > 0 else 0:.1f}% |

### Overall Status
"""
        if failed == 0 and warned == 0:
            report += "**✓ ALL TESTS PASSED!** The API is functioning correctly.\n"
        elif failed == 0:
            report += f"**✓ All functional tests passed** ({warned} warnings about missing features/images)\n"
        else:
            report += f"**✗ {failed} TESTS FAILED** - Immediate attention required!\n"

        report += "\n---\n\n## Test Results by Endpoint\n\n"

        for endpoint in sorted(by_endpoint.keys()):
            results = by_endpoint[endpoint]
            endpoint_passed = sum(1 for r in results if r.status == "pass")
            endpoint_failed = sum(1 for r in results if r.status == "fail")
            endpoint_total = len(results)

            status_emoji = "✓" if endpoint_failed == 0 else "✗"
            report += f"### {status_emoji} `{endpoint}` ({endpoint_passed}/{endpoint_total} passed)\n\n"
            report += "| Test Name | Status | Details | Status Code | Response Time |\n"
            report += "|-----------|--------|---------|-------------|---------------|\n"

            for result in results:
                status_emoji = {"pass": "✓", "fail": "✗", "warn": "⚠", "skip": "○"}[result.status]
                report += f"| {result.test_name} | {status_emoji} {result.status.upper()} | {result.details} | {result.status_code} | {result.response_time:.3f}s |\n"

            report += "\n"

        report += "---\n\n## Failed Tests Detail\n\n"
        failed_tests = [r for r in self.results if r.status == "fail"]
        if failed_tests:
            for result in failed_tests:
                report += f"### ✗ {result.test_name}\n"
                report += f"- **Endpoint:** `{result.endpoint}`\n"
                report += f"- **Status Code:** {result.status_code}\n"
                report += f"- **Details:** {result.details}\n\n"
        else:
            report += "**No failed tests!** 🎉\n\n"

        report += "---\n\n## Performance Metrics\n\n"
        report += "| Endpoint | Avg Response Time | Min | Max |\n"
        report += "|----------|------------------|-----|-----|\n"

        for endpoint in sorted(by_endpoint.keys()):
            results = [r for r in by_endpoint[endpoint] if r.response_time > 0]
            if results:
                times = [r.response_time for r in results]
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
                report += f"| `{endpoint}` | {avg_time:.3f}s | {min_time:.3f}s | {max_time:.3f}s |\n"

        report += "\n---\n\n## Recommendations\n\n"

        if failed > 0:
            report += "### Critical Issues\n"
            report += f"- **{failed} endpoints are failing** - Review the 'Failed Tests Detail' section above\n"
            report += "- Fix these issues before deploying to production\n\n"

        if warned > 0:
            report += "### Warnings\n"
            report += f"- **{warned} tests generated warnings** - Review missing features or test data\n\n"

        slow_endpoints = []
        for endpoint in by_endpoint.keys():
            results = [r for r in by_endpoint[endpoint] if r.response_time > 0]
            if results:
                avg_time = sum(r.response_time for r in results) / len(results)
                if avg_time > 5.0:
                    slow_endpoints.append((endpoint, avg_time))

        if slow_endpoints:
            report += "### Performance Concerns\n"
            for endpoint, avg_time in slow_endpoints:
                report += f"- `{endpoint}` has average response time of {avg_time:.2f}s (>5s threshold)\n"
            report += "\n"

        report += "---\n\n*Report generated by Comprehensive API Tester*\n"

        return report

    def print_summary(self):
        """Print test summary to console."""
        passed = sum(1 for r in self.results if r.status == "pass")
        failed = sum(1 for r in self.results if r.status == "fail")
        warned = sum(1 for r in self.results if r.status == "warn")
        skipped = sum(1 for r in self.results if r.status == "skip")
        total = len(self.results)

        print("\n" + "=" * 140)
        print(f"SUMMARY: {total} tests | ✓ PASSED: {passed} | ✗ FAILED: {failed} | ⚠ WARNINGS: {warned} | ○ SKIPPED: {skipped}")

        if failed == 0 and warned == 0:
            print("✓ ALL TESTS PASSED!")
        elif failed == 0:
            print(f"✓ All functional tests passed ({warned} warnings)")
        else:
            print(f"✗ {failed} TESTS FAILED - NEEDS ATTENTION")

        print("=" * 140)


async def main():
    """Run comprehensive API tests."""
    print("=" * 140)
    print("COMPREHENSIVE API ENDPOINT TESTING WITH DETAILED REPORT GENERATION")
    print("=" * 140)
    print()

    tester = ComprehensiveAPITester(API_BASE_URL)

    try:
        # Get test image directories
        afuat_dir = FIXTURES_DIR / "afuat"
        aga_dir = FIXTURES_DIR / "aga"
        ahab_dir = FIXTURES_DIR / "ahab"

        # 1. Health check
        print("1. HEALTH CHECK")
        print("-" * 140)
        await tester.test_health()
        print()

        # 2. Quality analysis
        print("2. QUALITY ANALYSIS TESTS")
        print("-" * 140)
        await tester.test_quality_analyze(afuat_dir / "profileImage_1200.jpg", 200, "Quality: Large good image")
        await tester.test_quality_analyze(afuat_dir / "3.jpg", 200, "Quality: Small image")
        await tester.test_quality_analyze(afuat_dir / "DSC_8681.jpg", 400, "Quality: No face")
        await tester.test_quality_analyze(ahab_dir / "foto.jpg", 200, "Quality: Different person")
        print()

        # 3. Demographics analysis
        print("3. DEMOGRAPHICS ANALYSIS TESTS")
        print("-" * 140)
        await tester.test_demographics_analyze(afuat_dir / "profileImage_1200.jpg", 200, "Demographics: Large image")
        await tester.test_demographics_analyze(afuat_dir / "3.jpg", 400, "Demographics: Small image <224px")
        await tester.test_demographics_analyze(afuat_dir / "DSC_8681.jpg", 400, "Demographics: No face")
        await tester.test_demographics_analyze(ahab_dir / "foto.jpg", 200, "Demographics: Different person")
        print()

        # 4. Face detection
        print("4. FACE DETECTION TESTS")
        print("-" * 140)
        await tester.test_face_detect(afuat_dir / "profileImage_1200.jpg", 200, "Face Detect: Good image")
        await tester.test_face_detect(afuat_dir / "DSC_8681.jpg", 400, "Face Detect: No face")
        await tester.test_face_detect(aga_dir / "indir.jpg", 200, "Face Detect: Another person")
        print()

        # 5. Multi-face detection
        print("5. MULTI-FACE DETECTION TESTS")
        print("-" * 140)
        await tester.test_multi_face_detect(afuat_dir / "profileImage_1200.jpg", 200, "Multi-Face: Single face")
        await tester.test_multi_face_detect(afuat_dir / "DSC_8681.jpg", 400, "Multi-Face: No face")
        print()

        # 6. Landmarks detection
        print("6. LANDMARKS DETECTION TESTS")
        print("-" * 140)
        await tester.test_landmarks_detect(afuat_dir / "profileImage_1200.jpg", 200, "Landmarks: Good image")
        await tester.test_landmarks_detect(afuat_dir / "DSC_8681.jpg", 400, "Landmarks: No face")
        await tester.test_landmarks_detect(ahab_dir / "foto.jpg", 200, "Landmarks: Different person")
        print()

        # 7. Liveness check
        print("7. LIVENESS CHECK TESTS")
        print("-" * 140)
        await tester.test_liveness_check(afuat_dir / "profileImage_1200.jpg", 200, "Liveness: Good image")
        await tester.test_liveness_check(afuat_dir / "DSC_8681.jpg", 400, "Liveness: No face")
        await tester.test_liveness_check(ahab_dir / "foto.jpg", 200, "Liveness: Different person")
        print()

        # 8. Enrollment
        print("8. ENROLLMENT TESTS")
        print("-" * 140)
        await tester.test_enrollment(afuat_dir / "profileImage_1200.jpg", "afuat-test", 200, "Enroll: User afuat")
        await tester.test_enrollment(afuat_dir / "profileImage_1200.jpg", "afuat-test", 409, "Enroll: Duplicate afuat")
        await tester.test_enrollment(aga_dir / "spring21_veda1.png", "aga-test", 200, "Enroll: User aga")
        await tester.test_enrollment(ahab_dir / "foto.jpg", "ahab-test", 200, "Enroll: User ahab")
        await tester.test_enrollment(afuat_dir / "DSC_8681.jpg", "no-face", 400, "Enroll: No face")
        print()

        # 9. Verification
        print("9. VERIFICATION TESTS")
        print("-" * 140)
        await tester.test_verification(afuat_dir / "3.jpg", "afuat-test", 200, "Verify: Same person (afuat)")
        await tester.test_verification(aga_dir / "indir.jpg", "aga-test", 200, "Verify: Same person (aga)")
        await tester.test_verification(afuat_dir / "3.jpg", "aga-test", 200, "Verify: Wrong person")
        await tester.test_verification(afuat_dir / "DSC_8681.jpg", "afuat-test", 400, "Verify: No face")
        print()

        # 10. Search
        print("10. SEARCH TESTS")
        print("-" * 140)
        await tester.test_search(afuat_dir / "3.jpg", 200, "Search: Find afuat")
        await tester.test_search(aga_dir / "indir.jpg", 200, "Search: Find aga")
        await tester.test_search(afuat_dir / "DSC_8681.jpg", 400, "Search: No face")
        print()

        # 11. Compare
        print("11. FACE COMPARISON TESTS")
        print("-" * 140)
        await tester.test_compare(
            afuat_dir / "profileImage_1200.jpg",
            afuat_dir / "3.jpg",
            200,
            "Compare: Same person (afuat vs afuat)"
        )
        await tester.test_compare(
            afuat_dir / "profileImage_1200.jpg",
            aga_dir / "spring21_veda1.png",
            200,
            "Compare: Different persons (afuat vs aga)"
        )
        await tester.test_compare(
            ahab_dir / "foto.jpg",
            ahab_dir / "1679744618228.jpg",
            200,
            "Compare: Same person (ahab vs ahab)"
        )
        print()

        # Print summary
        tester.print_summary()

        # Generate and save report
        print(f"\nGenerating detailed report to {REPORT_FILE}...")
        report = tester.generate_report()
        with open(REPORT_FILE, "w") as f:
            f.write(report)
        print(f"✓ Report saved to {REPORT_FILE}")

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
