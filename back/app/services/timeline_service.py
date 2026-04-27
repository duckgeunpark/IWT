"""
타임라인 서비스 — LLM 없이 EXIF 시간 + GPS로 이동 정보 계산

계산 항목:
  - stay_min              : 클러스터 내 머문 시간 (분)
  - travel_from_prev_min  : 이전 클러스터에서 이동 시간 (분)
  - distance_from_prev_km : 이전 클러스터와의 직선 거리 (km)
  - transport             : 이동 수단 추정
  - pin_number            : 일차 내 시간순 번호 (①②③...)
  - is_skip               : 본문 블록 생성 제외 여부
"""

import math
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── 거리 계산 ─────────────────────────────────────────────────────────

def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 GPS 좌표 간 Haversine 거리 (km)"""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── 이동 수단 추정 ────────────────────────────────────────────────────

def estimate_transport(travel_min: Optional[int], distance_km: Optional[float]) -> Optional[str]:
    """이동 시간 + 거리로 이동 수단 추정 (LLM 없음)"""
    if travel_min is None:
        return None
    if distance_km and distance_km > 20:
        return "장거리"
    if travel_min < 15:
        return "도보"
    if travel_min < 45:
        return "버스/지하철"
    return "택시/차량"


# ── skip 판단 ─────────────────────────────────────────────────────────

def is_skip_cluster(cluster: Any, stay_min: Optional[int]) -> bool:
    """
    본문 블록 생성을 건너뛸 클러스터 판단 (LLM 없음).

    skip 기준:
      - 사진 1장 이하
      - 이동 중 찍힌 장거리 클러스터 (stay_min < 5)
      - 3분 미만 체류
    """
    if getattr(cluster, 'photo_count', 0) <= 1:
        return True
    if stay_min is not None and stay_min < 3:
        return True
    return False


# ── 메인 함수 ─────────────────────────────────────────────────────────

def build_day_timeline(clusters: List[Any]) -> List[Dict[str, Any]]:
    """
    같은 날짜의 클러스터 목록을 받아 타임라인 데이터를 반환.

    Args:
        clusters: 시간순 정렬된 같은 날짜 Cluster 인스턴스 목록

    Returns:
        [
          {
            "cluster": Cluster,
            "pin_number": int,        # 1부터 시작
            "stay_min": int | None,
            "travel_from_prev_min": int | None,
            "distance_from_prev_km": float | None,
            "transport": str | None,
            "is_skip": bool,
            "arrival_str": str,       # "09:30" 형식
            "stay_str": str,          # "1시간 30분" 형식
          },
          ...
        ]
    """
    result = []

    for i, cluster in enumerate(clusters):
        # 머문 시간
        stay_min = None
        if cluster.time_start and cluster.time_end:
            delta = cluster.time_end - cluster.time_start
            stay_min = max(0, int(delta.total_seconds() / 60))

        # 이동 시간 + 거리
        travel_min = None
        distance_km = None
        transport = None
        if i > 0:
            prev = clusters[i - 1]
            if prev.time_end and cluster.time_start:
                delta = cluster.time_start - prev.time_end
                travel_min = max(0, int(delta.total_seconds() / 60))
            if (prev.centroid_lat and prev.centroid_lng
                    and cluster.centroid_lat and cluster.centroid_lng):
                distance_km = round(haversine_km(
                    prev.centroid_lat, prev.centroid_lng,
                    cluster.centroid_lat, cluster.centroid_lng,
                ), 1)
            transport = estimate_transport(travel_min, distance_km)

        skip = is_skip_cluster(cluster, stay_min)

        # 도착 시간 문자열
        arrival_str = ""
        if cluster.time_start:
            arrival_str = cluster.time_start.strftime("%H:%M")

        # 머문 시간 문자열
        stay_str = ""
        if stay_min is not None and stay_min > 0:
            if stay_min >= 60:
                h, m = divmod(stay_min, 60)
                stay_str = f"{h}시간 {m}분" if m else f"{h}시간"
            else:
                stay_str = f"{stay_min}분"

        result.append({
            "cluster":               cluster,
            "pin_number":            i + 1,
            "stay_min":              stay_min,
            "travel_from_prev_min":  travel_min,
            "distance_from_prev_km": distance_km,
            "transport":             transport,
            "is_skip":               skip,
            "arrival_str":           arrival_str,
            "stay_str":              stay_str,
        })

    return result


def group_clusters_by_day(clusters: List[Any]) -> Dict[int, List[Any]]:
    """
    클러스터 목록을 일차별로 그룹핑 (cluster.cluster_order 필드의 day 정보 활용).
    cluster에 day 필드가 없으면 time_start 날짜 기준으로 추정.
    """
    day_map: Dict[int, List[Any]] = {}

    # 날짜 → day 번호 매핑
    date_to_day: Dict[str, int] = {}
    for c in sorted(clusters, key=lambda x: x.time_start or datetime.min):
        if c.time_start:
            date_str = c.time_start.strftime("%Y-%m-%d")
            if date_str not in date_to_day:
                date_to_day[date_str] = len(date_to_day) + 1
            day = date_to_day[date_str]
        else:
            day = 1
        day_map.setdefault(day, []).append(c)

    # 각 일차 내부를 시간순 정렬
    for day in day_map:
        day_map[day].sort(key=lambda c: c.time_start or datetime.min)

    return day_map


def build_timeline(clusters: List[Any]) -> Dict[str, Any]:
    """
    전체 클러스터 목록으로 일차별 타임라인을 구성.

    Returns:
        {
          "days": {
            1: [timeline_item, ...],
            2: [timeline_item, ...],
          },
          "total_days": int,
          "total_places": int,   # skip 제외
        }
    """
    day_map = group_clusters_by_day(clusters)
    days_timeline: Dict[int, List[Dict]] = {}
    total_places = 0

    for day, day_clusters in sorted(day_map.items()):
        items = build_day_timeline(day_clusters)
        days_timeline[day] = items
        total_places += sum(1 for item in items if not item["is_skip"])

    return {
        "days": days_timeline,
        "total_days": len(day_map),
        "total_places": total_places,
    }


def format_transport_label(item: Dict[str, Any]) -> str:
    """타임라인 아이템의 이동 정보를 표시 문자열로 변환"""
    if not item.get("transport"):
        return ""
    parts = [item["transport"]]
    if item.get("travel_from_prev_min"):
        parts.append(f"{item['travel_from_prev_min']}분")
    if item.get("distance_from_prev_km") and item["distance_from_prev_km"] > 0:
        parts.append(f"{item['distance_from_prev_km']}km")
    return " ".join(parts)
