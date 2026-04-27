"""공통 유틸리티"""

import json
import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)


def parse_llm_json(response: str) -> Dict[str, Any]:
    """LLM JSON 응답 파싱 (마크다운 코드블록 포함 처리)"""
    try:
        text = response.strip()
        block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if block:
            text = block.group(1).strip()
        return json.loads(text)
    except json.JSONDecodeError:
        logger.error(f"JSON 파싱 실패: {response[:200]}")
        return {}
