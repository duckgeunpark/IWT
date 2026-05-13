"""공통 유틸리티"""

import json
import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)


_FENCE_OPEN_RE = re.compile(r"^\s*```(?:json|JSON)?\s*\n?")
_FENCE_CLOSE_RE = re.compile(r"\n?\s*```\s*$")


def _strip_code_fence(text: str) -> str:
    """선행/후행 ``` 펜스를 가능한 만큼 제거 (한쪽만 있어도 동작)."""
    text = _FENCE_OPEN_RE.sub("", text)
    text = _FENCE_CLOSE_RE.sub("", text)
    return text.strip()


def _extract_balanced_json(text: str) -> str:
    """
    첫 '{' 부터 균형 잡힌 '}' 까지를 추출.
    문자열 내부의 중괄호와 이스케이프된 따옴표를 고려.
    잘린 응답이라 닫는 '}' 가 부족하면 부족한 만큼 보충해서 반환.
    """
    start = text.find("{")
    if start < 0:
        return text

    depth = 0
    in_string = False
    escape = False
    end = -1
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break

    if end >= 0:
        return text[start : end + 1]

    # 응답이 잘려 닫는 '}' 가 부족한 경우 — 부족한 만큼 채워 복구 시도
    fragment = text[start:]
    if in_string:
        fragment += '"'
    if depth > 0:
        fragment += "}" * depth
    return fragment


def parse_llm_json(response: str) -> Dict[str, Any]:
    """
    LLM JSON 응답 파싱 — 견고화 버전.

    처리 가능한 케이스:
      - ```json ... ``` 코드블록으로 감싼 응답
      - 닫는 ``` 가 없거나 잘린 응답
      - JSON 앞뒤에 잡설이 붙은 응답
      - 응답이 토큰 제한으로 잘려 닫는 '}' 가 부족한 경우 (부분 복구)
    """
    if not response:
        return {}

    text = response.strip()

    # 1차: 완전한 코드블록 (```json ... ```)
    block = re.search(r"```(?:json|JSON)?\s*([\s\S]*?)```", text)
    if block:
        candidate = block.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass  # 다음 단계로

    # 2차: 펜스 일부 제거 후 균형 괄호 추출
    stripped = _strip_code_fence(text)
    candidate = _extract_balanced_json(stripped)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # 3차: 원문 그대로 시도
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        logger.error(f"JSON 파싱 실패: {response[:300]}")
        return {}
