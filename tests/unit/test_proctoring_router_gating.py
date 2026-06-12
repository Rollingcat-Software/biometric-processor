"""Tests for the proctoring + live-analysis router kill-switch.

GPU-less hardening (2026-06-12): the proctoring HTTP/WebSocket routers and the
``/ws/live-analysis`` WebSocket run the HEAVIEST per-frame ML in the service
(YOLOv8 object detection + MediaPipe gaze + texture/FFT+optical-flow deepfake +
MTCNN+Facenet512 face-verify + UniFace MiniFASNet liveness, plus optional
DeepFace demographics ~400 MB) yet had ZERO production callers (no /proctor,
/live-analysis, or /ws/live-analysis references in identity-core-api or
web-app). They were mounted UNCONDITIONALLY on a CPU-only box.

They are now gated behind ``PROCTORING_ROUTER_ENABLED`` (default False),
mirroring the existing ``DEMOGRAPHICS_ROUTER_ENABLED`` pattern. The
``/ws/live-analysis`` WebSocket additionally now authenticates on accept via
the same API-key mechanism the rest of the service uses, because the HTTP
``@app.middleware`` API-key guard never runs for WebSocket scopes.

Implementation note: we don't import ``app.main`` directly (it wires up the
full container, GPU detection, lifespan handlers, and real ML preloading).
Instead we replicate the small gating block under test on a fresh ``FastAPI``
instance, mirroring ``test_demographics_gating.py``.
"""

import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


API_PREFIX = "/api/v1"


def _try_import(module: str):
    """Import a heavy-ML route module, skipping cleanly if deps are missing.

    Importing the proctoring / live-analysis routers transitively pulls cv2,
    DeepFace, etc. via ``app.core.container``. In a stripped-down dev env those
    may be missing — skip the route-registration tests while the Settings-default
    tests below keep running.
    """
    try:
        return importlib.import_module(module)
    except ImportError as e:  # pragma: no cover - exercised only in light envs
        pytest.skip(f"heavy ML deps not installed: {e}")


def _build_app(*, proctoring_enabled: bool) -> FastAPI:
    """Build a minimal FastAPI app with the same gating logic as main.py."""
    app = FastAPI()
    if proctoring_enabled:
        proctor = _try_import("app.api.routes.proctor")
        proctor_ws = _try_import("app.api.routes.proctor_ws")
        live_analysis = _try_import("app.api.routes.live_analysis")
        app.include_router(proctor.router, prefix=API_PREFIX)
        app.include_router(proctor_ws.router, prefix=API_PREFIX)
        app.include_router(live_analysis.router, prefix=API_PREFIX)
    return app


class TestProctoringRouterGating:
    """Proctoring + live-analysis routers must be off by default."""

    def test_routers_absent_when_disabled(self):
        """With the flag OFF, proctoring + live-analysis routes must 404."""
        app = _build_app(proctoring_enabled=False)
        client = TestClient(app)

        # Proctoring HTTP route — must not exist.
        resp = client.post(f"{API_PREFIX}/proctoring/sessions")
        assert resp.status_code == 404, (
            f"expected 404 (route not registered) but got {resp.status_code}: "
            f"{resp.text[:200]}"
        )

        # OpenAPI schema must NOT advertise the paths either.
        schema = client.get("/openapi.json").json()
        paths = schema.get("paths", {})
        assert f"{API_PREFIX}/proctoring/sessions" not in paths
        assert f"{API_PREFIX}/ws/live-analysis" not in paths

    def test_routers_present_when_enabled(self):
        """With the flag ON, proctoring + live-analysis routes are registered.

        We assert against the app's route table directly rather than driving a
        TestClient: building the OpenAPI schema / hitting a handler would resolve
        the proctor session-repository dependency, which raises unless a postgres
        DATABASE_URL is configured (in-memory storage was removed for prod
        safety). Inspecting ``app.routes`` proves the gating block mounted the
        routers without needing a live DB, which is exactly what's under test.
        """
        app = _build_app(proctoring_enabled=True)
        mounted = {getattr(r, "path", None) for r in app.routes}

        assert f"{API_PREFIX}/proctoring/sessions" in mounted, (
            "proctoring HTTP route should be registered when "
            "PROCTORING_ROUTER_ENABLED=true"
        )
        assert f"{API_PREFIX}/ws/live-analysis" in mounted, (
            "live-analysis WebSocket route should be registered when "
            "PROCTORING_ROUTER_ENABLED=true"
        )


class TestProctoringRouterDefault:
    """The Settings default for PROCTORING_ROUTER_ENABLED must be False."""

    def test_default_is_false(self):
        """Settings() default must NOT enable the proctoring routers."""
        from app.core.config import Settings

        s = Settings(_env_file=None)
        assert s.PROCTORING_ROUTER_ENABLED is False, (
            "PROCTORING_ROUTER_ENABLED must default to False — zero production "
            "callers + heaviest per-frame ML on a CPU-only box"
        )

    def test_explicit_true_is_respected(self):
        """Operators can opt in via env/kwarg."""
        from app.core.config import Settings

        s = Settings(_env_file=None, PROCTORING_ROUTER_ENABLED=True)
        assert s.PROCTORING_ROUTER_ENABLED is True


class TestLiveAnalysisWebSocketAuth:
    """The /ws/live-analysis WebSocket must authenticate on accept.

    The HTTP API-key middleware does not run for WebSocket scopes, so the
    socket was reachable with no key on the Docker network. ``_is_ws_authenticated``
    closes that gap, fail-closed, using the same API-key mechanism as the rest
    of the service.
    """

    def _auth_fn(self):
        live_analysis = _try_import("app.api.routes.live_analysis")
        return live_analysis._is_ws_authenticated

    def _fake_ws(self, *, headers=None, query=None):
        """Minimal duck-typed stand-in for starlette's WebSocket."""

        class _FakeWS:
            def __init__(self, headers, query):
                self.headers = headers or {}
                self.query_params = query or {}
                self.client = ("127.0.0.1", 0)

        return _FakeWS(headers, query)

    def test_open_when_api_key_auth_disabled(self, monkeypatch):
        """When API-key auth is not configured, WS auth passes (matches HTTP)."""
        from app.core.config import settings

        auth = self._auth_fn()
        monkeypatch.setattr(settings, "API_KEY_ENABLED", False, raising=False)
        monkeypatch.setattr(settings, "API_KEY_REQUIRE_AUTH", False, raising=False)
        assert auth(self._fake_ws()) is True

    def test_rejected_without_key_when_required(self, monkeypatch):
        """With API-key auth armed, a keyless socket is rejected (fail-closed)."""
        from app.core.config import settings

        auth = self._auth_fn()
        monkeypatch.setattr(settings, "API_KEY_ENABLED", True, raising=False)
        monkeypatch.setattr(settings, "API_KEY_REQUIRE_AUTH", True, raising=False)
        monkeypatch.setattr(settings, "API_KEY_SECRET", "s3cret", raising=False)
        monkeypatch.setattr(settings, "API_KEY_HEADER", "X-API-Key", raising=False)
        assert auth(self._fake_ws()) is False

    def test_accepts_valid_key_via_header(self, monkeypatch):
        """A correct X-API-Key header is accepted."""
        from app.core.config import settings

        auth = self._auth_fn()
        monkeypatch.setattr(settings, "API_KEY_ENABLED", True, raising=False)
        monkeypatch.setattr(settings, "API_KEY_REQUIRE_AUTH", True, raising=False)
        monkeypatch.setattr(settings, "API_KEY_SECRET", "s3cret", raising=False)
        monkeypatch.setattr(settings, "API_KEY_HEADER", "X-API-Key", raising=False)
        ws = self._fake_ws(headers={"X-API-Key": "s3cret"})
        assert auth(ws) is True

    def test_accepts_valid_key_via_query_param(self, monkeypatch):
        """Browser WS clients can pass the key via ?api_key= fallback."""
        from app.core.config import settings

        auth = self._auth_fn()
        monkeypatch.setattr(settings, "API_KEY_ENABLED", True, raising=False)
        monkeypatch.setattr(settings, "API_KEY_REQUIRE_AUTH", True, raising=False)
        monkeypatch.setattr(settings, "API_KEY_SECRET", "s3cret", raising=False)
        monkeypatch.setattr(settings, "API_KEY_HEADER", "X-API-Key", raising=False)
        ws = self._fake_ws(query={"api_key": "s3cret"})
        assert auth(ws) is True

    def test_rejects_wrong_key(self, monkeypatch):
        """An incorrect key is rejected."""
        from app.core.config import settings

        auth = self._auth_fn()
        monkeypatch.setattr(settings, "API_KEY_ENABLED", True, raising=False)
        monkeypatch.setattr(settings, "API_KEY_REQUIRE_AUTH", True, raising=False)
        monkeypatch.setattr(settings, "API_KEY_SECRET", "s3cret", raising=False)
        monkeypatch.setattr(settings, "API_KEY_HEADER", "X-API-Key", raising=False)
        ws = self._fake_ws(headers={"X-API-Key": "wrong"})
        assert auth(ws) is False

    def test_fail_closed_when_secret_missing(self, monkeypatch):
        """Auth required but no secret configured -> reject (misconfiguration)."""
        from app.core.config import settings

        auth = self._auth_fn()
        monkeypatch.setattr(settings, "API_KEY_ENABLED", True, raising=False)
        monkeypatch.setattr(settings, "API_KEY_REQUIRE_AUTH", True, raising=False)
        monkeypatch.setattr(settings, "API_KEY_SECRET", "", raising=False)
        ws = self._fake_ws(headers={"X-API-Key": "anything"})
        assert auth(ws) is False
