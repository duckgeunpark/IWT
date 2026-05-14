"""
타임존 감지 + naive ↔ UTC 변환 서비스.

규칙:
  - 게시글 1개 = 1개 타임존 (IANA name, 예: "Asia/Bangkok")
  - 사진의 EXIF DateTimeOriginal 은 naive local 문자열 ("2024-03-15 20:00:00")
  - 이를 게시글 타임존 기준으로 해석해 UTC datetime + naive local ISO 문자열 둘 다 저장

감지 우선순위:
  1. EXIF OffsetTimeOriginal 태그 (예: "+07:00") → 해당 offset 의 가장 가까운 IANA tz
  2. GPS 좌표 → timezonefinder
  3. fallback: "Asia/Seoul"
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "Asia/Seoul"

# timezonefinder 는 첫 import 시 ~5MB 데이터를 메모리에 올림 → 싱글톤
_tf = None


def _get_tf():
    global _tf
    if _tf is None:
        from timezonefinder import TimezoneFinder
        _tf = TimezoneFinder()
    return _tf


def detect_timezone_from_gps(lat: Optional[float], lng: Optional[float]) -> Optional[str]:
    """GPS 좌표 → IANA tz name. 실패 시 None."""
    if lat is None or lng is None:
        return None
    try:
        tf = _get_tf()
        tz = tf.timezone_at(lat=float(lat), lng=float(lng))
        return tz  # "Asia/Bangkok" 같은 형태 또는 None
    except Exception as e:
        logger.warning(f"GPS→tz 변환 실패 (lat={lat}, lng={lng}): {e}")
        return None


def parse_exif_offset(offset_str: Optional[str]) -> Optional[int]:
    """
    EXIF OffsetTimeOriginal ("+07:00", "-05:30") → 분 단위 offset.
    실패 시 None.
    """
    if not offset_str:
        return None
    m = re.match(r"^\s*([+-])(\d{1,2}):?(\d{2})\s*$", offset_str.strip())
    if not m:
        return None
    sign = 1 if m.group(1) == "+" else -1
    hours = int(m.group(2))
    minutes = int(m.group(3))
    return sign * (hours * 60 + minutes)


def is_valid_iana_tz(tz_name: Optional[str]) -> bool:
    if not tz_name:
        return False
    try:
        ZoneInfo(tz_name)
        return True
    except ZoneInfoNotFoundError:
        return False
    except Exception:
        return False


def parse_naive_datetime(s: Optional[str]) -> Optional[datetime]:
    """
    EXIF / ISO 다양한 포맷을 naive datetime 으로 파싱.
    실패 시 None.

    지원 포맷:
      - "2024:03:15 20:00:00"  (EXIF 원본)
      - "2024-03-15T20:00:00"
      - "2024-03-15 20:00:00"
      - "2024-03-15T20:00:00Z" / "...+09:00"  (tz 정보 무시하고 naive 로)
    """
    if not s:
        return None
    raw = s.strip()
    # 시작 시각 부분만 잘라 사용 (마이크로초·tz suffix 제거)
    # EXIF 콜론 구분자를 ISO 식으로 변환
    if raw[:10].count(":") == 2:
        raw = raw[:4] + "-" + raw[5:7] + "-" + raw[8:10] + raw[10:]
    raw = raw.replace("T", " ")
    # tz suffix 제거 — naive 가 목적
    raw = re.sub(r"(Z|[+-]\d{2}:?\d{2})$", "", raw).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw[:len(fmt) + 4 if "%f" in fmt else len(fmt)], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def local_to_utc(naive_local: datetime, tz_name: str) -> Optional[datetime]:
    """naive local datetime + IANA tz → UTC datetime (tz-aware)."""
    if not is_valid_iana_tz(tz_name):
        return None
    try:
        aware = naive_local.replace(tzinfo=ZoneInfo(tz_name))
        return aware.astimezone(timezone.utc)
    except Exception as e:
        logger.warning(f"local→utc 변환 실패: {e}")
        return None


def utc_to_local_str(utc_dt: datetime, tz_name: str) -> Optional[str]:
    """UTC datetime + IANA tz → naive local ISO 문자열 ('2024-03-15T20:00:00')."""
    if not is_valid_iana_tz(tz_name):
        return None
    try:
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=timezone.utc)
        local = utc_dt.astimezone(ZoneInfo(tz_name))
        return local.replace(tzinfo=None).isoformat(timespec="seconds")
    except Exception as e:
        logger.warning(f"utc→local 변환 실패: {e}")
        return None


def compute_taken_times(
    raw_datetime: Optional[str],
    tz_name: str,
) -> Tuple[Optional[datetime], Optional[str]]:
    """
    raw EXIF datetime 문자열 + 게시글 타임존 → (UTC datetime, local ISO str).
    실패 시 (None, None).
    """
    naive = parse_naive_datetime(raw_datetime)
    if naive is None:
        return None, None
    if not is_valid_iana_tz(tz_name):
        tz_name = DEFAULT_TIMEZONE
    utc_dt = local_to_utc(naive, tz_name)
    if utc_dt is None:
        return None, None
    return utc_dt, naive.isoformat(timespec="seconds")


def resolve_post_timezone(
    user_choice: Optional[str],
    first_gps: Optional[Tuple[float, float]] = None,
    exif_offset_str: Optional[str] = None,
) -> str:
    """
    게시글 단위 타임존 결정.

    우선순위:
      1. user_choice (프론트가 명시적으로 보낸 IANA tz)
      2. exif_offset_str (첫 사진의 OffsetTimeOriginal) → offset 으로 ZoneInfo 찾기
      3. first_gps → timezonefinder
      4. fallback DEFAULT_TIMEZONE
    """
    if user_choice and is_valid_iana_tz(user_choice):
        return user_choice

    if first_gps is not None:
        lat, lng = first_gps
        tz = detect_timezone_from_gps(lat, lng)
        if tz:
            return tz

    # EXIF offset 으로 fallback (정밀도 떨어지지만 없는것보단 나음)
    if exif_offset_str:
        minutes = parse_exif_offset(exif_offset_str)
        if minutes is not None:
            # 자주 쓰는 offset → 대표 IANA name 매핑
            common = {
                540: "Asia/Seoul",
                480: "Asia/Shanghai",
                420: "Asia/Bangkok",
                360: "Asia/Dhaka",
                330: "Asia/Kolkata",
                60:  "Europe/Paris",
                0:   "Europe/London",
                -300: "America/New_York",
                -480: "America/Los_Angeles",
            }
            return common.get(minutes, DEFAULT_TIMEZONE)

    return DEFAULT_TIMEZONE
