"""Seeded, call-recording random source for deterministic tests."""

from __future__ import annotations

import random
from typing import Any, List, MutableSequence, Sequence, TypeVar

from app.domain.interfaces.random_source import IRandomSource

T = TypeVar("T")


class RecordingRandomSource(IRandomSource):
    """Draws from a seeded ``random.Random`` and records every call name."""

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)
        self.calls: List[str] = []

    def choice(self, seq: Sequence[T]) -> T:
        self.calls.append("choice")
        return self._rng.choice(seq)

    def sample(self, population: Sequence[T], k: int) -> List[T]:
        self.calls.append("sample")
        return self._rng.sample(population, k)

    def randint(self, a: int, b: int) -> int:
        self.calls.append("randint")
        return self._rng.randint(a, b)

    def shuffle(self, items: MutableSequence[Any]) -> None:
        self.calls.append("shuffle")
        self._rng.shuffle(items)
