"""
일차 통합 LLM 호출 오케스트레이터.

Phase 1 최적화의 핵심:
  - 기존: PlaceNote(N) + place block(N) + title(1) + intro(1) + tags(1) + eval(1) → ~3N+3회
  - 변경: 일차별 통합 콜(D) + title/intro 통합(1) → D+1회 (장소 수와 무관)

장소 수가 한 일차에 8개를 넘으면 6개씩 청크 분할.
일차 fingerprint 기반 캐시로 변경 안 된 일차는 LLM 호출 생략.
출력 검증 실패 시 청크 단위 자동 재호출.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.output_parsers import StrOutputParser

from app.services.day_chunk_prompts import (
    CHUNK_MAX_PLACES,
    CHUNK_TARGET_PLACES,
    DAY_CHUNK_PROMPT,
    TITLE_INTRO_PROMPT,
)
from app.services.llm_factory import get_llm, register_reset_callback
from app.services.utils import parse_llm_json

logger = logging.getLogger(__name__)


# ── day_header 블록 (LLM 없음) ────────────────────────────────────────

def build_day_header_content(day: int, timeline_items: List[Dict]) -> str:
    """
    일차 헤더 블록의 ai_content — JSON 형식으로 저장.
    프론트엔드가 이 JSON을 파싱해 지도 핀 + 타임라인 UI를 렌더링.
    """
    pins = []
    for item in timeline_items:
        cluster = item["cluster"]
        pins.append({
            "pin_number":   item["pin_number"],
            "cluster_id":   cluster.id,
            "place_name":   cluster.location_name or "",
            "lat":          cluster.centroid_lat,
            "lng":          cluster.centroid_lng,
            "arrival_str":  item.get("arrival_str", ""),
            "stay_str":     item.get("stay_str", ""),
            "transport":    item.get("transport"),
            "travel_min":   item.get("travel_from_prev_min"),
            "distance_km":  item.get("distance_from_prev_km"),
            "is_skip":      item["is_skip"],
        })

    return json.dumps({
        "day": day,
        "pins": pins,
    }, ensure_ascii=False)


# ── LLM 체인 싱글톤 ──────────────────────────────────────────────────

_chain_chunk = None
_chain_title_intro = None


def _get_chunk_chain():
    global _chain_chunk
    if _chain_chunk is None:
        # 일차 통합 콜은 출력이 길 수 있으므로 max_tokens 충분히
        llm = get_llm(temperature=0.7, max_tokens=4096)
        _chain_chunk = DAY_CHUNK_PROMPT | llm | StrOutputParser()
    return _chain_chunk


def _get_title_intro_chain():
    global _chain_title_intro
    if _chain_title_intro is None:
        llm = get_llm(temperature=0.5, max_tokens=400)
        _chain_title_intro = TITLE_INTRO_PROMPT | llm | StrOutputParser()
    return _chain_title_intro


def _reset_chains():
    global _chain_chunk, _chain_title_intro
    _chain_chunk = None
    _chain_title_intro = None


register_reset_callback(_reset_chains)


# ── Fingerprint ───────────────────────────────────────────────────────

def _cluster_fingerprint(cluster: Any) -> str:
    """클러스터 사진 구성 → 12자리 MD5 (단일 클러스터 캐시 키)"""
    photos = getattr(cluster, "photos", []) or []
    file_keys = sorted(p.file_key for p in photos if getattr(p, "file_key", None))
    if not file_keys:
        file_keys = [str(getattr(cluster, "cluster_hash", None) or cluster.id)]
    return hashlib.md5("|".join(file_keys).encode()).hexdigest()[:12]


def _day_fingerprint(day_items: List[Dict[str, Any]]) -> str:
    """일차 내 모든 클러스터 fp의 정렬 결합 → 일차 캐시 키"""
    cluster_fps = sorted(
        _cluster_fingerprint(item["cluster"])
        for item in day_items
        if not item.get("is_skip")
    )
    if not cluster_fps:
        return ""
    return hashlib.md5("|".join(cluster_fps).encode()).hexdigest()[:12]


# ── 청크 분할 ─────────────────────────────────────────────────────────

def _split_chunks(items: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """
    일차 items(skip 제외)를 청크로 분할.
    8개 이하면 1청크, 초과하면 6개 단위로 시간 연속성 유지하며 분할.
    """
    if len(items) <= CHUNK_MAX_PLACES:
        return [items]

    chunks = []
    for i in range(0, len(items), CHUNK_TARGET_PLACES):
        chunks.append(items[i : i + CHUNK_TARGET_PLACES])
    return chunks


# ── 입력 빌드 ────────────────────────────────────────────────────────

def _format_transport_hint(item: Dict[str, Any]) -> str:
    """이동 컨텍스트를 본문 연결용 힌트 문자열로"""
    transport = item.get("transport")
    travel_min = item.get("travel_from_prev_min")
    if transport and travel_min:
        return f"{travel_min}분 {transport}로"
    if transport:
        return transport
    return "다음 장소로"


def _build_chunk_input(
    items: List[Dict[str, Any]],
    day_index: int,
    day_total: int,
    tone: str,
    style: str,
) -> Dict[str, Any]:
    """청크 items → 프롬프트 입력 dict"""
    places = []
    transport_hints = []
    for item in items:
        cluster = item["cluster"]
        place = {
            "order": item["pin_number"],
            "location_name": cluster.location_name or "알 수 없는 장소",
            "city": getattr(cluster, "city", "") or "",
            "country": getattr(cluster, "country", "") or "",
            "photo_count": getattr(cluster, "photo_count", 0),
            "stay_str": item.get("stay_str", "정보 없음") or "정보 없음",
            "arrival_str": item.get("arrival_str", "") or "",
        }
        if item.get("transport"):
            place["transport_from_prev"] = _format_transport_hint(item)
        places.append(place)
        transport_hints.append(_format_transport_hint(item))

    # 다음 장소가 있는 경우 본문 마지막에 어떤 표현으로 연결할지에 대한 예시 힌트
    transport_hint = transport_hints[1] if len(transport_hints) > 1 else "다음 장소로"

    return {
        "day_index": day_index,
        "day_total": day_total,
        "places_json": json.dumps(places, ensure_ascii=False, indent=2),
        "tone": tone,
        "style": style,
        "transport_hint": transport_hint,
    }


# ── 출력 검증 ────────────────────────────────────────────────────────

def _validate_chunk_output(
    parsed: Dict[str, Any],
    expected_orders: List[int],
) -> Tuple[bool, str]:
    """
    LLM 출력 JSON 검증.
    Returns: (ok, reason)
    """
    if not isinstance(parsed, dict):
        return False, "응답이 dict가 아님"

    places_out = parsed.get("places")
    if not isinstance(places_out, list) or len(places_out) != len(expected_orders):
        return False, f"places 수 불일치 ({len(places_out) if isinstance(places_out, list) else 0} vs {len(expected_orders)})"

    out_orders = [p.get("order") for p in places_out]
    if sorted(out_orders) != sorted(expected_orders):
        return False, f"order 불일치 (expected={expected_orders}, got={out_orders})"

    short_main = 0
    short_brief = 0
    for p in places_out:
        para = (p.get("paragraph") or "").strip()
        depth = p.get("depth") or "brief"
        if not para:
            return False, f"빈 paragraph (order={p.get('order')})"
        if depth == "main" and len(para) < 80:
            short_main += 1
        elif depth == "brief" and len(para) < 25:
            short_brief += 1

    # 절반 이상이 비정상적으로 짧으면 실패
    if short_main + short_brief > len(places_out) // 2:
        return False, f"너무 짧은 paragraph 다수 ({short_main}+{short_brief}/{len(places_out)})"

    return True, ""


# ── 청크 실행 (재시도 포함) ──────────────────────────────────────────

async def _run_chunk_with_retry(
    chunk_input: Dict[str, Any],
    expected_orders: List[int],
    max_retries: int = 2,
) -> Optional[Dict[str, Any]]:
    """청크 1개 LLM 호출 + 검증. 실패 시 재시도 후 None 반환."""
    chain = _get_chunk_chain()

    for attempt in range(max_retries + 1):
        try:
            raw = await chain.ainvoke(chunk_input)
            parsed = parse_llm_json(raw)
            ok, reason = _validate_chunk_output(parsed, expected_orders)
            if ok:
                return parsed
            logger.warning(f"청크 출력 검증 실패 (attempt={attempt}): {reason}")
        except Exception as e:
            logger.warning(f"청크 LLM 호출 실패 (attempt={attempt}): {e}")

        if attempt < max_retries:
            await asyncio.sleep(0.5 * (attempt + 1))  # 지수 백오프 흉내

    return None


# ── Fallback 본문 ────────────────────────────────────────────────────

def _fallback_place(item: Dict[str, Any]) -> Dict[str, Any]:
    cluster = item["cluster"]
    name = cluster.location_name or "알 수 없는 장소"
    stay = item.get("stay_str", "")
    photos = getattr(cluster, "photo_count", 0)
    parts = [f"{name}에서의 시간을 사진에 담았습니다."]
    if stay:
        parts.append(f"머문 시간 {stay}.")
    if photos:
        parts.append(f"사진 {photos}장을 남겼습니다.")
    return {
        "order": item["pin_number"],
        "category": "etc",
        "depth": "brief",
        "mood_keywords": [],
        "highlight_scene": "",
        "paragraph": " ".join(parts),
    }


# ── Title + Intro ────────────────────────────────────────────────────

async def _run_title_intro(
    total_days: int,
    main_places: List[str],
    trip_summary: str,
    tone: str,
    style: str,
) -> Tuple[str, str]:
    chain = _get_title_intro_chain()
    inputs = {
        "total_days": total_days,
        "main_places_str": ", ".join(main_places[:8]) + ("..." if len(main_places) > 8 else ""),
        "trip_summary": trip_summary,
        "tone": tone,
        "style": style,
    }
    try:
        raw = await chain.ainvoke(inputs)
        parsed = parse_llm_json(raw)
        title = (parsed.get("title") or "").strip() or "나의 여행 기록"
        intro = (parsed.get("intro") or "").strip() or "사진으로 기록한 소중한 여행입니다."
        return title, intro
    except Exception as e:
        logger.warning(f"title/intro 호출 실패: {e}")
        return "나의 여행 기록", "사진으로 기록한 소중한 여행입니다."


# ── 메인 엔트리 ──────────────────────────────────────────────────────

async def generate_blocks_day_chunked(
    timeline: Dict[str, Any],
    *,
    tone: str = "감성적",
    style: str = "개인 일기",
    cached_day_cache: Optional[Dict[str, Any]] = None,
    locked_blocks: Optional[Dict[int, Dict[str, Any]]] = None,
    locked_title: Optional[str] = None,
    locked_intro: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], str, List[str], Dict[str, Any], Dict[str, int]]:
    """
    타임라인 → 모든 블록 데이터 + title + tags + 새 day_cache + cache 통계 반환.

    Args:
        timeline: timeline_service.build_timeline() 결과
        tone, style: 작성 톤/스타일
        cached_day_cache: {str(day_idx): {"fp": str, "places": [...], "tag_candidates": [...]}}
                          (Post.day_cache JSON 디코딩 결과)
        locked_blocks: {cluster.id: {"ai_content": str, "depth": str, "quality_score": float}}
                       사용자가 잠근 place 블록은 LLM 결과로 덮지 않음
        locked_title: 지정 시 LLM 호출 없이 이 제목 사용 (재생성 시 제목 보존)
        locked_intro: 지정 시 LLM 호출 없이 이 도입부 사용

    Returns:
        (blocks_data, title, tags, new_day_cache, cache_stats)
        cache_stats = {"day_hit": N, "day_miss": M, "chunk_calls": K}
    """
    days = timeline["days"]
    cached_day_cache = cached_day_cache or {}
    locked_blocks = locked_blocks or {}

    # 1) 일차별로 캐시 hit/miss 판정
    new_day_cache: Dict[str, Any] = {}
    day_results: Dict[int, Dict[str, Any]] = {}        # {day: {"places": [...], "tag_candidates": [...]}}
    day_fp_map: Dict[int, str] = {}

    miss_jobs: List[Tuple[int, List[Dict[str, Any]]]] = []  # (day, chunk_items)
    day_hit_count = 0
    day_miss_count = 0

    for day, items in sorted(days.items()):
        active_items = [it for it in items if not it.get("is_skip")]
        if not active_items:
            day_results[day] = {"places": [], "tag_candidates": []}
            continue

        fp = _day_fingerprint(items)
        day_fp_map[day] = fp

        cached = cached_day_cache.get(str(day))
        if cached and cached.get("fp") == fp:
            # 일차 fp 일치 → 재사용
            day_results[day] = {
                "places": cached.get("places", []),
                "tag_candidates": cached.get("tag_candidates", []),
            }
            day_hit_count += 1
            continue

        # miss → 청크 분할 후 실행 큐에 추가
        chunks = _split_chunks(active_items)
        for chunk in chunks:
            miss_jobs.append((day, chunk))
        day_miss_count += 1

    # 2) miss 일차들 청크 단위 병렬 실행 (max_concurrency 5)
    day_total = timeline["total_days"]
    semaphore = asyncio.Semaphore(5)

    async def _exec_chunk(day: int, chunk: List[Dict[str, Any]]):
        async with semaphore:
            chunk_input = _build_chunk_input(chunk, day, day_total, tone, style)
            expected_orders = [it["pin_number"] for it in chunk]
            parsed = await _run_chunk_with_retry(chunk_input, expected_orders)
            if parsed is None:
                # 모든 재시도 실패 → fallback
                logger.error(f"day={day} 청크 실패 → fallback 적용 ({len(chunk)}곳)")
                return day, {
                    "places": [_fallback_place(it) for it in chunk],
                    "tag_candidates": [],
                }
            return day, parsed

    chunk_results = await asyncio.gather(
        *[_exec_chunk(day, chunk) for day, chunk in miss_jobs]
    )

    # 3) 청크 결과를 일차 단위로 합치기
    for day, parsed in chunk_results:
        slot = day_results.setdefault(day, {"places": [], "tag_candidates": []})
        slot["places"].extend(parsed.get("places", []))
        slot["tag_candidates"].extend(parsed.get("tag_candidates", []))

    # 일차 내 places는 order로 정렬
    for day, slot in day_results.items():
        slot["places"].sort(key=lambda p: p.get("order", 0))

    # 4) 새 day_cache 구성 (skip 제외 일차만 저장)
    for day, fp in day_fp_map.items():
        if day in day_results:
            new_day_cache[str(day)] = {
                "fp": fp,
                "places": day_results[day]["places"],
                "tag_candidates": day_results[day]["tag_candidates"],
            }

    # 5) Title + Intro (1콜)
    all_main_places: List[str] = []
    for day, items in sorted(days.items()):
        slot = day_results.get(day, {})
        place_meta = {p.get("order"): p for p in slot.get("places", [])}
        for item in items:
            if item.get("is_skip"):
                continue
            cluster = item["cluster"]
            name = cluster.location_name or "알 수 없는 장소"
            meta = place_meta.get(item["pin_number"])
            if meta and meta.get("depth") == "main":
                all_main_places.append(name)

    if not all_main_places:
        # depth=main이 없으면 모든 활성 장소명 사용
        for day, items in sorted(days.items()):
            for item in items:
                if not item.get("is_skip"):
                    all_main_places.append(item["cluster"].location_name or "알 수 없는 장소")

    if locked_title is not None and locked_intro is not None:
        # 재생성 시 제목/도입부 보존 → LLM 호출 생략
        title, intro = locked_title, locked_intro
    else:
        trip_summary = f"{len(all_main_places)}개 주요 장소 방문"
        title, intro = await _run_title_intro(day_total, all_main_places, trip_summary, tone, style)

    # 6) 블록 조립
    blocks: List[Dict[str, Any]] = []
    order = 0

    blocks.append({
        "block_type": "title", "block_order": order, "day": None,
        "cluster_id": None, "pin_number": None,
        "depth": "main", "ai_content": title,
        "stay_min": None, "travel_from_prev_min": None,
        "distance_from_prev_km": None, "transport": None,
    })
    order += 1

    blocks.append({
        "block_type": "intro", "block_order": order, "day": None,
        "cluster_id": None, "pin_number": None,
        "depth": "main", "ai_content": intro,
        "stay_min": None, "travel_from_prev_min": None,
        "distance_from_prev_km": None, "transport": None,
    })
    order += 1

    all_tag_candidates: List[str] = []

    for day, items in sorted(days.items()):
        # day_header (LLM 없음)
        blocks.append({
            "block_type": "day_header", "block_order": order, "day": day,
            "cluster_id": None, "pin_number": None,
            "depth": "main", "ai_content": build_day_header_content(day, items),
            "stay_min": None, "travel_from_prev_min": None,
            "distance_from_prev_km": None, "transport": None,
        })
        order += 1

        slot = day_results.get(day, {"places": [], "tag_candidates": []})
        all_tag_candidates.extend(slot.get("tag_candidates", []))
        place_meta = {p.get("order"): p for p in slot["places"]}

        for item in items:
            if item.get("is_skip"):
                continue
            cluster = item["cluster"]
            meta = place_meta.get(item["pin_number"])

            if meta:
                depth = meta.get("depth") or "brief"
                ai_content = (meta.get("paragraph") or "").strip()
                quality_score = 0.8  # 검증 통과 시 기본
            else:
                depth = "brief"
                fb = _fallback_place(item)
                ai_content = fb["paragraph"]
                quality_score = 0.3

            # 잠금 블록 보호: cluster.id로 매칭, 기존 ai_content/depth 유지
            lock_key = cluster.id
            if lock_key in locked_blocks:
                locked = locked_blocks[lock_key]
                ai_content = locked.get("ai_content", ai_content)
                depth = locked.get("depth", depth)
                quality_score = locked.get("quality_score", quality_score)

            blocks.append({
                "block_type": "place", "block_order": order, "day": day,
                "cluster_id": cluster.id, "pin_number": item["pin_number"],
                "depth": depth, "ai_content": ai_content,
                "stay_min": item.get("stay_min"),
                "travel_from_prev_min": item.get("travel_from_prev_min"),
                "distance_from_prev_km": item.get("distance_from_prev_km"),
                "transport": item.get("transport"),
                "quality_score": quality_score,
            })
            order += 1

    # 7) 태그 — 일차 콜에서 모은 후보 + 주요 장소명 첫 글자
    # 후보 중복 제거 후 상위 5개
    seen = set()
    tags: List[str] = []
    for t in all_tag_candidates:
        t = (t or "").strip().lstrip("#")
        if t and t not in seen:
            seen.add(t)
            tags.append(t)
        if len(tags) >= 5:
            break
    if not tags:
        tags = ["여행"]

    blocks.append({
        "block_type": "tags", "block_order": order, "day": None,
        "cluster_id": None, "pin_number": None,
        "depth": "brief", "ai_content": json.dumps(tags, ensure_ascii=False),
        "stay_min": None, "travel_from_prev_min": None,
        "distance_from_prev_km": None, "transport": None,
    })

    cache_stats = {
        "day_hit": day_hit_count,
        "day_miss": day_miss_count,
        "chunk_calls": len(miss_jobs),
    }

    return blocks, title, tags, new_day_cache, cache_stats
