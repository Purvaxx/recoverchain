"""
Redis is optional. The app runs fully offline without it — nothing on the
request path depends on Redis today; only /health probes it. Set REDIS_URL to
enable it.
"""

import os

REDIS_URL = os.getenv("REDIS_URL", "")  # empty = disabled

try:
    import redis  # noqa: F401

    _REDIS_AVAILABLE = True
except Exception:  # package not installed
    _REDIS_AVAILABLE = False


def redis_enabled() -> bool:
    return bool(REDIS_URL) and _REDIS_AVAILABLE


def get_redis_client():
    if not redis_enabled():
        return None
    return redis.Redis.from_url(
        REDIS_URL, decode_responses=True, socket_connect_timeout=0.2, socket_timeout=0.2
    )
