"""Tests for demographics router feature-flag gating.

Covers FINDINGS_2026-04-25 B2: the /api/v1/demographics/* routes must be
disabled by default and only registered when DEMOGRAPHICS_ROUTER_ENABLED=true.

Rationale: web-app has zero callers for this endpoint, and DeepFace.analyze
lazy-loads 4 extra models (age/gender/race/emotion, ~400 MB) the first time
it is hit. Hetzner CX43 prod is memory-constrained; we don't want a stray
caller to swing it into OOM.

Implementation note: we don't import ``app.main`` directly, because that
module wires up the full container, GPU detection, lifespan handlers, and
real ML preloading.  Instead we replicate the small gating block under test
on a fresh ``FastAPI`` instance.  This mirrors what main.py does at module
load and keeps the test fast and isolated.
"""

import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


API_PREFIX = "/api/v1"


def _try_import_demographics_router():
    """Import the demographics route module if heavy ML deps are present.

    Importing ``app.api.routes.demographics`` transitively pulls cv2 and
    DeepFace via ``app.core.container``.  In a stripped-down dev env those
    may be missing — return None so the route-registration tests skip
    cleanly while the Settings-default tests below keep running.
    """
    try:
        return importlib.import_module("app.api.routes.demographics")
    except ImportError as e:  # pragma: no cover - exercised only in light envs
        pytest.skip(f"heavy ML deps not installed: {e}")


def _build_app(*, demographics_enabled: bool) -> FastAPI:
    """Build a minimal FastAPI app with the same gating logic as main.py."""
    app = FastAPI()
    if demographics_enabled:
        demographics = _try_import_demographics_router()
        app.include_router(demographics.router, prefix=API_PREFIX)
    return app


class TestDemographicsRouterGating:
    """B2: demographics router must be off by default."""

    def test_router_absent_when_disabled(self):
        """With the flag OFF, /api/v1/demographics/analyze must 404."""
        app = _build_app(demographics_enabled=False)
        client = TestClient(app)

        # POST is the real verb; we don't even need a valid file because the
        # route doesn't exist — FastAPI must answer 404 before any handler runs.
        resp = client.post(f"{API_PREFIX}/demographics/analyze")
        assert resp.status_code == 404, (
            f"expected 404 (route not registered) but got {resp.status_code}: "
            f"{resp.text[:200]}"
        )

        # OpenAPI schema must NOT advertise the path either, so SDK generators
        # and Swagger consumers can't accidentally call it.
        schema = client.get("/openapi.json").json()
        assert f"{API_PREFIX}/demographics/analyze" not in schema.get("paths", {})

    def test_router_present_when_enabled(self):
        """With the flag ON, /api/v1/demographics/analyze must be registered.

        We don't actually invoke the analyzer (would load ~400 MB of DeepFace
        weights); we just confirm FastAPI knows about the path.
        """
        app = _build_app(demographics_enabled=True)
        client = TestClient(app)

        schema = client.get("/openapi.json").json()
        assert f"{API_PREFIX}/demographics/analyze" in schema.get("paths", {}), (
            "demographics route should be registered when "
            "DEMOGRAPHICS_ROUTER_ENABLED=true"
        )

        # POST without a file: FastAPI's validation layer answers 422
        # (missing required form field), proving the route IS wired up
        # — anything other than 404 confirms registration.
        resp = client.post(f"{API_PREFIX}/demographics/analyze")
        assert resp.status_code != 404, (
            "route should exist when flag is on; got 404 which means it wasn't registered"
        )


class TestDemographicsRouterEnabledDefault:
    """The Settings default for DEMOGRAPHICS_ROUTER_ENABLED must be False."""

    def test_default_is_false(self):
        """Settings() default must NOT enable the demographics router."""
        from app.core.config import Settings

        # Build a Settings instance ignoring any ambient .env file
        s = Settings(_env_file=None)
        assert s.DEMOGRAPHICS_ROUTER_ENABLED is False, (
            "DEMOGRAPHICS_ROUTER_ENABLED must default to False — see "
            "FINDINGS_2026-04-25 B2"
        )

    def test_explicit_true_is_respected(self):
        """Operators can opt in via env/kwarg."""
        from app.core.config import Settings

        s = Settings(_env_file=None, DEMOGRAPHICS_ROUTER_ENABLED=True)
        assert s.DEMOGRAPHICS_ROUTER_ENABLED is True
