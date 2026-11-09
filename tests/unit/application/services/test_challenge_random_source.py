"""Every challenge draw goes through the injected random source.

The production default is the OS CSPRNG (``secrets.SystemRandom``); a seeded
source makes the draws reproducible here. The uniformity smoke tests run the
puzzle session sampler under a FIXED seed, so they are deterministic: they
check that the sampler maps uniform draws to uniform challenges, not the
quality of the generator itself.
"""

from __future__ import annotations

import asyncio
import itertools
import secrets
from collections import Counter
from unittest.mock import AsyncMock

import pytest

from app.api.schemas.active_liveness import ActiveLivenessConfig, ChallengeType
from app.api.schemas.gesture_liveness import GestureLivenessConfig
from app.application.services.active_gesture_liveness_manager import (
    ActiveGestureLivenessManager,
)
from app.application.services.active_liveness_manager import ActiveLivenessManager
from app.application.services.light_challenge_service import LightChallengeService
from app.application.services.puzzle_session_manager import PuzzleSessionManager
from app.application.use_cases.generate_puzzle import GeneratePuzzleUseCase
from tests.unit.application.services.random_source_spy import RecordingRandomSource

_FACE_POOL = [
    ChallengeType.BLINK,
    ChallengeType.SMILE,
    ChallengeType.TURN_LEFT,
    ChallengeType.TURN_RIGHT,
    ChallengeType.OPEN_MOUTH,
    ChallengeType.NOD,
]

# Chi-square upper-tail critical values at p = 0.001, keyed by degrees of freedom.
_CHI2_CRIT_P001 = {4: 18.467, 5: 20.515, 29: 58.301}


def _chi_square(counts: Counter, categories: list, n: int) -> float:
    expected = n / len(categories)
    return sum((counts.get(c, 0) - expected) ** 2 / expected for c in categories)


def _session_manager(source: RecordingRandomSource) -> PuzzleSessionManager:
    return PuzzleSessionManager(random_source=source, clock=lambda: 1000.0)


# ---------------------------------------------------------------------------
# Defaults: production code never falls back to the Mersenne Twister
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "build",
    [
        lambda: PuzzleSessionManager(),
        lambda: LightChallengeService(),
        lambda: ActiveLivenessManager(),
        lambda: ActiveGestureLivenessManager(),
        lambda: GeneratePuzzleUseCase(puzzle_repository=AsyncMock()),
    ],
    ids=["puzzle_session", "light", "active_liveness", "gesture", "legacy_puzzle"],
)
def test_constructor_WhenNoSourceInjected_ShouldUseSecretsSystemRandom(build) -> None:
    service = build()

    assert isinstance(service.random_source.generator, secrets.SystemRandom)


def test_activeLivenessManager_WhenNoLightServiceInjected_ShouldShareItsSource() -> (
    None
):
    source = RecordingRandomSource()

    manager = ActiveLivenessManager(random_source=source)

    assert manager.light_challenge_service.random_source is source


def test_puzzleRoute_WhenBuildingSessionManager_ShouldInjectTheContainerSource() -> (
    None
):
    from app.api.routes.puzzle import get_puzzle_session_manager
    from app.core.container import get_random_source

    manager = get_puzzle_session_manager.__wrapped__()

    assert manager.random_source is get_random_source()
    assert isinstance(manager.random_source.generator, secrets.SystemRandom)


# ---------------------------------------------------------------------------
# Every draw goes through the injected source
# ---------------------------------------------------------------------------


def test_puzzleSession_WhenCreated_ShouldDrawChallengesAndTargetsFromSource() -> None:
    source = RecordingRandomSource(seed=3)
    pool = [ChallengeType.FINGER_COUNT, ChallengeType.MATH]

    session = _session_manager(source).create_session(
        user_id="u", tenant_id="t", allowed_challenge_types=pool, count=2
    )

    assert source.calls == ["sample", "randint", "randint"]
    replay = RecordingRandomSource(seed=3)
    assert [c.action for c in session.challenges] == replay.sample(pool, 2)
    assert [c.params["target"] for c in session.challenges] == [
        replay.randint(1, 5),
        replay.randint(1, 5),
    ]


def test_puzzleSession_WhenCountExceedsPool_ShouldDrawWithReplacementFromSource() -> (
    None
):
    source = RecordingRandomSource(seed=5)

    _session_manager(source).create_session(
        user_id="u",
        tenant_id="t",
        allowed_challenge_types=[ChallengeType.BLINK],
        count=3,
    )

    assert source.calls == ["choice", "choice", "choice"]


def test_lightChallenge_WhenGenerated_ShouldPickColourFromSource() -> None:
    source = RecordingRandomSource()

    LightChallengeService(random_source=source).generate_challenge()

    assert source.calls == ["choice"]


def test_activeLiveness_WhenRandomized_ShouldShuffleWithSource() -> None:
    source = RecordingRandomSource()

    ActiveLivenessManager(random_source=source).create_session(
        ActiveLivenessConfig(num_challenges=3, randomize=True)
    )

    assert "shuffle" in source.calls


def test_gestureLiveness_WhenRandomized_ShouldDrawOrderAndTargetsFromSource() -> None:
    source = RecordingRandomSource()
    manager = ActiveGestureLivenessManager(random_source=source)

    manager.create_session(
        GestureLivenessConfig(
            required_challenges=[ChallengeType.FINGER_COUNT, ChallengeType.MATH],
            num_challenges=2,
        )
    )
    manager.create_session(GestureLivenessConfig(num_challenges=3, randomize=True))

    # FINGER_COUNT target, MATH target, MATH split; then the default-pool shuffle.
    assert source.calls[:4] == ["randint", "randint", "randint", "shuffle"]


def test_legacyPuzzle_WhenGenerated_ShouldDrawStepsFromSource() -> None:
    source = RecordingRandomSource()
    use_case = GeneratePuzzleUseCase(
        puzzle_repository=AsyncMock(), random_source=source
    )

    puzzle = asyncio.run(use_case.execute(difficulty="standard"))

    assert source.calls[0] == "randint"
    assert source.calls[1:] == ["choice"] * len(puzzle.steps)


# ---------------------------------------------------------------------------
# Uniformity smoke tests (fixed seed, deterministic)
# ---------------------------------------------------------------------------


def test_puzzleSession_WhenSampledManyTimes_ShouldIssueOrderedPairsUniformly() -> None:
    manager = _session_manager(RecordingRandomSource(seed=20261109))
    n = 6000
    pairs: Counter = Counter()
    for i in range(n):
        session = manager.create_session(
            user_id=f"u{i}", tenant_id="t", allowed_challenge_types=_FACE_POOL, count=2
        )
        actions = tuple(c.action for c in session.challenges)
        assert actions[0] != actions[1]
        pairs[actions] += 1

    categories = list(itertools.permutations(_FACE_POOL, 2))
    assert set(pairs) == set(categories)
    assert _chi_square(pairs, categories, n) < _CHI2_CRIT_P001[len(categories) - 1]


def test_puzzleSession_WhenSampledManyTimes_ShouldIssueFingerTargetsUniformly() -> None:
    manager = _session_manager(RecordingRandomSource(seed=42))
    n = 5000
    targets: Counter = Counter()
    for i in range(n):
        session = manager.create_session(
            user_id=f"u{i}",
            tenant_id="t",
            allowed_challenge_types=[ChallengeType.FINGER_COUNT],
            count=1,
        )
        targets[session.challenges[0].params["target"]] += 1

    categories = [1, 2, 3, 4, 5]
    assert set(targets) == set(categories)
    assert _chi_square(targets, categories, n) < _CHI2_CRIT_P001[len(categories) - 1]


def test_puzzleSession_WhenSampledManyTimes_ShouldPlaceEachTypeFirstUniformly() -> None:
    manager = _session_manager(RecordingRandomSource(seed=7))
    n = 6000
    first: Counter = Counter()
    for i in range(n):
        session = manager.create_session(
            user_id=f"u{i}", tenant_id="t", allowed_challenge_types=_FACE_POOL, count=3
        )
        first[session.challenges[0].action] += 1

    assert _chi_square(first, _FACE_POOL, n) < _CHI2_CRIT_P001[len(_FACE_POOL) - 1]
