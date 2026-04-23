"""
block_assembler.py
3-stage LLM 파이프라인 결과 → blocks[] 조립 (케이스 1: 최초 생성 전용)
"""
import re
import uuid
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional


# ── 클러스터 stable hash ──────────────────────────────────────────────────────

def compute_cluster_hash(centroid_lat: Optional[float], centroid_lng: Optional[float], date_str: Optional[str]) -> str:
    """
    GPS 격자(0.001도 ≈ 100m) + 날짜 문자열(YYYY-MM-DD)을 기반으로 stable hash 생성.
    GPS 없으면 날짜만 사용.
    """
    if centroid_lat is not None and centroid_lng is not None:
        lat_grid = round(centroid_lat, 3)
        lng_grid = round(centroid_lng, 3)
        raw = f"{lat_grid:.3f}_{lng_grid:.3f}_{date_str or 'unknown'}"
    else:
        raw = f"nogps_{date_str or 'unknown'}"
    return hashlib.md5(raw.encode()).hexdigest()[:20]


# ── Stage 3 출력 파싱 ────────────────────────────────────────────────────────

def _parse_stage3_markdown(markdown: str) -> Dict[str, Any]:
    """
    Stage 3 최종 마크다운을 파싱해서 구조화된 dict 반환.

    반환:
      {
        "title": str,
        "itinerary": str,         # | 로 시작하는 표 전체
        "sections": [             # ## 섹션 목록 (결론 제외)
            {"heading": str, "body": str},
            ...
        ],
        "conclusion": str,        # 마지막 ## 없는 끝 블록 또는 빈 문자열
        "tags": str,              # <!-- tags: ... --> 전체 줄
      }
    """
    lines = markdown.strip().split("\n")

    title = ""
    itinerary_lines: List[str] = []
    sections: List[Dict[str, str]] = []
    conclusion_lines: List[str] = []
    tags_line = ""

    # 1) 제목 추출 (# 로 시작하는 첫 줄)
    content_lines = []
    for line in lines:
        if not title and line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("<!-- tags:"):
            tags_line = line
        else:
            content_lines.append(line)

    # 2) 일정표(|로 시작하는 블록) 추출 — 첫 번째 ## 앞에 있는 것만
    first_h2_idx = next((i for i, l in enumerate(content_lines) if l.startswith("## ")), len(content_lines))

    pre_h2 = content_lines[:first_h2_idx]
    post_h2 = content_lines[first_h2_idx:]

    # pre_h2에서 표 행 추출
    for line in pre_h2:
        if line.strip().startswith("|"):
            itinerary_lines.append(line)

    # 3) ## 섹션 파싱
    current_heading = None
    current_body: List[str] = []

    for line in post_h2:
        if line.startswith("## "):
            if current_heading is not None:
                sections.append({"heading": current_heading, "body": "\n".join(current_body).strip()})
            current_heading = line[3:].strip()
            current_body = []
        else:
            current_body.append(line)

    if current_heading is not None:
        body_text = "\n".join(current_body).strip()
        # 마지막 ## 섹션 — 끝 단락이 결론처럼 보이면 conclusion으로 분리
        # (간단히: 마지막 섹션은 그냥 sections에 넣고, conclusion은 별도 처리)
        sections.append({"heading": current_heading, "body": body_text})

    return {
        "title": title,
        "itinerary": "\n".join(itinerary_lines),
        "sections": sections,
        "conclusion": "",
        "tags": tags_line,
    }


# ── 블록 팩토리 ───────────────────────────────────────────────────────────────

def _make_block(block_type: str, order: int, ai_content: Optional[str] = None,
                cluster_id: Optional[int] = None, anchor_cluster_id: Optional[int] = None) -> Dict[str, Any]:
    return {
        "block_id": str(uuid.uuid4()),
        "block_type": block_type,
        "order": order,
        "cluster_id": cluster_id,
        "ai_content": ai_content,
        "user_content": None,
        "locked": False,
        "anchor_cluster_id": anchor_cluster_id,
    }


# ── 메인 조립 함수 ────────────────────────────────────────────────────────────

def assemble_blocks(
    pipeline_result: Dict[str, Any],
    pipeline_clusters: List[Dict[str, Any]],
    db_cluster_id_map: Dict[int, int],
) -> List[Dict[str, Any]]:
    """
    3-stage 파이프라인 결과를 blocks[] 배열로 조립.

    Args:
        pipeline_result: run() / run_incremental() 반환값.
            필드: markdown, title, tags, itinerary_table, stage2_cache
        pipeline_clusters: auto-create에서 사용한 클러스터 목록.
            각 항목: {cluster_id(int), location_name, ...}
        db_cluster_id_map: pipeline cluster_id(int) → DB Cluster.id(int) 매핑

    Returns:
        블록 배열 (order 순서대로 정렬됨)
    """
    markdown = pipeline_result.get("markdown", "")
    itinerary_table = pipeline_result.get("itinerary_table", "")
    stage2_cache = pipeline_result.get("stage2_cache", {})

    parsed = _parse_stage3_markdown(markdown)
    blocks: List[Dict[str, Any]] = []
    order = 0

    # 블록 0: title
    blocks.append(_make_block("title", order, ai_content=parsed["title"] or pipeline_result.get("title", "")))
    order += 1

    # 블록 1: itinerary
    blocks.append(_make_block("itinerary", order, ai_content=itinerary_table or parsed["itinerary"]))
    order += 1

    # location_name → DB cluster_id 매핑 빌드
    name_to_pipeline_id = {c.get("location_name", ""): c["cluster_id"] for c in pipeline_clusters}

    # 단락 캐시에서 location_name → paragraph 매핑
    # stage2_cache: {fingerprint: {location_name, paragraph, photo_url}}
    name_to_paragraph: Dict[str, str] = {}
    name_to_photo_url: Dict[str, str] = {}
    for cached in stage2_cache.values():
        name = cached.get("location_name", "")
        if name:
            name_to_paragraph[name] = cached.get("paragraph", "")
            name_to_photo_url[name] = cached.get("photo_url", "")

    # 클러스터별 블록 쌍 생성
    # Stage 3 sections의 순서를 따르되, pipeline_clusters 순서로 fallback
    used_headings = set()
    section_map = {s["heading"]: s["body"] for s in parsed["sections"]}

    for cluster in sorted(pipeline_clusters, key=lambda c: c.get("cluster_order", c["cluster_id"])):
        loc_name = cluster.get("location_name", "")
        pipeline_cid = cluster["cluster_id"]
        db_cid = db_cluster_id_map.get(pipeline_cid)

        # cluster_photos 블록
        blocks.append(_make_block("cluster_photos", order, cluster_id=db_cid))
        order += 1

        # cluster_text 블록: Stage 3 본문 우선, 없으면 Stage 2 단락
        body = section_map.get(loc_name) or name_to_paragraph.get(loc_name, "")
        blocks.append(_make_block("cluster_text", order, ai_content=body, cluster_id=db_cid))
        order += 1
        used_headings.add(loc_name)

    # Stage 3에서 클러스터와 매핑 안 된 섹션 → conclusion 후보
    extra_sections = [s for s in parsed["sections"] if s["heading"] not in used_headings]
    if extra_sections:
        conclusion_text = "\n\n".join(s["body"] for s in extra_sections)
        blocks.append(_make_block("conclusion", order, ai_content=conclusion_text))
        order += 1
    elif parsed.get("conclusion"):
        blocks.append(_make_block("conclusion", order, ai_content=parsed["conclusion"]))
        order += 1

    return blocks
