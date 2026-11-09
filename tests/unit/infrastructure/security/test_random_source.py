"""The production random source is the OS CSPRNG, and the adapter delegates exactly."""

from __future__ import annotations

import random
import secrets

from app.domain.interfaces.random_source import IRandomSource
from app.infrastructure.security.random_source import (
    StdlibRandomSourceAdapter,
    csprng_random_source,
)


def test_csprngRandomSource_WhenCreated_ShouldDrawFromSecretsSystemRandom() -> None:
    source = csprng_random_source()

    assert isinstance(source, IRandomSource)
    assert isinstance(source.generator, secrets.SystemRandom)


def test_stdlibAdapter_WhenSeeded_ShouldReproduceTheGeneratorDrawForDraw() -> None:
    source = StdlibRandomSourceAdapter(random.Random(7))
    reference = random.Random(7)
    pool = ["a", "b", "c", "d", "e"]

    assert source.choice(pool) == reference.choice(pool)
    assert source.sample(pool, 3) == reference.sample(pool, 3)
    assert source.randint(1, 5) == reference.randint(1, 5)
    mine, theirs = list(pool), list(pool)
    source.shuffle(mine)
    reference.shuffle(theirs)
    assert mine == theirs


def test_stdlibAdapter_WhenSamplingWholePopulation_ShouldReturnEachElementOnce() -> (
    None
):
    source = StdlibRandomSourceAdapter(random.Random(1))

    drawn = source.sample(list(range(10)), 10)

    assert sorted(drawn) == list(range(10))
