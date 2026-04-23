"""
GPS + 시간 기반 사진 위치 클러스터링 서비스
"""

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 GPS 좌표 간 거리(km) 계산 (Haversine 공식)"""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(dt_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        return None


def cluster_photos_by_location(
    photos: List[Dict[str, Any]],
    distance_km: float = 0.1,
    time_hours: float = 2.0,
) -> List[Dict[str, Any]]:
    """
    GPS + 시간 기준으로 사진을 위치 클러스터로 묶는다.

    같은 클러스터 조건 (둘 다 만족해야 함):
      - 직전 사진과 GPS 거리 < distance_km
      - 직전 사진과 촬영 시간 차이 < time_hours

    GPS 없는 사진은 시간만 비교해 인접 클러스터에 편입하거나 별도 클러스터로 분리.

    반환:
      [
        {
          "cluster_id": int,
          "photos": [photo, ...],
          "center_gps": {"lat": float, "lng": float} | None,
          "photo_count": int,
          "start_time": str | None,
          "end_time": str | None,
        },
        ...
      ]
    """
    if not photos:
        return []

    # 시간순 정렬 (taken_at 없는 사진은 뒤로)
    def sort_key(p):
        t = _parse_datetime(p.get("taken_at"))
        return t if t else datetime.max.replace(tzinfo=timezone.utc)

    sorted_photos = sorted(photos, key=sort_key)

    clusters: List[List[Dict]] = [[sorted_photos[0]]]

    for photo in sorted_photos[1:]:
        last = clusters[-1][-1]

        prev_gps = last.get("gps")
        curr_gps = photo.get("gps")

        # GPS 거리 비교
        if prev_gps and curr_gps:
            dist = haversine_distance(
                prev_gps["lat"], prev_gps["lng"],
                curr_gps["lat"], curr_gps["lng"],
            )
            close_enough = dist < distance_km
        else:
            close_enough = True  # GPS 없으면 거리 조건 통과

        # 시간 간격 비교
        t_prev = _parse_datetime(last.get("taken_at"))
        t_curr = _parse_datetime(photo.get("taken_at"))
        if t_prev and t_curr:
            gap_hours = abs((t_curr - t_prev).total_seconds()) / 3600
            recent_enough = gap_hours < time_hours
        else:
            recent_enough = True

        if close_enough and recent_enough:
            clusters[-1].append(photo)
        else:
            clusters.append([photo])

    result = []
    for i, cluster_photos in enumerate(clusters):
        gps_photos = [p for p in cluster_photos if p.get("gps")]

        center_gps = None
        if gps_photos:
            center_gps = {
                "lat": sum(p["gps"]["lat"] for p in gps_photos) / len(gps_photos),
                "lng": sum(p["gps"]["lng"] for p in gps_photos) / len(gps_photos),
            }

        times = [_parse_datetime(p.get("taken_at")) for p in cluster_photos]
        times = [t for t in times if t]

        result.append({
            "cluster_id": i,
            "photos": cluster_photos,
            "center_gps": center_gps,
            "photo_count": len(cluster_photos),
            "start_time": min(times).isoformat() if times else None,
            "end_time": max(times).isoformat() if times else None,
        })

    return result
