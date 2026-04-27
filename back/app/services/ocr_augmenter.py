"""
OCR 기반 위치 정보 보완 서비스 (LangChain LCEL 기반)
이미지에서 텍스트를 추출하여 위치 정보를 보완
"""

import json
import logging
from typing import Dict, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.services.llm_factory import get_default_llm
from app.services.utils import parse_llm_json

logger = logging.getLogger(__name__)

_OCR_EXTRACT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 이미지에서 텍스트를 추출하는 전문가입니다."),
    ("human", """다음 이미지에서 텍스트를 추출해주세요:
이미지 URL: {image_url}

이미지에서 보이는 모든 텍스트, 표지판, 간판, 메뉴 등을 읽어서 알려주세요.

다음 JSON 형식으로만 응답해주세요:
{{
    "extracted_text": ["추출된 텍스트들"],
    "location_clues": ["위치 관련 단서들"],
    "business_names": ["상호명들"],
    "confidence": 0.0
}}

텍스트 정보만 JSON으로 응답하고 다른 설명은 포함하지 마세요."""),
])

_OCR_ENHANCE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 OCR 정보를 바탕으로 위치 정보를 보완하는 전문가입니다."),
    ("human", """다음 정보를 바탕으로 위치 정보를 보완해주세요:

기존 위치 정보:
{existing_location_text}

추출된 텍스트:
{text_data_text}

다음 JSON 형식으로만 응답해주세요:
{{
    "country": "국가명",
    "city": "도시명",
    "region": "지역명",
    "landmark": "주요 랜드마크",
    "business_name": "상호명",
    "confidence": 0.0,
    "ocr_enhanced": true
}}

위치 정보만 JSON으로 응답하고 다른 설명은 포함하지 마세요."""),
])

_TEXT_ANALYZE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 텍스트에서 위치 정보를 추출하는 전문가입니다."),
    ("human", """다음 텍스트를 분석하여 위치 정보를 추출해주세요:

추출된 텍스트:
{text_data_text}

다음 JSON 형식으로만 응답해주세요:
{{
    "country": "국가명",
    "city": "도시명",
    "region": "지역명",
    "landmark": "주요 랜드마크",
    "business_name": "상호명",
    "confidence": 0.0,
    "extracted_from_text": true
}}

위치 정보만 JSON으로 응답하고 다른 설명은 포함하지 마세요."""),
])


class OCRAugmenterService:
    """OCR 기반 위치 정보 보완 서비스 (LCEL)"""

    def __init__(self):
        llm = get_default_llm()
        parser = StrOutputParser()
        self._extract_chain  = _OCR_EXTRACT_PROMPT  | llm | parser
        self._enhance_chain  = _OCR_ENHANCE_PROMPT  | llm | parser
        self._analyze_chain  = _TEXT_ANALYZE_PROMPT | llm | parser

    async def extract_text_from_image(self, image_url: str) -> Dict:
        """이미지에서 텍스트 추출"""
        try:
            raw = await self._extract_chain.ainvoke({"image_url": image_url})
            return parse_llm_json(raw)
        except Exception as e:
            logger.error(f"텍스트 추출 실패: {e}")
            return {"extracted_text": [], "location_clues": [], "business_names": [], "confidence": 0.0}

    async def enhance_location_with_ocr(
        self,
        image_url: str,
        existing_location: Optional[Dict] = None,
    ) -> Dict:
        """OCR로 위치 정보 보완"""
        try:
            text_data = await self.extract_text_from_image(image_url)
            if not text_data or text_data.get("error"):
                return existing_location or {}

            raw = await self._enhance_chain.ainvoke({
                "existing_location_text": json.dumps(existing_location, ensure_ascii=False, indent=2) if existing_location else "없음",
                "text_data_text": json.dumps(text_data, ensure_ascii=False, indent=2),
            })
            enhanced = parse_llm_json(raw)
            if existing_location:
                enhanced = {**existing_location, **enhanced}
            return enhanced
        except Exception as e:
            logger.error(f"OCR 위치 보완 실패: {e}")
            return existing_location or {}

    async def analyze_text_for_location(self, text_data: Dict) -> Dict:
        """추출된 텍스트 분석 → 위치 정보"""
        try:
            raw = await self._analyze_chain.ainvoke({
                "text_data_text": json.dumps(text_data, ensure_ascii=False, indent=2),
            })
            return parse_llm_json(raw)
        except Exception as e:
            logger.error(f"텍스트 위치 분석 실패: {e}")
            return {"error": str(e), "confidence": 0.0}


# 서비스 싱글톤
ocr_service = OCRAugmenterService()
