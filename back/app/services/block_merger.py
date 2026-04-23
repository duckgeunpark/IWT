"""
block_merger.py
케이스 2 재생성 시 기존 blocks[] + 신규 LLM 결과 병합.
사용자가 편집한 user_content는 절대 건드리지 않음.
"""
import uuid
from typing import Any, Dict, List, Optional, Set


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


def merge_blocks(
    existing_blocks: List[Dict[str, Any]],
    new_cluster_db_rows: List[Any],
    cache_hit_hashes: Set[str],
    hash_to_new_paragraph: Dict[str, str],
    new_itinerary: str,
    new_conclusion: str,
    regenerate_title: bool = False,
) -> List[Dict[str, Any]]:
    """
    기존 blocks[]에 재생성 결과를 병합.

    Args:
        existing_blocks: 현재 Post.blocks 파싱 결과
        new_cluster_db_rows: 재계산 후 DB에 저장된 Cluster 객체 목록
            각 항목에 id, cluster_hash, location_name 필드 필요
        cache_hit_hashes: cluster_hash 값 중 캐시 히트(변경 없음)된 것들
        hash_to_new_paragraph: cluster_hash → 새 LLM 단락 (cache miss만 포함)
        new_itinerary: 새로 생성된 일정표 마크다운
        new_conclusion: 새로 생성된 결론 텍스트
        regenerate_title: True면 title 블록 ai_content도 교체

    Returns:
        병합된 blocks[] (order 재번호 완료)
    """
    result: List[Dict[str, Any]] = []

    # DB cluster rows를 hash로 인덱싱
    hash_to_db_cluster: Dict[str, Any] = {row.cluster_hash: row for row in new_cluster_db_rows}
    new_db_ids: Set[int] = {row.id for row in new_cluster_db_rows}

    # 기존 블록에서 cluster_id 기준 빠른 조회
    existing_by_cluster_id: Dict[int, List[Dict[str, Any]]] = {}
    for blk in existing_blocks:
        cid = blk.get("cluster_id")
        if cid is not None:
            existing_by_cluster_id.setdefault(cid, []).append(blk)

    # ── 1) title 블록 처리 ───────────────────────────────────────────────
    title_blk = next((b for b in existing_blocks if b["block_type"] == "title"), None)
    if title_blk:
        if not title_blk.get("locked") and regenerate_title:
            title_blk = {**title_blk}  # 복사
        result.append(title_blk)
    else:
        result.append(_make_block("title", 0))

    # ── 2) itinerary 블록 — 항상 ai_content 교체 ─────────────────────────
    itinerary_blk = next((b for b in existing_blocks if b["block_type"] == "itinerary"), None)
    if itinerary_blk and itinerary_blk.get("locked"):
        result.append(itinerary_blk)
    elif itinerary_blk:
        result.append({**itinerary_blk, "ai_content": new_itinerary})
    else:
        result.append(_make_block("itinerary", 0, ai_content=new_itinerary))

    # ── 3) user_insert 블록 수집 (anchor_cluster_id 기준으로 재배치) ─────
    user_inserts: List[Dict[str, Any]] = [b for b in existing_blocks if b["block_type"] == "user_insert"]
    # anchor → [user_insert 블록]
    anchor_to_inserts: Dict[Optional[int], List[Dict[str, Any]]] = {}
    for ui in user_inserts:
        anchor = ui.get("anchor_cluster_id")
        anchor_to_inserts.setdefault(anchor, []).append(ui)

    # ── 4) 클러스터 블록 쌍 병합 ─────────────────────────────────────────
    processed_existing_cluster_ids: Set[int] = set()

    for db_cluster in sorted(new_cluster_db_rows, key=lambda r: r.cluster_order):
        c_hash = db_cluster.cluster_hash
        c_db_id = db_cluster.id

        is_cache_hit = c_hash in cache_hit_hashes

        # 기존 블록에서 이 cluster_id에 해당하는 쌍 찾기
        existing_pair = existing_by_cluster_id.get(c_db_id, [])
        existing_photos = next((b for b in existing_pair if b["block_type"] == "cluster_photos"), None)
        existing_text = next((b for b in existing_pair if b["block_type"] == "cluster_text"), None)
        processed_existing_cluster_ids.add(c_db_id)

        # cluster_photos 블록
        if existing_photos:
            result.append(existing_photos)
        else:
            result.append(_make_block("cluster_photos", 0, cluster_id=c_db_id))

        # cluster_text 블록
        if existing_text and existing_text.get("locked"):
            result.append(existing_text)
        elif existing_text and is_cache_hit:
            # 캐시 히트 → ai_content 유지, user_content 유지
            result.append(existing_text)
        elif existing_text:
            # 캐시 미스 → ai_content만 교체, user_content 유지
            new_para = hash_to_new_paragraph.get(c_hash, existing_text.get("ai_content", ""))
            result.append({**existing_text, "ai_content": new_para})
        else:
            # 신규 클러스터 → 새 블록 생성
            new_para = hash_to_new_paragraph.get(c_hash, "")
            result.append(_make_block("cluster_text", 0, ai_content=new_para, cluster_id=c_db_id))

        # 이 클러스터 이후에 anchor된 user_insert 삽입
        for ui in anchor_to_inserts.get(c_db_id, []):
            result.append(ui)

    # anchor가 삭제된 cluster를 가리키는 user_insert → 맨 뒤로
    for anchor_id, inserts in anchor_to_inserts.items():
        if anchor_id is None or anchor_id not in new_db_ids:
            result.extend(inserts)

    # ── 5) conclusion 블록 — ai_content 교체, user_content 유지 ──────────
    conclusion_blk = next((b for b in existing_blocks if b["block_type"] == "conclusion"), None)
    if conclusion_blk and conclusion_blk.get("locked"):
        result.append(conclusion_blk)
    elif conclusion_blk:
        result.append({**conclusion_blk, "ai_content": new_conclusion})
    else:
        if new_conclusion:
            result.append(_make_block("conclusion", 0, ai_content=new_conclusion))

    # ── 6) order 재번호 ──────────────────────────────────────────────────
    for idx, blk in enumerate(result):
        blk["order"] = idx

    return result


def has_user_edits(blocks: List[Dict[str, Any]]) -> bool:
    """blocks 중 user_content가 있는 블록이 하나라도 있으면 True"""
    return any(b.get("user_content") is not None for b in blocks)
