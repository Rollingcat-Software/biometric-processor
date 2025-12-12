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


class ProctorUser(HttpUser):
    """Simulated user for proctoring API load testing."""

    wait_time = between(0.5, 2)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._session_id: Optional[str] = None
        self._tenant_id = f"load-test-tenant-{uuid.uuid4().hex[:8]}"

    def on_start(self):
        """Create a proctoring session on start."""
        self._create_session()

    def on_stop(self):
        """End the session on stop."""
        if self._session_id:
            self._end_session()

    def _create_session(self):
        """Create a new proctoring session."""
        with self.client.post(
            "/api/v1/proctor/sessions",
            json={
                "exam_id": f"exam-{uuid.uuid4().hex[:8]}",
                "user_id": f"user-{uuid.uuid4().hex[:8]}",
                "tenant_id": self._tenant_id,
                "config": {
                    "gaze_threshold_seconds": 3.0,
                    "risk_threshold": 0.7,
                },
            },
            name="/api/v1/proctor/sessions [create]",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    self._session_id = data.get("session_id")
                    if self._session_id:
                        self._start_session()
                except Exception:
                    pass
            elif response.status_code >= 400:
                response.failure(f"Session creation failed: {response.status_code}")

    def _start_session(self):
        """Start the proctoring session."""
        if not self._session_id:
            return

        image_data = generate_test_image()
        image_b64 = base64.b64encode(image_data).decode("utf-8")

        self.client.post(
            f"/api/v1/proctor/sessions/{self._session_id}/start",
            json={"baseline_image": image_b64},
            name="/api/v1/proctor/sessions/{id}/start",
        )

    def _end_session(self):
        """End the proctoring session."""
        if not self._session_id:
            return

        self.client.post(
            f"/api/v1/proctor/sessions/{self._session_id}/end",
            name="/api/v1/proctor/sessions/{id}/end",
        )

    @task(10)
    def submit_frame(self):
        """Submit a frame for analysis (main proctoring workload)."""
        if not self._session_id:
            self._create_session()
            return

        image_data = generate_test_image()
        image_b64 = base64.b64encode(image_data).decode("utf-8")

        with self.client.post(
            f"/api/v1/proctor/sessions/{self._session_id}/frames",
            json={
                "image": image_b64,
                "timestamp": uuid.uuid4().hex,
            },
            name="/api/v1/proctor/sessions/{id}/frames",
            catch_response=True,
        ) as response:
            if response.status_code == 404:
                self._create_session()
            elif response.status_code >= 500:
                response.failure(f"Server error: {response.status_code}")

    @task(3)
    def get_session_status(self):
        """Get current session status."""
        if not self._session_id:
            return

        self.client.get(
            f"/api/v1/proctor/sessions/{self._session_id}",
            name="/api/v1/proctor/sessions/{id}",
        )

    @task(2)
    def get_incidents(self):
        """Get session incidents."""
        if not self._session_id:
            return

        self.client.get(
            f"/api/v1/proctor/sessions/{self._session_id}/incidents",
            name="/api/v1/proctor/sessions/{id}/incidents",
        )


class MixedWorkloadUser(HttpUser):
    """Mixed workload simulating realistic production traffic patterns."""

    wait_time = between(1, 5)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = str(uuid.uuid4())
        self.enrolled = False

    @task(20)
    def health_check(self):
        """Health checks - highest frequency."""
        self.client.get("/api/v1/health", name="/api/v1/health")

    @task(5)
    def verify_face(self):
        """Face verification - common operation."""
        image_data = generate_test_image()

        self.client.post(
            "/api/v1/verify",
            files={"image": ("test.jpg", image_data, "image/jpeg")},
            data={"user_id": self.user_id},
            name="/api/v1/verify",
        )

    @task(3)
    def check_liveness(self):
        """Liveness check - security critical."""
        image_data = generate_test_image()

        self.client.post(
            "/api/v1/liveness/check",
            files={"image": ("test.jpg", image_data, "image/jpeg")},
            name="/api/v1/liveness/check",
        )

    @task(1)
    def enroll_face(self):
        """Face enrollment - less frequent."""
        image_data = generate_test_image()
        user_id = f"user_{uuid.uuid4().hex[:8]}"

        with self.client.post(
            "/api/v1/enroll",
            files={"image": ("test.jpg", image_data, "image/jpeg")},
            data={"user_id": user_id},
            name="/api/v1/enroll",
            catch_response=True,
        ) as response:
            if response.status_code in [200, 201]:
                self.user_id = user_id
                self.enrolled = True
