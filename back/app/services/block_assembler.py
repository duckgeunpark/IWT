"""
클러스터 stable hash 헬퍼.

GPS 격자 + 날짜 기반으로 클러스터의 안정적 식별자를 생성.
사진 추가/삭제 시에도 같은 위치+날짜 클러스터는 동일 hash를 가져 cache hit 판정에 사용.
"""

import hashlib
from typing import Optional


def compute_cluster_hash(
    centroid_lat: Optional[float],
    centroid_lng: Optional[float],
    date_str: Optional[str],
) -> str:
    """
    GPS 격자(0.001도 ≈ 100m) + 날짜 문자열(YYYY-MM-DD) → 20자 stable hash.
    GPS 없으면 날짜만 사용.
    """
    if centroid_lat is not None and centroid_lng is not None:
        lat_grid = round(centroid_lat, 3)
        lng_grid = round(centroid_lng, 3)
        raw = f"{lat_grid:.3f}_{lng_grid:.3f}_{date_str or 'unknown'}"
    else:
        raw = f"nogps_{date_str or 'unknown'}"
    return hashlib.md5(raw.encode()).hexdigest()[:20]
