"""
역지오코딩 서비스 — Google Maps Geocoding API
Place 테이블을 캐시로 활용해 API 호출 횟수 최소화
"""

import os
import math
import logging
from typing import Dict, Optional

import httpx

from app.services.system_config import system_config_service

logger = logging.getLogger(__name__)

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

# place_type 변환 우선순위 (앞쪽일수록 더 구체적)
_TYPE_PRIORITY = [
    "restaurant", "cafe", "bar", "food", "bakery",
    "tourist_attraction", "museum", "art_gallery", "amusement_park", "zoo",
    "park", "natural_feature", "campground",
    "lodging", "hotel",
    "shopping_mall", "store", "supermarket",
    "airport", "train_station", "transit_station",
    "hospital", "school", "university",
    "point_of_interest", "establishment",
]


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 간 거리(미터) 반환"""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _pick_place_type(types: list) -> Optional[str]:
    for t in _TYPE_PRIORITY:
        if t in types:
            return t
    return types[0] if types else None


def _parse_google_response(data: Dict, lat: float, lng: float) -> Optional[Dict]:
    results = data.get("results", [])
    if not results:
        return None

    best = results[0]
    components = best.get("address_components", [])

    def _get(comp_type: str) -> Optional[str]:
        for c in components:
            if comp_type in c.get("types", []):
                return c.get("long_name")
        return None

    place_id = best.get("place_id")
    types = best.get("types", [])
    place_type = _pick_place_type(types)

    # 장소명: 첫 번째 결과의 formatted_address 앞부분 또는 establishment name
    name = _get("point_of_interest") or _get("establishment") or _get("premise")
    if not name:
        addr = best.get("formatted_address", "")
        name = addr.split(",")[0].strip() if addr else "알 수 없는 장소"

    return {
        "country":    _get("country"),
        "city":       _get("locality") or _get("administrative_area_level_2"),
        "region":     _get("administrative_area_level_1"),
        "address":    best.get("formatted_address"),
        "landmark":   name,
        "place_id":   place_id,
        "place_type": place_type,
        "latitude":   lat,
        "longitude":  lng,
    }


def _find_nearby_place(db, lat: float, lng: float, radius_m: float) -> Optional[object]:
    """Place 테이블에서 반경 내 가장 가까운 장소 반환 (바운딩박스 → Haversine)"""
    from app.models.db_models import Place

    # 위경도 1도 ≈ 111km → 바운딩박스로 후보 필터
    delta_deg = radius_m / 111_000
    candidates = (
        db.query(Place)
        .filter(
            Place.latitude.between(lat - delta_deg, lat + delta_deg),
            Place.longitude.between(lng - delta_deg, lng + delta_deg),
        )
        .all()
    )

    closest, min_dist = None, float("inf")
    for p in candidates:
        d = _haversine_m(lat, lng, p.latitude, p.longitude)
        if d <= radius_m and d < min_dist:
            closest, min_dist = p, d

    return closest


def _place_to_result(place) -> Dict:
    return {
        "country":     place.country,
        "city":        place.city,
        "region":      place.region,
        "address":     place.address,
        "landmark":    place.name,
        "place_id":    place.google_place_id,
        "place_type":  place.place_type,
        "latitude":    place.latitude,
        "longitude":   place.longitude,
        "place_db_id": place.id,
    }


def _default_result(lat: float, lng: float) -> Dict:
    return {
        "country": None, "city": None, "region": None,
        "address": None, "landmark": None,
        "place_id": None, "place_type": None,
        "latitude": lat, "longitude": lng,
        "place_db_id": None,
    }


async def reverse_geocode(lat: float, lng: float, db) -> Dict:
    """
    위경도 → 위치 정보 반환.
    1) Place DB 반경 검색 (캐시 히트 시 API 호출 없음)
    2) Google Maps Geocoding API 호출 → Place 저장
    """
    radius_m = system_config_service.get_int("place_match_radius_m", 20, db)

    # 1. Place DB 캐시 조회
    cached = _find_nearby_place(db, lat, lng, radius_m)
    if cached:
        logger.debug(f"Place DB 캐시 히트: {cached.name} (id={cached.id})")
        cached.visit_count = (cached.visit_count or 0) + 1
        db.commit()
        return _place_to_result(cached)

    # 2. Google Maps API 호출
    if not GOOGLE_MAPS_API_KEY:
        logger.warning("GOOGLE_MAPS_API_KEY 미설정 — 역지오코딩 불가")
        return _default_result(lat, lng)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                _GEOCODE_URL,
                params={"latlng": f"{lat},{lng}", "key": GOOGLE_MAPS_API_KEY, "language": "ko"},
            )
        data = resp.json()
        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            logger.error(f"Google Maps API 오류: {data.get('status')} — {data.get('error_message')}")
            return _default_result(lat, lng)

        parsed = _parse_google_response(data, lat, lng)
        if not parsed:
            return _default_result(lat, lng)

    except Exception as e:
        logger.error(f"Google Maps API 호출 실패: {e}")
        return _default_result(lat, lng)

    # 3. Place 테이블 저장 (google_place_id 중복 체크)
    from app.models.db_models import Place

    place = None
    if parsed["place_id"]:
        place = db.query(Place).filter(Place.google_place_id == parsed["place_id"]).first()

    if place:
        place.visit_count = (place.visit_count or 0) + 1
    else:
        place = Place(
            google_place_id=parsed["place_id"],
            name=parsed["landmark"] or "알 수 없는 장소",
            place_type=parsed["place_type"],
            address=parsed["address"],
            latitude=lat,
            longitude=lng,
            country=parsed["country"],
            city=parsed["city"],
            region=parsed["region"],
            visit_count=1,
        )
        db.add(place)

    db.flush()
    parsed["place_db_id"] = place.id
    db.commit()

    logger.info(f"Place 저장: {place.name} (place_id={parsed['place_id']})")
    return parsed


# 동기 래퍼 — 기존 코드 호환용 (클러스터 없는 단순 조회)
def reverse_geocode_sync(lat: float, lng: float) -> Dict:
    """DB 없이 Google Maps API만 호출 (Place 저장 없음). 레거시 용도."""
    import asyncio
    import httpx

    if not GOOGLE_MAPS_API_KEY:
        return _default_result(lat, lng)
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                _GEOCODE_URL,
                params={"latlng": f"{lat},{lng}", "key": GOOGLE_MAPS_API_KEY, "language": "ko"},
            )
        data = resp.json()
        parsed = _parse_google_response(data, lat, lng)
        return parsed or _default_result(lat, lng)
    except Exception as e:
        logger.error(f"reverse_geocode_sync 실패: {e}")
        return _default_result(lat, lng)


# 싱글톤 호환 (기존 import: from app.services.reverse_geocoder import geocoder_service)
class _GeocoderCompat:
    """기존 코드가 geocoder_service.xxx() 형태로 호출하는 경우 대응"""
    async def reverse_geocode(self, latitude: float, longitude: float, db=None) -> Dict:
        if db:
            return await reverse_geocode(latitude, longitude, db)
        return reverse_geocode_sync(latitude, longitude)

    async def get_location_categories(self, latitude: float, longitude: float) -> Dict:
        result = reverse_geocode_sync(latitude, longitude)
        return {
            "country": {"name": result.get("country"), "type": "country"},
            "city":    {"name": result.get("city"),    "type": "city"},
            "region":  {"name": result.get("region"),  "type": "region"},
        }


geocoder_service = _GeocoderCompat()
