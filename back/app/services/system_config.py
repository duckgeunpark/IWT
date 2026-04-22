"""
시스템 설정 서비스 — 관리자가 조정 가능한 파라미터 읽기/쓰기
인메모리 캐시 (5분 TTL)로 DB 부하 최소화
"""

import time
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULTS: Dict[str, Dict[str, str]] = {
    "place_match_radius_m": {
        "value": "20",
        "description": "Place DB 캐시 매칭 반경 (미터). 이 반경 내 기존 Place가 있으면 Google Maps API 호출 생략.",
    },
    "cluster_distance_km": {
        "value": "0.5",
        "description": "사진 클러스터링 거리 기준 (km). 직전 사진과 이 거리 이내이면 같은 클러스터로 분류.",
    },
    "cluster_time_hours": {
        "value": "2.0",
        "description": "사진 클러스터링 시간 기준 (시간). 직전 사진과 이 시간 이내이면 같은 클러스터로 분류.",
    },
}

_CACHE_TTL = 300  # 5분


class SystemConfigService:
    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._cache_ts: float = 0.0

    def _is_cache_valid(self) -> bool:
        return bool(self._cache) and (time.time() - self._cache_ts) < _CACHE_TTL

    def _load_cache(self, db) -> None:
        from app.models.db_models import SystemConfig
        rows = db.query(SystemConfig).all()
        self._cache = {r.key: r.value for r in rows}
        self._cache_ts = time.time()

    def get(self, key: str, default: Any = None, db=None) -> Any:
        if db and not self._is_cache_valid():
            try:
                self._load_cache(db)
            except Exception as e:
                logger.warning(f"SystemConfig 캐시 로드 실패: {e}")

        raw = self._cache.get(key)
        if raw is None:
            raw = _DEFAULTS.get(key, {}).get("value")
        if raw is None:
            return default
        try:
            return type(default)(raw) if default is not None else raw
        except (ValueError, TypeError):
            return raw

    def get_float(self, key: str, default: float = 0.0, db=None) -> float:
        try:
            return float(self.get(key, default, db))
        except (ValueError, TypeError):
            return default

    def get_int(self, key: str, default: int = 0, db=None) -> int:
        try:
            return int(float(self.get(key, default, db)))
        except (ValueError, TypeError):
            return default

    def set(self, key: str, value: str, db) -> None:
        from app.models.db_models import SystemConfig
        row = db.query(SystemConfig).filter(SystemConfig.key == key).first()
        if row:
            row.value = value
        else:
            db.add(SystemConfig(
                key=key,
                value=value,
                description=_DEFAULTS.get(key, {}).get("description"),
            ))
        db.commit()
        self._cache[key] = value
        self._cache_ts = time.time()

    def get_all(self, db) -> List[Dict]:
        if not self._is_cache_valid():
            try:
                self._load_cache(db)
            except Exception as e:
                logger.warning(f"SystemConfig 캐시 로드 실패: {e}")

        result = []
        all_keys = set(list(self._cache.keys()) + list(_DEFAULTS.keys()))
        for key in sorted(all_keys):
            value = self._cache.get(key, _DEFAULTS.get(key, {}).get("value", ""))
            description = _DEFAULTS.get(key, {}).get("description", "")
            result.append({"key": key, "value": value, "description": description})
        return result

    def initialize_defaults(self, db) -> None:
        """서버 시작 시 기본값이 없는 키만 삽입"""
        from app.models.db_models import SystemConfig
        for key, meta in _DEFAULTS.items():
            exists = db.query(SystemConfig).filter(SystemConfig.key == key).first()
            if not exists:
                db.add(SystemConfig(key=key, value=meta["value"], description=meta["description"]))
        db.commit()
        self._load_cache(db)
        logger.info("SystemConfig 기본값 초기화 완료")


system_config_service = SystemConfigService()
