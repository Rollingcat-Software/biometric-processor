import json
import logging

import pytest

from app.application.use_cases.verify_puzzle import VerifyPuzzleUseCase
from app.core.config import Settings
from app.core.container import clear_cache, get_verify_puzzle_use_case
from app.core.logging_config import StructuredFormatter
from app.infrastructure.ml.liveness.uniface_liveness_detector import UniFaceLivenessDetector


def test_combined_mode_default_backend_is_hybrid_until_flag_wired():
    """Pin the *current* default-backend behaviour for combined liveness mode.

    `LIVENESS_UNIFACE_DEFAULT_ENABLED` exists in `core/config.py` (default
    False) and its docstring claims it should make UniFace the default
    backend for combined mode. In practice `Settings.get_liveness_backend()`
    does NOT read that flag — it always maps `combined -> hybrid` when
    `LIVENESS_BACKEND` is unset. Production overrides via
    `LIVENESS_BACKEND=uniface` in `.env.prod`, not via the feature flag.

    This test pins the actual behaviour so a future regression that flips
    the default unintentionally fails loud. The earlier name
    (`test_combined_mode_defaults_to_uniface_backend`) was aspirational and
    the flag-wiring work it implied was never landed.
    """
    settings = Settings(_env_file=None, JWT_ENABLED=False)

    assert settings.LIVENESS_MODE == "combined"
    assert settings.LIVENESS_UNIFACE_DEFAULT_ENABLED is False
    assert settings.get_liveness_backend() == "hybrid"


@pytest.mark.xfail(
    reason=(
        "LIVENESS_UNIFACE_DEFAULT_ENABLED is defined in config.py but never "
        "consumed by get_liveness_backend(). Wiring the flag + flipping the "
        "default to True is tracked as a follow-up; this xfail keeps the "
        "intended contract visible until that wiring lands."
    ),
    strict=True,
)
def test_combined_mode_should_default_to_uniface_when_flag_enabled():
    """Aspirational: when LIVENESS_UNIFACE_DEFAULT_ENABLED is True and no
    explicit LIVENESS_BACKEND override is set, combined mode should resolve
    to the UniFace backend. Currently fails because `get_liveness_backend()`
    ignores the flag."""
    settings = Settings(
        _env_file=None,
        JWT_ENABLED=False,
        LIVENESS_UNIFACE_DEFAULT_ENABLED=True,
    )

    assert settings.get_liveness_backend() == "uniface"


def test_verify_puzzle_use_case_pins_spot_check_to_uniface():
    clear_cache()
    use_case = get_verify_puzzle_use_case()

    assert isinstance(use_case, VerifyPuzzleUseCase)
    assert isinstance(use_case._spot_check_detector, UniFaceLivenessDetector)

    clear_cache()


def test_structured_formatter_includes_calibration_payload():
    formatter = StructuredFormatter()
    record = logging.LogRecord(
        name="liveness_calibration",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="liveness_calibration",
        args=(),
        exc_info=None,
    )
    record.event_type = "liveness_calibration"
    record.payload = {
        "score": 91.2,
        "confidence": 0.93,
        "backend": "uniface",
        "sub_scores": {"texture": 0.4},
    }

    output = json.loads(formatter.format(record))

    assert output["event_type"] == "liveness_calibration"
    assert output["score"] == 91.2
    assert output["confidence"] == 0.93
    assert output["backend"] == "uniface"
    assert output["sub_scores"]["texture"] == 0.4
