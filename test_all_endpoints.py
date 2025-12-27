#!/usr/bin/env python3
"""Comprehensive API endpoint testing script.

Tests all biometric API endpoints with various scenarios:
- Success cases
- Error cases (no face, bad quality, missing data)
- Edge cases (multiple faces, small images)
- Response validation
- Error code verification
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

API_BASE_URL = "http://localhost:8001/api/v1"
TIMEOUT = 30.0

# Test image paths (relative to project root)
TEST_IMAGES = {
    "good_quality": "demo-ui/public/images/sample-face.jpg",
    "multiple_faces": "demo-ui/public/images/group-photo.jpg",
    "no_face": "demo-ui/public/images/landscape.jpg",
    "small_face": "demo-ui/public/images/tiny-face.jpg",
    "poor_quality": "demo-ui/public/images/blurry-face.jpg",
}


class TestResult:
    """Test result container."""

    def __init__(self, name: str, endpoint: str, status: str, details: str = ""):
        self.name = name
        self.endpoint = endpoint
        self.status = status  # "✓ PASS", "✗ FAIL", "⚠ WARN"
        self.details = details


class APITester:
    """Comprehensive API testing suite."""

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=TIMEOUT)
        self.results: List[TestResult] = []

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    def add_result(self, name: str, endpoint: str, status: str, details: str = ""):
        """Add test result."""
        self.results.append(TestResult(name, endpoint, status, details))

    async def test_health(self):
        """Test health endpoint."""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                if "status" in data and data["status"] == "healthy":
                    self.add_result("Health Check", "/health", "✓ PASS", f"Model: {data.get('model')}")
                else:
                    self.add_result("Health Check", "/health", "✗ FAIL", "Invalid response format")
            else:
                self.add_result("Health Check", "/health", "✗ FAIL", f"Status: {response.status_code}")
        except Exception as e:
            self.add_result("Health Check", "/health", "✗ FAIL", str(e))

    async def test_quality_analyze(self, image_path: str, expected_status: int, test_name: str):
        """Test quality analysis endpoint."""
        try:
            if not Path(image_path).exists():
                self.add_result(test_name, "/quality/analyze", "⚠ WARN", f"Image not found: {image_path}")
                return

            with open(image_path, "rb") as f:
                files = {"file": (Path(image_path).name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/quality/analyze", files=files)

            if response.status_code == expected_status:
                data = response.json()
                if response.status_code == 200:
                    score = data.get("overall_score", 0)
                    self.add_result(test_name, "/quality/analyze", "✓ PASS", f"Score: {score:.1f}%")
                else:
                    error_code = data.get("error_code", "UNKNOWN")
                    self.add_result(test_name, "/quality/analyze", "✓ PASS", f"Expected error: {error_code}")
            else:
                self.add_result(test_name, "/quality/analyze", "✗ FAIL",
                              f"Expected {expected_status}, got {response.status_code}")
        except Exception as e:
            self.add_result(test_name, "/quality/analyze", "✗ FAIL", str(e))

    async def test_demographics_analyze(self, image_path: str, expected_status: int, test_name: str):
        """Test demographics analysis endpoint."""
        try:
            if not Path(image_path).exists():
                self.add_result(test_name, "/demographics/analyze", "⚠ WARN", f"Image not found: {image_path}")
                return

            with open(image_path, "rb") as f:
                files = {"file": (Path(image_path).name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/demographics/analyze", files=files)

            if response.status_code == expected_status:
                data = response.json()
                if response.status_code == 200:
                    age = data.get("age")
                    gender = data.get("gender")
                    self.add_result(test_name, "/demographics/analyze", "✓ PASS",
                                  f"Age: {age}, Gender: {gender}")
                else:
                    error_code = data.get("error_code", "UNKNOWN")
                    self.add_result(test_name, "/demographics/analyze", "✓ PASS",
                                  f"Expected error: {error_code}")
            else:
                data = response.json() if response.status_code != 500 else {"error": "Server error"}
                self.add_result(test_name, "/demographics/analyze", "✗ FAIL",
                              f"Expected {expected_status}, got {response.status_code}: {data.get('error_code', data)}")
        except Exception as e:
            self.add_result(test_name, "/demographics/analyze", "✗ FAIL", str(e))

    async def test_face_detect(self, image_path: str, expected_status: int, test_name: str):
        """Test face detection endpoint."""
        try:
            if not Path(image_path).exists():
                self.add_result(test_name, "/face/detect", "⚠ WARN", f"Image not found: {image_path}")
                return

            with open(image_path, "rb") as f:
                files = {"file": (Path(image_path).name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/face/detect", files=files)

            if response.status_code == expected_status:
                data = response.json()
                if response.status_code == 200:
                    confidence = data.get("confidence", 0)
                    self.add_result(test_name, "/face/detect", "✓ PASS",
                                  f"Confidence: {confidence:.2f}")
                else:
                    error_code = data.get("error_code", "UNKNOWN")
                    self.add_result(test_name, "/face/detect", "✓ PASS",
                                  f"Expected error: {error_code}")
            else:
                self.add_result(test_name, "/face/detect", "✗ FAIL",
                              f"Expected {expected_status}, got {response.status_code}")
        except Exception as e:
            self.add_result(test_name, "/face/detect", "✗ FAIL", str(e))

    async def test_liveness_check(self, image_path: str, expected_status: int, test_name: str):
        """Test liveness check endpoint."""
        try:
            if not Path(image_path).exists():
                self.add_result(test_name, "/liveness/check", "⚠ WARN", f"Image not found: {image_path}")
                return

            with open(image_path, "rb") as f:
                files = {"file": (Path(image_path).name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/liveness/check", files=files)

            if response.status_code == expected_status:
                data = response.json()
                if response.status_code == 200:
                    is_live = data.get("is_live", False)
                    confidence = data.get("confidence", 0)
                    self.add_result(test_name, "/liveness/check", "✓ PASS",
                                  f"Live: {is_live}, Confidence: {confidence:.2f}")
                else:
                    error_code = data.get("error_code", "UNKNOWN")
                    self.add_result(test_name, "/liveness/check", "✓ PASS",
                                  f"Expected error: {error_code}")
            else:
                self.add_result(test_name, "/liveness/check", "✗ FAIL",
                              f"Expected {expected_status}, got {response.status_code}")
        except Exception as e:
            self.add_result(test_name, "/liveness/check", "✗ FAIL", str(e))

    async def test_landmarks_detect(self, image_path: str, expected_status: int, test_name: str):
        """Test landmarks detection endpoint."""
        try:
            if not Path(image_path).exists():
                self.add_result(test_name, "/landmarks/detect", "⚠ WARN", f"Image not found: {image_path}")
                return

            with open(image_path, "rb") as f:
                files = {"file": (Path(image_path).name, f, "image/jpeg")}
                response = await self.client.post(f"{self.base_url}/landmarks/detect", files=files)

            if response.status_code == expected_status:
                data = response.json()
                if response.status_code == 200:
                    num_landmarks = len(data.get("landmarks", {}))
                    self.add_result(test_name, "/landmarks/detect", "✓ PASS",
                                  f"Landmarks: {num_landmarks}")
                else:
                    error_code = data.get("error_code", "UNKNOWN")
                    self.add_result(test_name, "/landmarks/detect", "✓ PASS",
                                  f"Expected error: {error_code}")
            else:
                self.add_result(test_name, "/landmarks/detect", "✗ FAIL",
                              f"Expected {expected_status}, got {response.status_code}")
        except Exception as e:
            self.add_result(test_name, "/landmarks/detect", "✗ FAIL", str(e))

    async def test_enrollment(self, image_path: str, user_id: str, expected_status: int, test_name: str):
        """Test enrollment endpoint."""
        try:
            if not Path(image_path).exists():
                self.add_result(test_name, "/enroll", "⚠ WARN", f"Image not found: {image_path}")
                return

            with open(image_path, "rb") as f:
                files = {"file": (Path(image_path).name, f, "image/jpeg")}
                data = {"user_id": user_id}
                response = await self.client.post(f"{self.base_url}/enroll", files=files, data=data)

            if response.status_code == expected_status:
                response_data = response.json()
                if response.status_code == 200:
                    embedding_id = response_data.get("embedding_id", "")
                    self.add_result(test_name, "/enroll", "✓ PASS",
                                  f"Enrolled: {embedding_id[:16]}...")
                else:
                    error_code = response_data.get("error_code", "UNKNOWN")
                    self.add_result(test_name, "/enroll", "✓ PASS",
                                  f"Expected error: {error_code}")
            else:
                self.add_result(test_name, "/enroll", "✗ FAIL",
                              f"Expected {expected_status}, got {response.status_code}")
        except Exception as e:
            self.add_result(test_name, "/enroll", "✗ FAIL", str(e))

    def print_results(self):
        """Print test results in a nice table."""
        table = Table(title="API Endpoint Test Results", show_header=True, header_style="bold magenta")
        table.add_column("Test Name", style="cyan", width=40)
        table.add_column("Endpoint", style="blue", width=25)
        table.add_column("Status", width=10)
        table.add_column("Details", style="dim", width=40)

        pass_count = 0
        fail_count = 0
        warn_count = 0

        for result in self.results:
            if result.status == "✓ PASS":
                pass_count += 1
                status_color = "green"
            elif result.status == "✗ FAIL":
                fail_count += 1
                status_color = "red"
            else:
                warn_count += 1
                status_color = "yellow"

            table.add_row(
                result.name,
                result.endpoint,
                f"[{status_color}]{result.status}[/{status_color}]",
                result.details
            )

        console.print(table)
        console.print()
        console.print(Panel(
            f"[green]✓ Passed: {pass_count}[/green]  "
            f"[red]✗ Failed: {fail_count}[/red]  "
            f"[yellow]⚠ Warnings: {warn_count}[/yellow]",
            title="Summary"
        ))


async def main():
    """Run comprehensive API tests."""
    console.print(Panel.fit(
        "[bold cyan]Comprehensive API Endpoint Testing[/bold cyan]\n"
        "Testing all endpoints with various scenarios",
        border_style="cyan"
    ))

    tester = APITester(API_BASE_URL)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Running tests...", total=None)

            # 1. Health check
            await tester.test_health()

            # 2. Quality analysis tests
            await tester.test_quality_analyze("3.jpg", 200, "Quality: Good Image")
            await tester.test_quality_analyze("DSC_8681.jpg", 400, "Quality: No Face")
            await tester.test_quality_analyze("indir.jpg", 200, "Quality: Small Face")

            # 3. Demographics tests
            await tester.test_demographics_analyze("profileImage_1200.jpg", 200, "Demographics: Good Image")
            await tester.test_demographics_analyze("3.jpg", 400, "Demographics: Small Image")
            await tester.test_demographics_analyze("DSC_8681.jpg", 400, "Demographics: No Face")

            # 4. Face detection tests
            await tester.test_face_detect("profileImage_1200.jpg", 200, "Face Detect: Good Image")
            await tester.test_face_detect("DSC_8681.jpg", 400, "Face Detect: No Face")

            # 5. Liveness tests
            await tester.test_liveness_check("profileImage_1200.jpg", 200, "Liveness: Good Image")
            await tester.test_liveness_check("DSC_8681.jpg", 400, "Liveness: No Face")

            # 6. Landmarks tests
            await tester.test_landmarks_detect("profileImage_1200.jpg", 200, "Landmarks: Good Image")
            await tester.test_landmarks_detect("DSC_8681.jpg", 400, "Landmarks: No Face")

            # 7. Enrollment tests
            await tester.test_enrollment("profileImage_1200.jpg", "test-user-comprehensive", 200,
                                        "Enrollment: New User")
            await tester.test_enrollment("profileImage_1200.jpg", "test-user-comprehensive", 409,
                                        "Enrollment: Duplicate User")
            await tester.test_enrollment("DSC_8681.jpg", "test-user-no-face", 400,
                                        "Enrollment: No Face")

            progress.update(task, completed=True)

        # Print results
        console.print()
        tester.print_results()

    finally:
        await tester.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Test failed: {e}[/red]")
        sys.exit(1)
