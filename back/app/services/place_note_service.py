"""
Place Note 서비스 — 클러스터 → 구조화 JSON 노트 생성 (LLM, 병렬)

PlaceNote는 자연어 단락이 아닌 Pydantic 구조체.
LLM이 note를 생성하면서 동시에 depth(main|brief)를 결정.
fingerprint 기반 캐시: 같은 사진 구성이면 cluster.place_note에서 재사용.
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from app.services.llm_factory import get_llm
from app.services.utils import parse_llm_json

logger = logging.getLogger(__name__)


# ── Pydantic 스키마 ───────────────────────────────────────────────────

class PlaceNote(BaseModel):
    place_name:      str
    city:            str
    country:         str
    category:        str            # landmark|cafe|nature|restaurant|street|beach|market|transport|etc
    mood_keywords:   List[str]      # ["한적한", "골목길", "현지인 많은"]
    highlight_scene: str            # 이 장소에서 가장 인상적인 장면 한 줄
    depth:           str            # "main" | "brief"
    # depth 기준 (LLM이 판단):
    #   main  → 사진 5장↑ + 체류 30분↑ + 여행에서 의미 있는 장소
    #   brief → 그 외 (사진 적거나 짧게 들른 곳)


# ── fingerprint ───────────────────────────────────────────────────────

def cluster_fingerprint(cluster: Any) -> str:
    """클러스터 사진 구성 → 12자리 MD5 (캐시 키)"""
    photos = getattr(cluster, 'photos', [])
    file_keys = sorted(p.file_key for p in photos if p.file_key)
    if not file_keys:
        file_keys = [str(getattr(cluster, 'cluster_hash', cluster.id))]
    return hashlib.md5("|".join(file_keys).encode()).hexdigest()[:12]


# ── 프롬프트 ─────────────────────────────────────────────────────────

_PLACE_NOTE_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "당신은 여행 데이터를 구조화하는 전문가입니다. 주어진 정보만으로 정확한 JSON을 출력합니다.",
    ),
    (
        "human",
        """다음 여행 장소 정보를 바탕으로 구조화된 노트를 작성해주세요.

장소명: {location_name}
도시: {city}
국가: {country}
방문 시간대: {visit_time}
사진 수: {photo_count}장
머문 시간: {stay_str}

depth 판단 기준:
- main: 사진 5장 이상이고 체류 30분 이상이며 여행에서 의미 있는 장소
- brief: 그 외 (짧게 들르거나 사진이 적은 곳)

아래 JSON 형식으로만 응답하세요. 다른 설명 없이:
{{
    "place_name": "장소명",
    "city": "도시명",
    "country": "국가명",
    "category": "landmark|cafe|nature|restaurant|street|beach|market|transport|etc 중 하나",
    "mood_keywords": ["키워드1", "키워드2", "키워드3"],
    "highlight_scene": "이 장소에서 가장 인상적인 장면을 한 문장으로",
    "depth": "main 또는 brief"
}}""",
    ),
])

_chain = None


def _get_chain():
    global _chain
    if _chain is None:
        import os
        llm = get_llm(temperature=0.1, max_tokens=300)
        _chain = _PLACE_NOTE_PROMPT | llm | StrOutputParser()
    return _chain


# ── 단일 클러스터 처리 ────────────────────────────────────────────────

async def generate_place_note(
    cluster: Any,
    stay_str: str = "",
    visit_time: str = "",
) -> PlaceNote:
    """
    클러스터 하나 → PlaceNote 생성.
    cluster.place_note에 캐시가 있으면 재사용.
    """
    fp = cluster_fingerprint(cluster)

    # 캐시 확인
    if cluster.place_note:
        try:
            cached = json.loads(cluster.place_note)
            if cached.get("_fingerprint") == fp:
                return PlaceNote(**{k: v for k, v in cached.items() if k != "_fingerprint"})
        except Exception:
            pass

    # LLM 호출
    inputs = {
        "location_name": cluster.location_name or "알 수 없는 장소",
        "city":          cluster.city or "",
        "country":       cluster.country or "",
        "visit_time":    visit_time or "정보 없음",
        "photo_count":   getattr(cluster, 'photo_count', 0),
        "stay_str":      stay_str or "정보 없음",
    }

    try:
        raw = await _get_chain().ainvoke(inputs)
        data = parse_llm_json(raw)
        note = PlaceNote(
            place_name      = data.get("place_name", cluster.location_name or "장소"),
            city            = data.get("city", cluster.city or ""),
            country         = data.get("country", cluster.country or ""),
            category        = data.get("category", "etc"),
            mood_keywords   = data.get("mood_keywords", []),
            highlight_scene = data.get("highlight_scene", ""),
            depth           = data.get("depth", "brief"),
        )
    except Exception as e:
        logger.warning(f"PlaceNote 생성 실패 cluster_id={cluster.id}: {e}")
        note = PlaceNote(
            place_name      = cluster.location_name or "알 수 없는 장소",
            city            = cluster.city or "",
            country         = cluster.country or "",
            category        = "etc",
            mood_keywords   = [],
            highlight_scene = "",
            depth           = "brief",
        )

    # 캐시 저장값 반환 (DB 저장은 호출부에서)
    note._fingerprint = fp  # type: ignore[attr-defined]
    return note


# ── 배치 처리 ─────────────────────────────────────────────────────────

async def generate_place_notes_batch(
    timeline_items: List[Dict[str, Any]],
) -> Dict[int, PlaceNote]:
    """
    타임라인 아이템 목록에서 skip이 아닌 클러스터의 PlaceNote를 병렬 생성.

    Returns:
        {cluster.id: PlaceNote}
    """
    import asyncio

    tasks = {}
    for item in timeline_items:
        if item["is_skip"]:
            continue
        cluster = item["cluster"]
        tasks[cluster.id] = generate_place_note(
            cluster,
            stay_str=item.get("stay_str", ""),
            visit_time=item.get("arrival_str", ""),
        )

    if not tasks:
        return {}

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    notes: Dict[int, PlaceNote] = {}
    for cluster_id, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            logger.error(f"PlaceNote 배치 실패 cluster_id={cluster_id}: {result}")
        else:
            notes[cluster_id] = result

    return notes


def place_note_to_cache_json(note: PlaceNote, fingerprint: str) -> str:
    """PlaceNote → cluster.place_note 컬럼에 저장할 JSON 문자열"""
    data = note.model_dump()
    data["_fingerprint"] = fingerprint
    return json.dumps(data, ensure_ascii=False)
