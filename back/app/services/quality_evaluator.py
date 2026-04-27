"""
품질 평가 서비스 — LLM-as-a-judge

전체 place 블록을 한 번에 평가하고 기준 미달 블록만 재작성.
score < 0.65 → needs_rewrite = True
"""

import logging
from typing import Any, Dict, List

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.services.llm_factory import get_llm
from app.services.utils import parse_llm_json

logger = logging.getLogger(__name__)

REWRITE_THRESHOLD = 0.65

_EVALUATE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "당신은 여행 블로그 글의 품질을 평가하는 에디터입니다. 객관적으로 평가하고 JSON으로만 응답합니다."),
    ("human",
     """다음 여행 글 블록들을 평가해주세요.

{blocks_text}

각 블록을 아래 기준으로 0.0~1.0 점수를 매기세요:
- 장소의 특징/분위기가 명확히 드러나는가
- 반복 표현이 없는가
- 이전/다음 장소와의 흐름이 자연스러운가 (place 블록에만)
- 감성적이고 읽고 싶은 글인가

아래 JSON 형식으로만 응답하세요:
{{
    "results": [
        {{
            "block_order": 블록순서,
            "score": 0.0~1.0,
            "issues": ["문제점1", "문제점2"],
            "needs_rewrite": true 또는 false
        }}
    ]
}}"""),
])

_REWRITE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "당신은 여행 블로그 에디터입니다. 피드백을 반영해 글을 개선합니다."),
    ("human",
     """다음 여행 글 블록을 피드백을 반영해 개선해주세요.

[원본]
{original_text}

[장소 정보]
{place_info}

[피드백]
{issues}

[규칙]
- depth={depth}: {"main → 150~250자" if "{depth}" == "main" else "brief → 2~3문장 40~80자"}
- 헤딩 없이 본문만 출력
- 피드백의 문제를 해결하되 원본의 좋은 부분은 유지

개선된 본문만 출력, 다른 설명 없이."""),
])

_eval_chain = None
_rewrite_chain = None


def _get_eval_chain():
    global _eval_chain
    if _eval_chain is None:
        llm = get_llm(temperature=0.1, max_tokens=800)
        _eval_chain = _EVALUATE_PROMPT | llm | StrOutputParser()
    return _eval_chain


def _get_rewrite_chain():
    global _rewrite_chain
    if _rewrite_chain is None:
        llm = get_llm(temperature=0.6, max_tokens=400)
        _rewrite_chain = _REWRITE_PROMPT | llm | StrOutputParser()
    return _rewrite_chain


async def evaluate_and_rewrite(
    blocks: List[Dict[str, Any]],
    notes: Dict[int, Any],
) -> List[Dict[str, Any]]:
    """
    place 블록들을 평가하고 기준 미달 블록을 재작성.

    Args:
        blocks: block_generator.generate_all_blocks 결과 목록
        notes: {cluster_id: PlaceNote}

    Returns:
        quality_score와 재작성이 반영된 blocks
    """
    import asyncio

    place_blocks = [b for b in blocks if b["block_type"] == "place"]
    if not place_blocks:
        return blocks

    # 평가 입력 구성
    blocks_text_parts = []
    for b in place_blocks:
        blocks_text_parts.append(
            f"[블록 {b['block_order']}] depth={b['depth']}\n{b['ai_content']}"
        )
    blocks_text = "\n\n---\n\n".join(blocks_text_parts)

    # 평가 실행
    try:
        raw = await _get_eval_chain().ainvoke({"blocks_text": blocks_text})
        eval_data = parse_llm_json(raw)
        results = {r["block_order"]: r for r in eval_data.get("results", [])}
    except Exception as e:
        logger.warning(f"품질 평가 실패 (건너뜀): {e}")
        return blocks

    # 점수 반영 + 재작성 대상 수집
    rewrite_tasks = []
    block_map = {b["block_order"]: b for b in blocks}

    for b in place_blocks:
        result = results.get(b["block_order"], {})
        score = result.get("score", 1.0)
        b["quality_score"] = score

        if score < REWRITE_THRESHOLD and b.get("cluster_id") and not b.get("locked"):
            note = notes.get(b["cluster_id"])
            if note:
                rewrite_tasks.append((b, note, result.get("issues", [])))

    if not rewrite_tasks:
        return blocks

    # 재작성 병렬 실행
    logger.info(f"품질 미달 블록 {len(rewrite_tasks)}개 재작성")

    async def rewrite_one(block, note, issues):
        try:
            place_info = (
                f"이름: {note.place_name}, 카테고리: {note.category}, "
                f"분위기: {', '.join(note.mood_keywords)}, 핵심장면: {note.highlight_scene}"
            )
            result = await _get_rewrite_chain().ainvoke({
                "original_text": block["ai_content"],
                "place_info":    place_info,
                "issues":        "\n".join(f"- {i}" for i in issues),
                "depth":         block["depth"],
            })
            block["ai_content"] = result.strip()
            block["quality_score"] = 0.75  # 재작성 후 기본 점수
        except Exception as e:
            logger.warning(f"블록 재작성 실패 (order={block['block_order']}): {e}")

    await asyncio.gather(*[rewrite_one(b, n, i) for b, n, i in rewrite_tasks])

    return blocks
