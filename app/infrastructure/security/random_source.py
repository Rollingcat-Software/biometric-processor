"""Standard-library adapter for the random source port.

``csprng_random_source()`` is the production source: it draws from
``secrets.SystemRandom`` (the operating system CSPRNG behind ``os.urandom``),
never from the Mersenne Twister behind the module-level ``random`` functions,
whose output is predictable after 624 observed 32-bit words. Tests build a
``StdlibRandomSourceAdapter`` over a seeded ``random.Random`` instead.
"""

from __future__ import annotations

import random
import secrets
from typing import Any, List, MutableSequence, Sequence, TypeVar

from app.domain.interfaces.random_source import IRandomSource

T = TypeVar("T")


class StdlibRandomSourceAdapter(IRandomSource):
    """Delegates every draw to one ``random.Random`` instance."""

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng

    @property
    def generator(self) -> random.Random:
        return self._rng

    def choice(self, seq: Sequence[T]) -> T:
        return self._rng.choice(seq)

    def sample(self, population: Sequence[T], k: int) -> List[T]:
        return self._rng.sample(population, k)

    def randint(self, a: int, b: int) -> int:
        return self._rng.randint(a, b)

    def shuffle(self, items: MutableSequence[Any]) -> None:
        self._rng.shuffle(items)


def csprng_random_source() -> IRandomSource:
    """Return a source backed by the operating system CSPRNG."""
    return StdlibRandomSourceAdapter(secrets.SystemRandom())
