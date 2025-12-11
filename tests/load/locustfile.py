"""Load testing for Biometric Processor API using Locust.

Run with:
    locust -f tests/load/locustfile.py --host=http://localhost:8001

Or headless:
    locust -f tests/load/locustfile.py --host=http://localhost:8001 \
           --users 100 --spawn-rate 10 --run-time 60s --headless
"""

import base64
import io
import random
import uuid
from typing import Optional

from locust import HttpUser, between, task
from PIL import Image


def generate_test_image(size: tuple = (200, 200)) -> bytes:
    """Generate a simple test image.

    Args:
        size: Image dimensions

    Returns:
        JPEG image bytes
    """
    # Create a simple colored image
    color = (
        random.randint(50, 200),
        random.randint(50, 200),
        random.randint(50, 200),
    )
    img = Image.new("RGB", size, color=color)

    # Add some variation
    for x in range(0, size[0], 20):
        for y in range(0, size[1], 20):
            variation = (
                random.randint(-30, 30),
                random.randint(-30, 30),
                random.randint(-30, 30),
            )
            new_color = tuple(
                max(0, min(255, c + v)) for c, v in zip(color, variation)
            )
            for dx in range(20):
                for dy in range(20):
                    if x + dx < size[0] and y + dy < size[1]:
                        img.putpixel((x + dx, y + dy), new_color)

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


class BiometricAPIUser(HttpUser):
    """Simulated user for Biometric Processor API load testing."""

    # Wait between 1-3 seconds between tasks
    wait_time = between(1, 3)

    def on_start(self):
        """Initialize user session."""
        self.user_id = str(uuid.uuid4())
        self.tenant_id = f"tenant_{random.randint(1, 10)}"
        self.enrolled = False

    @task(10)
    def health_check(self):
        """Health check endpoint - high frequency."""
        with self.client.get(
            "/api/v1/health",
            name="/api/v1/health",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")

    @task(5)
    def analyze_quality(self):
        """Quality analysis endpoint."""
        image_data = generate_test_image()

        with self.client.post(
            "/api/v1/quality/analyze",
            files={"image": ("test.jpg", image_data, "image/jpeg")},
            name="/api/v1/quality/analyze",
            catch_response=True,
        ) as response:
            if response.status_code in [200, 400]:  # 400 = no face detected
                response.success()
            else:
                response.failure(f"Quality analysis failed: {response.status_code}")

    @task(3)
    def detect_faces(self):
        """Multi-face detection endpoint."""
        image_data = generate_test_image()

        with self.client.post(
            "/api/v1/faces/detect-all",
            files={"image": ("test.jpg", image_data, "image/jpeg")},
            name="/api/v1/faces/detect-all",
            catch_response=True,
        ) as response:
            if response.status_code in [200, 400]:
                response.success()
            else:
                response.failure(f"Face detection failed: {response.status_code}")

    @task(2)
    def enroll_face(self):
        """Face enrollment endpoint."""
        image_data = generate_test_image()
        user_id = f"user_{uuid.uuid4().hex[:8]}"

        with self.client.post(
            "/api/v1/enroll",
            files={"image": ("test.jpg", image_data, "image/jpeg")},
            data={"user_id": user_id},
            name="/api/v1/enroll",
            catch_response=True,
        ) as response:
            if response.status_code in [200, 201, 400, 409]:
                response.success()
                if response.status_code in [200, 201]:
                    self.user_id = user_id
                    self.enrolled = True
            else:
                response.failure(f"Enrollment failed: {response.status_code}")

    @task(3)
    def verify_face(self):
        """Face verification endpoint."""
        if not self.enrolled:
            return

        image_data = generate_test_image()

        with self.client.post(
            "/api/v1/verify",
            files={"image": ("test.jpg", image_data, "image/jpeg")},
            data={"user_id": self.user_id},
            name="/api/v1/verify",
            catch_response=True,
        ) as response:
            if response.status_code in [200, 400, 401, 404]:
                response.success()
            else:
                response.failure(f"Verification failed: {response.status_code}")

    @task(2)
    def check_liveness(self):
        """Liveness detection endpoint."""
        image_data = generate_test_image()

        with self.client.post(
            "/api/v1/liveness/check",
            files={"image": ("test.jpg", image_data, "image/jpeg")},
            name="/api/v1/liveness/check",
            catch_response=True,
        ) as response:
            if response.status_code in [200, 400]:
                response.success()
            else:
                response.failure(f"Liveness check failed: {response.status_code}")

    @task(1)
    def compare_faces(self):
        """Face comparison endpoint."""
        image1 = generate_test_image()
        image2 = generate_test_image()

        with self.client.post(
            "/api/v1/compare",
            files=[
                ("image1", ("test1.jpg", image1, "image/jpeg")),
                ("image2", ("test2.jpg", image2, "image/jpeg")),
            ],
            name="/api/v1/compare",
            catch_response=True,
        ) as response:
            if response.status_code in [200, 400]:
                response.success()
            else:
                response.failure(f"Comparison failed: {response.status_code}")

    @task(1)
    def get_metrics(self):
        """Prometheus metrics endpoint."""
        with self.client.get(
            "/metrics",
            name="/metrics",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Metrics failed: {response.status_code}")


class HighLoadUser(HttpUser):
    """High-load user focusing on lightweight endpoints."""

    wait_time = between(0.1, 0.5)

    @task(10)
    def health_check(self):
        """Rapid health checks."""
        self.client.get("/api/v1/health", name="/api/v1/health [high-load]")

    @task(5)
    def get_metrics(self):
        """Rapid metrics checks."""
        self.client.get("/metrics", name="/metrics [high-load]")


class StressTestUser(HttpUser):
    """Stress test user for finding breaking points."""

    wait_time = between(0, 0.1)

    @task
    def stress_quality(self):
        """Stress test quality endpoint."""
        image_data = generate_test_image((100, 100))  # Smaller image

        self.client.post(
            "/api/v1/quality/analyze",
            files={"image": ("test.jpg", image_data, "image/jpeg")},
            name="/api/v1/quality/analyze [stress]",
        )
