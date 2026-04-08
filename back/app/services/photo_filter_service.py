"""
사진 필터링 파이프라인 서비스

7단계 파이프라인 (flat 리스트 처리):
1. 중복 제거 (파일 해시 비교)
2. 연사/버스트 그룹화
3. GPS 없는 사진 분리
4. 같은 장소 그룹화
5. AI 품질 분석 (선택)
6. 쓰레기 데이터 구분
7. 데이터 활용 내역 표기

+ clean_batch(): 2단계 묶음 정제 파이프라인 (GPS 이상치 + 시간 구간 분리)
"""

import hashlib
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import logging

# ── 묶음 정제 상수 ─────────────────────────────────────────────
MAX_SPEED_KMH = 900        # 허용 최대 이동 속도 (상업 항공기 기준, km/h)
BURST_SECS = 3             # 연사 판단 시간 차이 (초)
BURST_RADIUS_M = 50        # 연사 판단 GPS 반경 (미터)
SEGMENT_GAP_HOURS = 6      # 여행 구간 분리 간격 (시간)
OUTLIER_MAD_FACTOR = 3.0   # GPS 이상치 MAD 배수
MIN_YEAR = 2000            # 유효 최소 촬영 연도

# 활용 코드
_CODE_USED = "used"
_CODE_NO_GPS = "0001"
_CODE_TIME_MISMATCH = "0002"
_CODE_BURST = "0003"
_CODE_GPS_OUTLIER = "0004"
_CODE_NO_DATE = "0005"


def _median(values: List[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2

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

    # ═══════════════════════════════════════════
    # 묶음 정제 파이프라인 (2단계: GPS 이상치 + 구간 분리)
    # ═══════════════════════════════════════════

    def clean_batch(self, photos: List[Dict]) -> Dict:
        """
        2단계 묶음 정제 파이프라인 — post_route.py에서 사용

        처리 순서:
          1. 시간 파싱 + 정렬 / 날짜 없는 사진 분리
          2. GPS 있는 사진 / 없는 사진 분리
          3. 연사/중복 제거
          4. GPS 이상치 탐지 및 제거 (속도 기반 + MAD 기반)
          5. 시간 간격 기반 여행 구간 분리
          6. 시간대 불일치 구간 필터

        Returns:
            {
              "segments": [...],          # 활용 구간별 사진 목록
              "no_gps_photos": [...],     # GPS 없음 (경로 미사용)
              "removed": [...],           # 제거된 사진 목록
              "usage_report": [...],      # 사진별 활용 내역
              "summary": {...}            # 요약 통계
            }
        """
        if not photos:
            return self._empty_clean_result()

        removed: List[Dict] = []

        # 1. 시간 파싱 + 정렬
        dated_photos, no_date_photos = self._cb_parse_and_sort(photos)
        for p in no_date_photos:
            removed.append({"photo": p, "reason": "날짜 정보 없음", "code": _CODE_NO_DATE})

        # 2. GPS 분리
        gps_photos, no_gps_photos = self._cb_split_by_gps(dated_photos)

        # 3. 연사/중복 제거
        deduped, burst_removed = self._cb_remove_burst(gps_photos)
        for p in burst_removed:
            removed.append({"photo": p, "reason": "연사/중복 사진", "code": _CODE_BURST})

        # 4. GPS 이상치 제거
        clean_photos, gps_outliers = self._cb_detect_gps_outliers(deduped)
        for p in gps_outliers:
            removed.append({"photo": p, "reason": "GPS 이상치 (경로 이탈 좌표)", "code": _CODE_GPS_OUTLIER})

        # 5. 시간 간격 기반 구간 분리
        segments = self._cb_split_segments(clean_photos)

        # 6. 시간대 불일치 구간 필터
        segments, time_outliers = self._cb_filter_outlier_segments(segments)
        for p in time_outliers:
            removed.append({"photo": p, "reason": "시간대 불일치 구간", "code": _CODE_TIME_MISMATCH})

        usage_report = self._cb_build_usage_report(photos, removed, no_gps_photos)

        summary = {
            "total_input": len(photos),
            "total_usable": sum(len(s["photos"]) for s in segments),
            "total_removed": len(removed),
            "no_date": len(no_date_photos),
            "no_gps": len(no_gps_photos),
            "segment_count": len(segments),
        }

        logger.info(
            f"clean_batch 완료 | 입력 {summary['total_input']}장 → "
            f"활용 {summary['total_usable']}장 / 제거 {summary['total_removed']}장 / "
            f"GPS없음 {summary['no_gps']}장 / 구간 {summary['segment_count']}개"
        )

        return {
            "segments": segments,
            "no_gps_photos": no_gps_photos,
            "removed": removed,
            "usage_report": usage_report,
            "summary": summary,
        }

    def _cb_parse_and_sort(self, photos: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        dated, no_date = [], []
        for photo in photos:
            dt = self._cb_extract_datetime(photo)
            if dt:
                p = dict(photo)
                p["_dt"] = dt
                dated.append(p)
            else:
                no_date.append(photo)
        dated.sort(key=lambda x: x["_dt"])
        return dated, no_date

    def _cb_split_by_gps(self, photos: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        with_gps, without_gps = [], []
        for photo in photos:
            lat, lon = self._cb_extract_gps(photo)
            if lat is not None:
                p = dict(photo)
                p["_lat"], p["_lon"] = lat, lon
                with_gps.append(p)
            else:
                without_gps.append(photo)
        return with_gps, without_gps

    def _cb_remove_burst(self, photos: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        if len(photos) <= 1:
            return list(photos), []
        kept, removed = [], []
        i = 0
        while i < len(photos):
            group = [photos[i]]
            j = i + 1
            while j < len(photos):
                secs = (photos[j]["_dt"] - photos[i]["_dt"]).total_seconds()
                if secs > BURST_SECS:
                    break
                dist = self._haversine(
                    photos[i]["_lat"], photos[i]["_lon"],
                    photos[j]["_lat"], photos[j]["_lon"],
                )
                if dist <= BURST_RADIUS_M:
                    group.append(photos[j])
                    j += 1
                else:
                    break
            rep = max(group, key=lambda p: p.get("file_size", 0))
            kept.append(rep)
            removed.extend(p for p in group if p is not rep)
            i = j
        return kept, removed

    def _cb_detect_gps_outliers(self, photos: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        if len(photos) <= 2:
            return list(photos), []
        outlier_idx: set = set()
        # 방법 A: 속도 기반
        for i in range(1, len(photos)):
            prev, curr = photos[i - 1], photos[i]
            dist_km = self._haversine(
                prev["_lat"], prev["_lon"], curr["_lat"], curr["_lon"]
            ) / 1000.0
            hours = (curr["_dt"] - prev["_dt"]).total_seconds() / 3600
            if hours > 0 and (dist_km / hours) > MAX_SPEED_KMH:
                outlier_idx.add(i)
        # 방법 B: MAD 기반
        lats = [p["_lat"] for p in photos]
        lons = [p["_lon"] for p in photos]
        med_lat = _median(lats)
        med_lon = _median(lons)
        dists = [self._haversine(p["_lat"], p["_lon"], med_lat, med_lon) / 1000.0 for p in photos]
        med_d = _median(dists)
        mad = _median([abs(d - med_d) for d in dists])
        threshold = med_d + OUTLIER_MAD_FACTOR * mad * 1.4826
        if threshold > 0:
            for i, d in enumerate(dists):
                if d > threshold:
                    outlier_idx.add(i)
        clean = [p for i, p in enumerate(photos) if i not in outlier_idx]
        outliers = [p for i, p in enumerate(photos) if i in outlier_idx]
        return clean, outliers

    def _cb_split_segments(self, photos: List[Dict]) -> List[Dict]:
        if not photos:
            return []
        segments, current = [], [photos[0]]
        for i in range(1, len(photos)):
            gap_h = (photos[i]["_dt"] - photos[i - 1]["_dt"]).total_seconds() / 3600
            if gap_h >= SEGMENT_GAP_HOURS:
                segments.append(self._cb_build_segment(current))
                current = [photos[i]]
            else:
                current.append(photos[i])
        if current:
            segments.append(self._cb_build_segment(current))
        return segments

    def _cb_filter_outlier_segments(self, segments: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        if len(segments) <= 1:
            return segments, []
        avg = sum(len(s["photos"]) for s in segments) / len(segments)
        threshold = max(2, avg * 0.1)
        kept, outlier_photos = [], []
        for seg in segments:
            if len(seg["photos"]) < threshold:
                outlier_photos.extend(seg["photos"])
            else:
                kept.append(seg)
        return (kept if kept else segments), outlier_photos

    def _cb_build_segment(self, photos: List[Dict]) -> Dict:
        times = [p["_dt"] for p in photos]
        lats = [p["_lat"] for p in photos]
        lons = [p["_lon"] for p in photos]
        return {
            "photos": photos,
            "start_time": min(times).isoformat(),
            "end_time": max(times).isoformat(),
            "duration_hours": round((max(times) - min(times)).total_seconds() / 3600, 2),
            "photo_count": len(photos),
            "center": {
                "lat": round(sum(lats) / len(lats), 6),
                "lon": round(sum(lons) / len(lons), 6),
            },
        }

    def _cb_build_usage_report(
        self, original: List[Dict], removed: List[Dict], no_gps: List[Dict]
    ) -> List[Dict]:
        removed_map: Dict[str, Dict] = {
            item["photo"].get("file_key", ""): item for item in removed
        }
        no_gps_keys = {p.get("file_key", "") for p in no_gps}
        report = []
        for i, photo in enumerate(original, start=1):
            fk = photo.get("file_key", "")
            if fk in removed_map:
                info = removed_map[fk]
                report.append({"index": i, "file_key": fk, "used": False, "code": info["code"], "reason": info["reason"]})
            elif fk in no_gps_keys:
                report.append({"index": i, "file_key": fk, "used": False, "code": _CODE_NO_GPS, "reason": "GPS 없음 (경로 미사용, 갤러리 포함 가능)"})
            else:
                report.append({"index": i, "file_key": fk, "used": True, "code": _CODE_USED, "reason": "GPS 및 게시글 경로에 활용됨"})
        return report

    def _cb_extract_datetime(self, photo: Dict) -> Optional[datetime]:
        try:
            exif = photo.get("exif_data") or {}
            raw = exif.get("datetime") or photo.get("datetime")
            if not raw:
                return None
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            now = datetime.now(tz=dt.tzinfo) if dt.tzinfo else datetime.now()
            if dt.year < MIN_YEAR or dt > now:
                return None
            return dt
        except Exception:
            return None

    def _cb_extract_gps(self, photo: Dict) -> Tuple[Optional[float], Optional[float]]:
        try:
            exif = photo.get("exif_data") or {}
            gps = exif.get("gps") or {}
            lat = gps.get("latitude") or photo.get("latitude")
            lon = gps.get("longitude") or photo.get("longitude")
            if lat is None or lon is None:
                return None, None
            lat, lon = float(lat), float(lon)
            if lat == 0.0 and lon == 0.0:
                return None, None
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return None, None
            return lat, lon
        except Exception:
            return None, None

    @staticmethod
    def _empty_clean_result() -> Dict:
        return {
            "segments": [],
            "no_gps_photos": [],
            "removed": [],
            "usage_report": [],
            "summary": {
                "total_input": 0,
                "total_usable": 0,
                "total_removed": 0,
                "no_date": 0,
                "no_gps": 0,
                "segment_count": 0,
            },
        }

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


# 싱글톤 인스턴스
photo_filter = PhotoFilterService()
