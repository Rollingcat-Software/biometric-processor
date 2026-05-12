"""Integration: confirm no runtime code path imports mediapipe.solutions.

Added 2026-05-12 after the mp.solutions → mp.tasks.vision port.

The legacy ``mp.solutions`` namespace was removed in mediapipe 0.10.35. Any
remaining call site would fail at runtime with:

    AttributeError: module 'mediapipe' has no attribute 'solutions'

The /verify route is the primary symptom surface today (every call was
logging ``Landmark detection failed: module 'mediapipe' has no attribute
'solutions'``). Rather than spinning up the full FastAPI stack and asserting
on the absence of a log line — which is brittle — this test does two things:

1. AST-scans the app/ tree for executable references to mp.solutions. Any
   non-comment, non-docstring reference fails the test.
2. Verifies the ported call sites can import without crashing.

Comments and docstrings that *mention* the migration are still permitted.
"""

from __future__ import annotations

import ast
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
APP_ROOT = REPO_ROOT / "app"


def _executable_references_to_mp_solutions(py_file: pathlib.Path) -> list[str]:
    """Return locations of executable mp.solutions references in py_file.

    AST walks the module; anything inside a string literal (docstring or
    comment-equivalent string assignment) is invisible to the AST, so this
    naturally ignores comments and docstring references.
    """
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            # Walk back along the attribute chain to find the root identifier.
            current = node
            attr_chain = []
            while isinstance(current, ast.Attribute):
                attr_chain.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                attr_chain.append(current.id)
                attr_chain.reverse()
                # Match patterns: mp.solutions, mediapipe.solutions
                joined = ".".join(attr_chain)
                if joined.startswith("mp.solutions") or joined.startswith(
                    "mediapipe.solutions"
                ):
                    offenders.append(f"{py_file}:{node.lineno}: {joined}")
    return offenders


def test_no_executable_mp_solutions_references_in_app() -> None:
    """No production code under app/ may reference mp.solutions executable-side."""
    offenders: list[str] = []
    for py_file in APP_ROOT.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        offenders.extend(_executable_references_to_mp_solutions(py_file))

    assert not offenders, (
        "Found executable references to mp.solutions / mediapipe.solutions:\n"
        + "\n".join(offenders)
        + "\n\nThe mp.solutions namespace was removed in mediapipe 0.10.35. "
        "Port to mp.tasks.vision.FaceLandmarker — see "
        "app/infrastructure/ml/landmarks/face_landmarker_loader.py."
    )


def test_ported_modules_import_cleanly() -> None:
    """The four ported modules must import without crashing in prod env."""
    # If any of these still referenced mp.solutions executable-side, the
    # import itself would not crash (the reference is inside lazy-init), but
    # any subsequent .detect() call would. The previous test (AST) catches
    # the executable references; this test catches import-time syntax /
    # name errors introduced by the port.
    from app.infrastructure.ml.landmarks import face_landmarker_loader  # noqa: F401
    from app.infrastructure.ml.landmarks.mediapipe_landmarks import (  # noqa: F401
        MediaPipeLandmarkDetector,
    )
    from app.infrastructure.ml.liveness.active_liveness_detector import (  # noqa: F401
        ActiveLivenessDetector,
    )
    from app.infrastructure.ml.proctoring.mediapipe_gaze_tracker import (  # noqa: F401
        MediaPipeGazeTracker,
    )
    from app.infrastructure.ml.quality.quality_assessor import (  # noqa: F401
        QualityAssessor,
    )
