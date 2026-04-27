"""
LLM 기반 위치 인식 서비스 (LangChain LCEL 기반)
이미지/EXIF 기반으로 LLM이 위치 정보를 추정하고 지명을 인식
"""

import json
import logging
from typing import Dict, List, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.services.llm_factory import get_default_llm
from app.services.utils import parse_llm_json

logger = logging.getLogger(__name__)

# ── 프롬프트 템플릿 ──────────────────────────────────────────────────

_EXIF_LOCATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 GPS 좌표를 기반으로 정확한 위치 정보를 제공하는 전문가입니다."),
    ("human", """다음 GPS 좌표를 기반으로 위치 정보를 추정해주세요:
위도: {lat}, 경도: {lon}
촬영 시간: {datetime_info}

다음 JSON 형식으로만 응답해주세요:
{{
    "country": "국가명",
    "city": "도시명",
    "region": "지역명 (선택사항)",
    "landmark": "주요 랜드마크 (선택사항)",
    "confidence": 0.0
}}

위치 정보만 JSON으로 응답하고 다른 설명은 포함하지 마세요."""),
])

_IMAGE_LOCATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 이미지를 분석하여 정확한 위치 정보를 제공하는 전문가입니다."),
    ("human", """다음 이미지를 분석하여 위치 정보를 추정해주세요:
이미지 URL: {image_url}

EXIF 데이터:
{exif_text}

이미지에서 보이는 건물, 풍경, 표지판 등을 바탕으로 위치를 추정해주세요.

다음 JSON 형식으로만 응답해주세요:
{{
    "country": "국가명",
    "city": "도시명",
    "region": "지역명 (선택사항)",
    "landmark": "주요 랜드마크 (선택사항)",
    "confidence": 0.0,
    "description": "위치 추정 근거 설명"
}}

위치 정보만 JSON으로 응답하고 다른 설명은 포함하지 마세요."""),
])

_ENHANCE_LOCATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 위치 정보를 사용자 컨텍스트에 맞게 보완하는 전문가입니다."),
    ("human", """기존 위치 정보를 사용자 컨텍스트를 바탕으로 보완해주세요:

기존 위치 정보:
{location_data_text}

사용자 컨텍스트:
{user_context_text}

더 정확하고 상세한 위치 정보로 보완해주세요.

다음 JSON 형식으로만 응답해주세요:
{{
    "country": "국가명",
    "city": "도시명",
    "region": "지역명",
    "landmark": "주요 랜드마크",
    "confidence": 0.0,
    "enhanced_details": {{
        "timezone": "시간대",
        "language": "주요 언어",
        "currency": "통화",
        "best_time_to_visit": "최적 방문 시기"
    }}
}}

위치 정보만 JSON으로 응답하고 다른 설명은 포함하지 마세요."""),
])


class LLMLocationSearchService:
    """LLM 기반 위치 인식 서비스 (LCEL)"""

    def __init__(self):
        llm = get_default_llm()
        parser = StrOutputParser()
        self._exif_chain    = _EXIF_LOCATION_PROMPT    | llm | parser
        self._image_chain   = _IMAGE_LOCATION_PROMPT   | llm | parser
        self._enhance_chain = _ENHANCE_LOCATION_PROMPT | llm | parser

    async def analyze_location_from_exif(
        self,
        gps_data: Dict,
        datetime_info: Optional[str] = None,
    ) -> Dict:
        """EXIF GPS 데이터 기반 위치 추정"""
        if not gps_data or not gps_data.get("latitude") or not gps_data.get("longitude"):
            return {"error": "GPS 데이터가 없습니다.", "coordinates": None}

        lat = gps_data["latitude"]
        lon = gps_data["longitude"]
        try:
            raw = await self._exif_chain.ainvoke({
                "lat": lat,
                "lon": lon,
                "datetime_info": datetime_info or "알 수 없음",
            })
            data = parse_llm_json(raw)
            data["coordinates"] = {"latitude": lat, "longitude": lon}
            return data
        except Exception as e:
            logger.error(f"LLM 위치 추정 실패: {e}")
            return {"error": str(e), "coordinates": {"latitude": lat, "longitude": lon}}

    async def analyze_location_from_image(
        self,
        image_url: str,
        exif_data: Optional[Dict] = None,
    ) -> Dict:
        """이미지 URL + EXIF 기반 위치 추정"""
        try:
            raw = await self._image_chain.ainvoke({
                "image_url": image_url,
                "exif_text": json.dumps(exif_data, ensure_ascii=False, indent=2) if exif_data else "없음",
            })
            return parse_llm_json(raw)
        except Exception as e:
            logger.error(f"LLM 이미지 위치 추정 실패: {e}")
            return {"error": str(e), "coordinates": None}

    async def enhance_location_with_context(
        self,
        location_data: Dict,
        user_context: Dict,
    ) -> Dict:
        """사용자 컨텍스트로 위치 정보 보완"""
        try:
            raw = await self._enhance_chain.ainvoke({
                "location_data_text": json.dumps(location_data, ensure_ascii=False, indent=2),
                "user_context_text":  json.dumps(user_context,  ensure_ascii=False, indent=2),
            })
            return parse_llm_json(raw)
        except Exception as e:
            logger.error(f"위치 정보 보완 실패: {e}")
            return location_data


# 서비스 싱글톤
llm_location_service = LLMLocationSearchService()
