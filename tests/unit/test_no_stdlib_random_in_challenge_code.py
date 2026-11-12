"""Fitness test: challenge code never draws from the Mersenne Twister.

The module-level ``random`` functions and ``numpy.random`` are predictable
after a short run of observed outputs, so a liveness or puzzle challenge drawn
from them can be anticipated. Draws go through the random source port
(``app.domain.interfaces.random_source``) instead; only its stdlib adapter may
import ``random``.
"""

from __future__ import annotations

import ast
from pathlib import Path

_APP = Path(__file__).resolve().parents[2] / "app"
_SCANNED = ("api", "application", "domain")


def _violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [
                a.name for a in node.names if a.name in ("random", "numpy.random")
            ]
        elif isinstance(node, ast.ImportFrom) and node.module in (
            "random",
            "numpy.random",
        ):
            found.append(f"from {node.module}")
        elif (
            isinstance(node, ast.Attribute)
            and node.attr == "random"
            and isinstance(node.value, ast.Name)
            and node.value.id in ("np", "numpy")
        ):
            found.append(f"{node.value.id}.random")
    return [f"{path.relative_to(_APP.parent)}:{v}" for v in found]


def test_challengeCode_WhenScanned_ShouldNotUseStdlibOrNumpyRandom() -> None:
    violations = [
        v
        for layer in _SCANNED
        for path in sorted((_APP / layer).rglob("*.py"))
        for v in _violations(path)
    ]

    assert violations == []
