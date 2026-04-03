"""
사진 필터링 파이프라인 서비스

7단계 파이프라인:
1. 중복 제거 (파일 해시 비교)
2. 연사/버스트 그룹화
3. GPS 없는 사진 분리
4. 같은 장소 그룹화
5. AI 품질 분석 (선택)
6. 쓰레기 데이터 구분
7. 데이터 활용 내역 표기
"""

import hashlib
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

# ── 데이터 클래스 ──

@dataclass
class PhotoItem:
    """파이프라인에서 처리할 사진 단위"""
    id: str
    file_name: str
    file_size: int
    file_hash: Optional[str] = None
    gps: Optional[Dict[str, float]] = None  # {lat, lng, alt?}
    taken_at: Optional[datetime] = None
    content_type: str = "image/jpeg"

    # 파이프라인 결과
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    burst_group_id: Optional[int] = None
    is_burst_representative: bool = False
    has_gps: bool = False
    place_group_id: Optional[int] = None
    is_place_representative: bool = False
    is_trash: bool = False
    trash_reason: Optional[str] = None
    trash_code: Optional[str] = None
    usage: List[str] = field(default_factory=list)


@dataclass
class PlaceGroup:
    """같은 장소 그룹"""
    group_id: int
    center_lat: float
    center_lng: float
    photos: List[PhotoItem] = field(default_factory=list)
    representative_id: Optional[str] = None


@dataclass
class FilterResult:
    """전체 필터링 결과"""
    total_input: int = 0
    duplicates_removed: int = 0
    burst_groups: int = 0
    burst_selected: int = 0
    no_gps_count: int = 0
    place_groups: int = 0
    trash_removed: int = 0
    usable_photos: int = 0
    photos: List[Dict[str, Any]] = field(default_factory=list)
    place_group_details: List[Dict[str, Any]] = field(default_factory=list)


class PhotoFilterService:
    """사진 필터링 파이프라인"""

    BURST_TIME_THRESHOLD_SECONDS = 3  # 연사 판단 시간 차이
    BURST_DISTANCE_THRESHOLD_M = 50   # 연사 판단 거리 (미터)
    PLACE_RADIUS_M = 100              # 같은 장소 판단 반경 (미터)
    TRASH_TIME_DEVIATION_DAYS = 30    # 시간대 이상치 판단 기준 (일)

    def run_pipeline(
        self,
        photos: List[Dict[str, Any]],
        enable_ai_quality: bool = False,
    ) -> FilterResult:
        """
        전체 파이프라인 실행

        Args:
            photos: 사진 데이터 리스트 (id, file_name, file_size, file_hash, gps, taken_at)
            enable_ai_quality: AI 품질 분석 활성화 여부
        """
        items = self._parse_input(photos)
        result = FilterResult(total_input=len(items))

        # 1단계: 중복 제거
        items = self._step1_remove_duplicates(items, result)

        # 2단계: 연사/버스트 그룹화
        items = self._step2_burst_grouping(items, result)

        # 3단계: GPS 없는 사진 분리
        self._step3_separate_no_gps(items, result)

        # 4단계: 같은 장소 그룹화
        place_groups = self._step4_place_grouping(items, result)

        # 5단계: AI 품질 분석 (선택)
        if enable_ai_quality:
            self._step5_ai_quality(items)

        # 6단계: 쓰레기 데이터 구분
        self._step6_trash_detection(items, result)

        # 7단계: 데이터 활용 내역 표기
        self._step7_usage_report(items)

        # 결과 집계
        result.usable_photos = sum(
            1 for p in items
            if not p.is_duplicate and not p.is_trash
            and (p.is_burst_representative or p.burst_group_id is None)
        )

        result.photos = [self._to_dict(p) for p in items]
        result.place_group_details = [
            {
                "group_id": pg.group_id,
                "center": {"lat": pg.center_lat, "lng": pg.center_lng},
                "photo_count": len(pg.photos),
                "representative_id": pg.representative_id,
            }
            for pg in place_groups
        ]

        return result

    # ═══════════════════════════════════════════
    # 1단계: 중복 제거
    # ═══════════════════════════════════════════

    def _step1_remove_duplicates(self, items: List[PhotoItem], result: FilterResult) -> List[PhotoItem]:
        """파일 해시(MD5) 비교로 완전 동일 파일 제거"""
        seen_hashes: Dict[str, str] = {}  # hash -> first photo id

        for item in items:
            if not item.file_hash:
                # 해시가 없으면 파일명+크기로 대체 비교
                fallback_key = f"{item.file_size}_{item.file_name}"
                if fallback_key in seen_hashes:
                    item.is_duplicate = True
                    item.duplicate_of = seen_hashes[fallback_key]
                    result.duplicates_removed += 1
                else:
                    seen_hashes[fallback_key] = item.id
            else:
                if item.file_hash in seen_hashes:
                    item.is_duplicate = True
                    item.duplicate_of = seen_hashes[item.file_hash]
                    result.duplicates_removed += 1
                else:
                    seen_hashes[item.file_hash] = item.id

        return items

    # ═══════════════════════════════════════════
    # 2단계: 연사/버스트 그룹화
    # ═══════════════════════════════════════════

    def _step2_burst_grouping(self, items: List[PhotoItem], result: FilterResult) -> List[PhotoItem]:
        """촬영 시간 차이 < N초 + 같은 GPS → 연사로 판단"""
        active = [p for p in items if not p.is_duplicate and p.taken_at]
        active.sort(key=lambda p: p.taken_at)

        group_id = 0
        i = 0
        while i < len(active):
            group = [active[i]]
            j = i + 1
            while j < len(active):
                time_diff = (active[j].taken_at - active[j - 1].taken_at).total_seconds()
                same_location = True
                if active[j].gps and active[j - 1].gps:
                    dist = self._haversine(
                        active[j - 1].gps["lat"], active[j - 1].gps["lng"],
                        active[j].gps["lat"], active[j].gps["lng"],
                    )
                    same_location = dist < self.BURST_DISTANCE_THRESHOLD_M

                if time_diff <= self.BURST_TIME_THRESHOLD_SECONDS and same_location:
                    group.append(active[j])
                    j += 1
                else:
                    break

            if len(group) > 1:
                group_id += 1
                result.burst_groups += 1
                # 대표 사진 선택: 파일 크기가 가장 큰 사진 (가장 고해상도일 가능성)
                representative = max(group, key=lambda p: p.file_size)
                for p in group:
                    p.burst_group_id = group_id
                    p.is_burst_representative = (p.id == representative.id)
                result.burst_selected += 1

            i = j

        return items

    # ═══════════════════════════════════════════
    # 3단계: GPS 없는 사진 분리
    # ═══════════════════════════════════════════

    def _step3_separate_no_gps(self, items: List[PhotoItem], result: FilterResult):
        """GPS 데이터 없는 사진 표시"""
        for item in items:
            if item.is_duplicate:
                continue
            item.has_gps = item.gps is not None and "lat" in (item.gps or {}) and "lng" in (item.gps or {})
            if not item.has_gps:
                result.no_gps_count += 1

    # ═══════════════════════════════════════════
    # 4단계: 같은 장소 그룹화
    # ═══════════════════════════════════════════

    def _step4_place_grouping(self, items: List[PhotoItem], result: FilterResult) -> List[PlaceGroup]:
        """GPS 좌표 반경 내 + 시간 근접 → 같은 장소로 그룹화"""
        gps_photos = [
            p for p in items
            if not p.is_duplicate and p.has_gps and p.gps
        ]

        place_groups: List[PlaceGroup] = []
        assigned = set()

        for p in gps_photos:
            if p.id in assigned:
                continue

            # 새 그룹 시작
            group_id = len(place_groups) + 1
            group = PlaceGroup(
                group_id=group_id,
                center_lat=p.gps["lat"],
                center_lng=p.gps["lng"],
            )
            group.photos.append(p)
            assigned.add(p.id)
            p.place_group_id = group_id

            # 근처 사진 찾기
            for q in gps_photos:
                if q.id in assigned:
                    continue
                dist = self._haversine(
                    group.center_lat, group.center_lng,
                    q.gps["lat"], q.gps["lng"],
                )
                if dist <= self.PLACE_RADIUS_M:
                    group.photos.append(q)
                    assigned.add(q.id)
                    q.place_group_id = group_id
                    # 중심 재계산
                    lats = [ph.gps["lat"] for ph in group.photos]
                    lngs = [ph.gps["lng"] for ph in group.photos]
                    group.center_lat = sum(lats) / len(lats)
                    group.center_lng = sum(lngs) / len(lngs)

            # 대표 사진 선택
            representative = max(group.photos, key=lambda ph: ph.file_size)
            representative.is_place_representative = True
            group.representative_id = representative.id

            place_groups.append(group)

        result.place_groups = len(place_groups)
        return place_groups

    # ═══════════════════════════════════════════
    # 5단계: AI 품질 분석 (선택)
    # ═══════════════════════════════════════════

    def _step5_ai_quality(self, items: List[PhotoItem]):
        """
        AI 기반 품질 분석 (향후 구현)
        - 흐린 사진 감지
        - 구도/품질 점수
        - 사진 내용 태깅
        """
        # TODO: LLM 또는 Vision API 연동
        pass

    # ═══════════════════════════════════════════
    # 6단계: 쓰레기 데이터 구분
    # ═══════════════════════════════════════════

    def _step6_trash_detection(self, items: List[PhotoItem], result: FilterResult):
        """다른 사진과 관계없는 사진 / 시간대가 맞지 않는 사진 구분"""
        active = [p for p in items if not p.is_duplicate and p.taken_at]

        if len(active) < 3:
            return

        # 촬영 시간 기반 이상치 감지
        timestamps = sorted([p.taken_at for p in active])
        median_time = timestamps[len(timestamps) // 2]

        for p in active:
            if p.taken_at:
                deviation = abs((p.taken_at - median_time).days)
                if deviation > self.TRASH_TIME_DEVIATION_DAYS:
                    p.is_trash = True
                    p.trash_reason = f"시간대가 맞지 않음 (중앙값과 {deviation}일 차이)"
                    p.trash_code = "0002"
                    result.trash_removed += 1

        # GPS 기반 이상치: 다른 모든 사진과 1000km 이상 떨어진 사진
        gps_active = [p for p in items if not p.is_duplicate and not p.is_trash and p.has_gps and p.gps]
        if len(gps_active) >= 3:
            for p in gps_active:
                distances = []
                for q in gps_active:
                    if p.id == q.id:
                        continue
                    d = self._haversine(p.gps["lat"], p.gps["lng"], q.gps["lat"], q.gps["lng"])
                    distances.append(d)
                if distances:
                    min_dist = min(distances)
                    if min_dist > 1_000_000:  # 1000km
                        p.is_trash = True
                        p.trash_reason = f"다른 사진과 거리가 너무 멀음 ({min_dist / 1000:.0f}km)"
                        p.trash_code = "0001"
                        result.trash_removed += 1

    # ═══════════════════════════════════════════
    # 7단계: 데이터 활용 내역 표기
    # ═══════════════════════════════════════════

    def _step7_usage_report(self, items: List[PhotoItem]):
        """각 사진의 활용 내역 표기"""
        for p in items:
            if p.is_duplicate:
                p.usage = ["활용하지 않음 (중복 파일)"]
                continue
            if p.is_trash:
                if p.trash_code == "0001":
                    p.usage = [f"활용하지 않음 (내용과 관계 없음 code: 0001/gps)"]
                elif p.trash_code == "0002":
                    p.usage = [f"활용하지 않음 (시간대가 맞지 않음 code: 0002/time)"]
                else:
                    p.usage = [f"활용하지 않음 ({p.trash_reason})"]
                continue

            usages = []
            if p.has_gps:
                usages.append("GPS 경로에 활용됨")
            if p.is_place_representative:
                usages.append("장소 대표 사진으로 게시글에 활용됨")
            elif p.place_group_id:
                usages.append("장소 앨범에 포함됨")
            if p.burst_group_id and not p.is_burst_representative:
                usages.append("연사 그룹에서 대표 사진이 아님 (보관)")
            if p.is_burst_representative:
                usages.append("연사 그룹 대표 사진")
            if not usages:
                usages.append("일반 사진으로 보관됨")

            p.usage = usages

    # ═══════════════════════════════════════════
    # 유틸리티
    # ═══════════════════════════════════════════

    @staticmethod
    def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """두 GPS 좌표 사이 거리 (미터)"""
        R = 6371000  # 지구 반지름 (미터)
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lng2 - lng1)

        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    @staticmethod
    def compute_file_hash(file_bytes: bytes) -> str:
        """파일 MD5 해시 계산"""
        return hashlib.md5(file_bytes).hexdigest()

    def _parse_input(self, photos: List[Dict[str, Any]]) -> List[PhotoItem]:
        """입력 데이터를 PhotoItem 리스트로 변환"""
        items = []
        for p in photos:
            taken_at = None
            if p.get("taken_at"):
                try:
                    if isinstance(p["taken_at"], str):
                        taken_at = datetime.fromisoformat(p["taken_at"].replace("Z", "+00:00"))
                    elif isinstance(p["taken_at"], datetime):
                        taken_at = p["taken_at"]
                except (ValueError, TypeError):
                    pass

            gps = p.get("gps")
            if gps and isinstance(gps, dict) and "lat" in gps and "lng" in gps:
                gps = {"lat": float(gps["lat"]), "lng": float(gps["lng"])}
            else:
                gps = None

            items.append(PhotoItem(
                id=str(p.get("id", "")),
                file_name=p.get("file_name", ""),
                file_size=p.get("file_size", 0),
                file_hash=p.get("file_hash"),
                gps=gps,
                taken_at=taken_at,
                content_type=p.get("content_type", "image/jpeg"),
            ))
        return items

    @staticmethod
    def _to_dict(p: PhotoItem) -> Dict[str, Any]:
        return {
            "id": p.id,
            "file_name": p.file_name,
            "file_size": p.file_size,
            "is_duplicate": p.is_duplicate,
            "duplicate_of": p.duplicate_of,
            "burst_group_id": p.burst_group_id,
            "is_burst_representative": p.is_burst_representative,
            "has_gps": p.has_gps,
            "place_group_id": p.place_group_id,
            "is_place_representative": p.is_place_representative,
            "is_trash": p.is_trash,
            "trash_reason": p.trash_reason,
            "trash_code": p.trash_code,
            "usage": p.usage,
            "gps": p.gps,
            "taken_at": p.taken_at.isoformat() if p.taken_at else None,
        }
