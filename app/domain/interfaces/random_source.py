"""Random source port for security-relevant draws.

Every draw an attacker must not predict (which challenges a liveness or puzzle
session issues, their order, finger targets, flash colours, shape templates)
goes through this port. Production wires a CSPRNG adapter
(``app.infrastructure.security.random_source``); tests inject a seeded
generator so they stay deterministic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, MutableSequence, Sequence, TypeVar

T = TypeVar("T")


class IRandomSource(ABC):
    """Uniform random draws over finite sets."""

    @abstractmethod
    def choice(self, seq: Sequence[T]) -> T:
        """Return one element of a non-empty sequence, uniformly."""

    @abstractmethod
    def sample(self, population: Sequence[T], k: int) -> List[T]:
        """Return ``k`` distinct positions of ``population`` in uniform random order."""

    @abstractmethod
    def randint(self, a: int, b: int) -> int:
        """Return an integer in the closed range ``[a, b]``, uniformly."""

    @abstractmethod
    def shuffle(self, items: MutableSequence[Any]) -> None:
        """Permute ``items`` in place, uniformly over all permutations."""
