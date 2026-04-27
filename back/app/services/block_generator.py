"""
블록 생성 서비스 — PlaceNote + 타임라인 데이터 → PostBlock 목록

이전/다음 장소 컨텍스트를 포함한 LLM 호출로
장소 간 흐름이 자연스럽게 이어지는 텍스트를 생성.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.services.llm_factory import get_llm
from app.services.place_note_service import PlaceNote
from app.services.utils import parse_llm_json

logger = logging.getLogger(__name__)


# ── 프롬프트: place 블록 ──────────────────────────────────────────────

_PLACE_MAIN_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "당신은 여행 블로거입니다. 현장감 있는 한국어 여행 글을 씁니다."),
    ("human",
     """다음 장소에 대한 여행 글 단락을 작성해주세요.

[현재 장소]
이름: {place_name} ({city}, {country})
카테고리: {category}
머문 시간: {stay_str}
분위기: {mood_keywords}
핵심 장면: {highlight_scene}

[이전 장소]{prev_context}

[다음 장소]{next_context}

작성 규칙:
1. 150~250자 (한국어 기준)
2. 헤딩 없이 본문만
3. 현재 장소의 분위기·특징·인상을 생생하게 묘사 (실제 여행자 시점)
4. 다음 장소가 있다면: 마지막에 자연스럽게 다음 장소로 이어지는 연결 문장 1줄 포함
5. 첫 문장 시작: 질문형·감탄형·묘사형·회상형 중 하나 선택

본문만 출력, 다른 설명 없이."""),
])

_PLACE_BRIEF_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "당신은 여행 블로거입니다. 간결하고 감성적인 한국어 여행 글을 씁니다."),
    ("human",
     """다음 장소에 대한 짧은 언급을 작성해주세요.

[현재 장소]
이름: {place_name} ({city}, {country})
카테고리: {category}
머문 시간: {stay_str}
분위기: {mood_keywords}
핵심 장면: {highlight_scene}

[다음 장소]{next_context}

작성 규칙:
1. 2~3문장 (40~80자)
2. 헤딩 없이 본문만
3. 간결하되 이 장소만의 특징 한 가지는 반드시 포함
4. 다음 장소가 있다면: 마지막 문장에 이동 흐름 자연스럽게 포함 가능

본문만 출력, 다른 설명 없이."""),
])

_TITLE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 여행 게시글 제목 전문가입니다."),
    ("human",
     """다음 여행 정보로 게시글 제목을 작성해주세요.

여행 개요:
{overview}

규칙:
1. 25자 이내
2. 방문 지역 + 여행 특징 포함
3. 감성적이고 매력적으로
4. 제목만 출력"""),
])

_INTRO_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 여행 블로거입니다."),
    ("human",
     """다음 여행의 도입부를 작성해주세요.

여행 개요:
{overview}

규칙:
1. 2~3문장
2. 여행 전체 분위기를 압축적으로 표현
3. 독자가 읽고 싶어지도록 감성적으로

본문만 출력, 다른 설명 없이."""),
])

_TAGS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "여행 콘텐츠에서 검색 최적화 태그를 추출합니다."),
    ("human",
     """다음 여행 정보로 태그를 생성해주세요.

제목: {title}
방문 장소: {places}

아래 JSON 형식으로만 응답:
{{"tags": ["태그1", "태그2", "태그3", "태그4", "태그5"]}}"""),
])


# ── LLM 체인 싱글톤 ───────────────────────────────────────────────────

_chains: Dict[str, Any] = {}


def _get_chain(name: str):
    if name not in _chains:
        llm_main  = get_llm(temperature=0.75, max_tokens=400)
        llm_brief = get_llm(temperature=0.5,  max_tokens=150)
        llm_meta  = get_llm(temperature=0.3,  max_tokens=200)
        parser = StrOutputParser()
        _chains["main"]  = _PLACE_MAIN_PROMPT  | llm_main  | parser
        _chains["brief"] = _PLACE_BRIEF_PROMPT | llm_brief | parser
        _chains["title"] = _TITLE_PROMPT       | llm_meta  | parser
        _chains["intro"] = _INTRO_PROMPT       | llm_meta  | parser
        _chains["tags"]  = _TAGS_PROMPT        | llm_meta  | parser
    return _chains[name]


# ── 컨텍스트 포맷 헬퍼 ───────────────────────────────────────────────

def _prev_context(item: Optional[Dict], prev_note: Optional[PlaceNote]) -> str:
    if not item or not prev_note:
        return " (없음)"
    transport = item.get("transport", "")
    travel_min = item.get("travel_from_prev_min")
    parts = [f"\n이름: {prev_note.place_name}"]
    if transport and travel_min:
        parts.append(f"이동: {transport} {travel_min}분")
    elif transport:
        parts.append(f"이동: {transport}")
    return "\n".join(parts)


def _next_context(item: Optional[Dict], next_note: Optional[PlaceNote]) -> str:
    if not item or not next_note:
        return " (없음 — 이 장소가 일차 마지막)"
    transport = item.get("transport", "")
    travel_min = item.get("travel_from_prev_min")
    parts = [f"\n이름: {next_note.place_name}"]
    if transport and travel_min:
        parts.append(f"이동 예정: {transport} {travel_min}분")
    elif transport:
        parts.append(f"이동 예정: {transport}")
    return "\n".join(parts)


# ── 장소 블록 생성 ────────────────────────────────────────────────────

async def generate_place_block(
    item: Dict[str, Any],
    note: PlaceNote,
    prev_item: Optional[Dict] = None,
    prev_note: Optional[PlaceNote] = None,
    next_item: Optional[Dict] = None,
    next_note: Optional[PlaceNote] = None,
) -> str:
    """장소 하나에 대한 블록 텍스트 생성"""
    chain_name = "main" if note.depth == "main" else "brief"
    inputs = {
        "place_name":      note.place_name,
        "city":            note.city,
        "country":         note.country,
        "category":        note.category,
        "stay_str":        item.get("stay_str") or "정보 없음",
        "mood_keywords":   ", ".join(note.mood_keywords) if note.mood_keywords else "정보 없음",
        "highlight_scene": note.highlight_scene or "",
        "next_context":    _next_context(next_item, next_note),
    }
    if chain_name == "main":
        inputs["prev_context"] = _prev_context(prev_item, prev_note)

    try:
        return (await _get_chain(chain_name).ainvoke(inputs)).strip()
    except Exception as e:
        logger.warning(f"place 블록 생성 실패 ({note.place_name}): {e}")
        return f"{note.place_name}에서의 시간을 사진에 담았습니다."


# ── 메타 블록 생성 ────────────────────────────────────────────────────

async def generate_title_block(overview: str) -> str:
    try:
        return (await _get_chain("title").ainvoke({"overview": overview})).strip()
    except Exception as e:
        logger.warning(f"title 블록 생성 실패: {e}")
        return "나의 여행 기록"


async def generate_intro_block(overview: str) -> str:
    try:
        return (await _get_chain("intro").ainvoke({"overview": overview})).strip()
    except Exception as e:
        logger.warning(f"intro 블록 생성 실패: {e}")
        return "사진으로 기록한 소중한 여행입니다."


async def generate_tags_block(title: str, place_names: List[str]) -> List[str]:
    try:
        raw = await _get_chain("tags").ainvoke({
            "title": title,
            "places": ", ".join(place_names[:10]),
        })
        data = parse_llm_json(raw)
        return data.get("tags", ["여행"])
    except Exception as e:
        logger.warning(f"tags 블록 생성 실패: {e}")
        return ["여행"]


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


# ── 전체 블록 배치 생성 ───────────────────────────────────────────────

async def generate_all_blocks(
    timeline: Dict[str, Any],
    notes: Dict[int, PlaceNote],
) -> List[Dict[str, Any]]:
    """
    타임라인 + PlaceNote 딕셔너리 → 모든 블록 데이터 목록 반환.
    반환값은 PostBlock 생성에 필요한 필드 딕셔너리 목록.
    """
    import asyncio

    days = timeline["days"]
    blocks: List[Dict[str, Any]] = []
    order = 0

    # 개요 텍스트 (제목/인트로/태그용)
    all_place_names = []
    for day, items in sorted(days.items()):
        for item in items:
            if not item["is_skip"]:
                note = notes.get(item["cluster"].id)
                if note:
                    all_place_names.append(note.place_name)

    overview = (
        f"총 {timeline['total_days']}일 여행, "
        f"방문 장소: {', '.join(all_place_names[:8])}"
        + ("..." if len(all_place_names) > 8 else "")
    )

    # 제목·인트로 (병렬)
    title_text, intro_text = await asyncio.gather(
        generate_title_block(overview),
        generate_intro_block(overview),
    )

    blocks.append({"block_type": "title", "block_order": order, "day": None,
                   "cluster_id": None, "pin_number": None,
                   "depth": "main", "ai_content": title_text,
                   "stay_min": None, "travel_from_prev_min": None,
                   "distance_from_prev_km": None, "transport": None})
    order += 1

    blocks.append({"block_type": "intro", "block_order": order, "day": None,
                   "cluster_id": None, "pin_number": None,
                   "depth": "main", "ai_content": intro_text,
                   "stay_min": None, "travel_from_prev_min": None,
                   "distance_from_prev_km": None, "transport": None})
    order += 1

    # 일차별 블록
    for day, items in sorted(days.items()):
        # day_header
        header_content = build_day_header_content(day, items)
        blocks.append({"block_type": "day_header", "block_order": order, "day": day,
                       "cluster_id": None, "pin_number": None,
                       "depth": "main", "ai_content": header_content,
                       "stay_min": None, "travel_from_prev_min": None,
                       "distance_from_prev_km": None, "transport": None})
        order += 1

        # place 블록들 (skip 제외, 병렬 생성)
        place_items = [item for item in items if not item["is_skip"]]
        place_tasks = []
        for idx, item in enumerate(place_items):
            note = notes.get(item["cluster"].id)
            if not note:
                continue
            prev_item = place_items[idx - 1] if idx > 0 else None
            prev_note = notes.get(prev_item["cluster"].id) if prev_item else None
            next_item = place_items[idx + 1] if idx < len(place_items) - 1 else None
            next_note = notes.get(next_item["cluster"].id) if next_item else None

            place_tasks.append((item, note, prev_item, prev_note, next_item, next_note))

        place_texts = await asyncio.gather(*[
            generate_place_block(item, note, prev_item, prev_note, next_item, next_note)
            for item, note, prev_item, prev_note, next_item, next_note in place_tasks
        ], return_exceptions=True)

        for (item, note, *_), text in zip(place_tasks, place_texts):
            cluster = item["cluster"]
            if isinstance(text, Exception):
                text = f"{note.place_name}에서의 시간을 기록했습니다."

            blocks.append({
                "block_type":            "place",
                "block_order":           order,
                "day":                   day,
                "cluster_id":            cluster.id,
                "pin_number":            item["pin_number"],
                "depth":                 note.depth,
                "ai_content":            text,
                "stay_min":              item.get("stay_min"),
                "travel_from_prev_min":  item.get("travel_from_prev_min"),
                "distance_from_prev_km": item.get("distance_from_prev_km"),
                "transport":             item.get("transport"),
            })
            order += 1

    # 태그
    tags = await generate_tags_block(title_text, all_place_names)
    blocks.append({"block_type": "tags", "block_order": order, "day": None,
                   "cluster_id": None, "pin_number": None,
                   "depth": "brief", "ai_content": json.dumps(tags, ensure_ascii=False),
                   "stay_min": None, "travel_from_prev_min": None,
                   "distance_from_prev_km": None, "transport": None})

    return blocks, title_text, tags
