from redis.asyncio import Redis

from app.core.config import settings

_redis: Redis | None = None  # type: ignore[type-arg]

# ── Canonical key patterns (ТП §5, architect.md lines 130-138) ────────────
SESSION_STATE = "session:{id}:state"       # Hash, TTL 24h
SESSION_HINTS = "session:{id}:hints"       # Hash, TTL 24h
WS_USER       = "ws:{user_id}"             # Set,  TTL 2h
QUEUE_SCENARIO_GENERATION = "queue:scenario_generation"  # Stream
QUEUE_VERIFICATION        = "queue:verification"         # Stream
RATE_LIMIT    = "rate:{user_id}:{route}"   # Hash, TTL 1m
LOCK          = "lock:{resource_id}"       # String NX EX 5m
LLM_MODE_SWITCH = "lock:llm_mode_switch"  # distributed lock for mode switch


def session_state_key(session_id: str) -> str:
    return SESSION_STATE.format(id=session_id)


def session_hints_key(session_id: str) -> str:
    return SESSION_HINTS.format(id=session_id)


def ws_user_key(user_id: str) -> str:
    return WS_USER.format(user_id=user_id)


def rate_limit_key(user_id: str, route: str) -> str:
    return RATE_LIMIT.format(user_id=user_id, route=route)


def lock_key(resource_id: str) -> str:
    return LOCK.format(resource_id=resource_id)


def get_redis() -> Redis:  # type: ignore[type-arg]
    if _redis is None:
        raise RuntimeError("Redis client not initialised — call init_redis() first")
    return _redis


async def init_redis() -> None:
    global _redis
    _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    await check_redis()


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


async def check_redis() -> None:
    """Startup check — raises if Redis is unreachable."""
    await get_redis().ping()
