"""
Redis 캐시 서비스
"""

import json
import logging
from typing import Optional, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client = None


def get_redis():
    """Redis 클라이언트 반환 (lazy initialization)"""
    global _redis_client
    if _redis_client is None:
        try:
            import redis
            _redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
            )
            _redis_client.ping()
            logger.info("Redis 연결 성공")
        except Exception as e:
            logger.warning(f"Redis 연결 실패, 캐시 비활성화: {e}")
            _redis_client = None
    return _redis_client


async def cache_get(key: str) -> Optional[Any]:
    """캐시에서 값 조회"""
    client = get_redis()
    if client is None:
        return None
    try:
        value = client.get(key)
        return json.loads(value) if value else None
    except Exception as e:
        logger.warning(f"캐시 조회 실패 [{key}]: {e}")
        return None


async def cache_set(key: str, value: Any, ttl: int = None) -> bool:
    """캐시에 값 저장"""
    client = get_redis()
    if client is None:
        return False
    try:
        serialized = json.dumps(value, ensure_ascii=False)
        client.setex(key, ttl or settings.cache_ttl, serialized)
        return True
    except Exception as e:
        logger.warning(f"캐시 저장 실패 [{key}]: {e}")
        return False


async def cache_delete(key: str) -> bool:
    """캐시에서 값 삭제"""
    client = get_redis()
    if client is None:
        return False
    try:
        client.delete(key)
        return True
    except Exception as e:
        logger.warning(f"캐시 삭제 실패 [{key}]: {e}")
        return False
