import pytest

from app.api.schemas.active_liveness import ActiveLivenessSession, Challenge
from app.api.schemas.active_liveness import ChallengeType
from app.core import container
from app.infrastructure.persistence.repositories.in_memory_active_liveness_session_repository import (
    InMemoryActiveLivenessSessionRepository,
)
from app.infrastructure.persistence.repositories.redis_active_liveness_session_repository import (
    RedisActiveLivenessSessionRepository,
)


class FakeRedisPipeline:
    def __init__(self, client):
        self._client = client
        self._watched = None
        self._commands = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._commands.clear()
        self._watched = None

    async def watch(self, key):
        self._watched = key

    async def get(self, key):
        return await self._client.get(key)

    async def unwatch(self):
        self._watched = None

    def multi(self):
        self._commands.clear()

    def setex(self, key, ttl, value):
        self._commands.append(("setex", key, ttl, value))

    async def execute(self):
        for command, key, ttl, value in self._commands:
            if command == "setex":
                await self._client.setex(key, ttl, value)
        self._commands.clear()


class FakeRedis:
    def __init__(self):
        self.storage = {}
        self.closed = False

    async def setex(self, key, ttl, value):
        self.storage[key] = {"value": value, "ttl": ttl}

    async def get(self, key):
        item = self.storage.get(key)
        return None if item is None else item["value"]

    async def delete(self, key):
        return 1 if self.storage.pop(key, None) is not None else 0

    def pipeline(self, transaction=True):
        return FakeRedisPipeline(self)

    async def close(self):
        self.closed = True


@pytest.fixture
def sample_session():
    return ActiveLivenessSession(
        session_id="session-1",
        challenges=[
            Challenge(type=ChallengeType.BLINK, instruction="Blink"),
        ],
        current_challenge_index=0,
        started_at=1_000.0,
        expires_at=1_120.0,
        last_activity_at=1_000.0,
        current_challenge_started_at=1_000.0,
    )


@pytest.fixture
def fake_redis_repo(monkeypatch):
    fake_redis = FakeRedis()

    def fake_from_url(*args, **kwargs):
        return fake_redis

    monkeypatch.setattr(
        "app.infrastructure.persistence.repositories.redis_active_liveness_session_repository.redis.from_url",
        fake_from_url,
    )
    repo = RedisActiveLivenessSessionRepository("redis://test")
    return repo, fake_redis


@pytest.mark.asyncio
async def test_save_and_get_active_liveness_session(fake_redis_repo, sample_session, monkeypatch):
    repo, fake_redis = fake_redis_repo
    monkeypatch.setattr(
        "app.infrastructure.persistence.repositories.redis_active_liveness_session_repository.time.time",
        lambda: 1_000.0,
    )

    await repo.save(sample_session)
    loaded = await repo.get(sample_session.session_id)

    assert loaded is not None
    assert loaded.session_id == sample_session.session_id
    assert fake_redis.storage[repo._key(sample_session.session_id)]["ttl"] == 120


@pytest.mark.asyncio
async def test_get_deletes_expired_active_session(fake_redis_repo, sample_session, monkeypatch):
    repo, fake_redis = fake_redis_repo
    sample_session.expires_at = 900.0
    await fake_redis.setex(repo._key(sample_session.session_id), 1, sample_session.model_dump_json())

    monkeypatch.setattr(
        "app.infrastructure.persistence.repositories.redis_active_liveness_session_repository.time.time",
        lambda: 1_000.0,
    )

    loaded = await repo.get(sample_session.session_id)

    assert loaded is None
    assert repo._key(sample_session.session_id) not in fake_redis.storage


@pytest.mark.asyncio
async def test_mutate_updates_session_and_uses_completion_ttl(fake_redis_repo, sample_session, monkeypatch):
    repo, fake_redis = fake_redis_repo
    await fake_redis.setex(repo._key(sample_session.session_id), 120, sample_session.model_dump_json())

    monkeypatch.setattr(
        "app.infrastructure.persistence.repositories.redis_active_liveness_session_repository.time.time",
        lambda: 1_010.0,
    )

    async def handler(session):
        session.is_complete = True
        session.completed_at = 1_010.0
        session.passed = True
        return "ok"

    result = await repo.mutate(sample_session.session_id, handler)
    stored = await repo.get(sample_session.session_id)

    assert result == "ok"
    assert stored is not None
    assert stored.is_complete is True
    assert fake_redis.storage[repo._key(sample_session.session_id)]["ttl"] == repo.COMPLETED_SESSION_TTL_SECONDS


@pytest.mark.asyncio
async def test_delete_returns_true_when_session_exists(fake_redis_repo, sample_session):
    repo, fake_redis = fake_redis_repo
    await fake_redis.setex(repo._key(sample_session.session_id), 120, sample_session.model_dump_json())

    deleted = await repo.delete(sample_session.session_id)

    assert deleted is True
    assert fake_redis.storage == {}


def test_container_uses_redis_repository_by_default(monkeypatch):
    container.clear_cache()

    class StubRedisRepository:
        def __init__(self, redis_url, max_connections):
            self.redis_url = redis_url
            self.max_connections = max_connections

    monkeypatch.setattr(container.settings, "TESTING", False)
    monkeypatch.setattr(
        "app.core.container.RedisActiveLivenessSessionRepository",
        StubRedisRepository,
    )

    repository = container.get_active_liveness_session_repository()

    assert isinstance(repository, StubRedisRepository)
    assert repository.redis_url == container.settings.redis_url

    container.clear_cache()


def test_container_uses_in_memory_repository_in_testing(monkeypatch):
    container.clear_cache()
    monkeypatch.setattr(container.settings, "TESTING", True)

    repository = container.get_active_liveness_session_repository()

    assert isinstance(repository, InMemoryActiveLivenessSessionRepository)

    container.clear_cache()
    monkeypatch.setattr(container.settings, "TESTING", False)
