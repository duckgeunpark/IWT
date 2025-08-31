"""
OCR 기반 위치 정보 보완 서비스
이미지에서 텍스트를 추출하여 위치 정보를 보완
"""

from typing import Dict, Optional, List
import logging
from .llm_factory import get_llm_service

logger = logging.getLogger(__name__)


class OCRAugmenterService:
    """OCR 기반 위치 정보 보완 서비스"""
    
    def __init__(self):
        self.llm_service = get_llm_service()
    
    async def extract_text_from_image(
        self, 
        image_url: str
    ) -> Dict:
        """
        이미지에서 텍스트 추출
        
        Args:
            image_url: 이미지 URL
            
        Returns:
            추출된 텍스트 정보
        """
        return await self.llm_service.extract_text_from_image(image_url)

    async def enhance_location_with_ocr(
        self, 
        image_url: str, 
        existing_location: Optional[Dict] = None
    ) -> Dict:
        """
        OCR을 통해 위치 정보 보완
        
        Args:
            image_url: 이미지 URL
            existing_location: 기존 위치 정보
            
        Returns:
            보완된 위치 정보
        """
        try:
            # 텍스트 추출
            text_data = await self.extract_text_from_image(image_url)
            
            if text_data.get("error"):
                return existing_location or {}
            
            # 위치 정보 보완 프롬프트 생성
            prompt = f"""
다음 정보를 바탕으로 위치 정보를 보완해주세요:

기존 위치 정보:
{self._format_location_data(existing_location)}

추출된 텍스트:
{self._format_text_data(text_data)}

추출된 텍스트를 바탕으로 위치 정보를 더 정확하게 보완해주세요.

다음 JSON 형식으로 응답해주세요:
{{
    "country": "국가명",
    "city": "도시명",
    "region": "지역명",
    "landmark": "주요 랜드마크",
    "business_name": "상호명",
    "confidence": 0.0-1.0,
    "ocr_enhanced": true
}}

위치 정보만 JSON으로 응답하고 다른 설명은 포함하지 마세요.
"""

            response = await self.llm_service.provider.chat_completion(
                messages=[
                    {"role": "system", "content": "당신은 OCR 정보를 바탕으로 위치 정보를 보완하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )

            enhanced_location = self.llm_service._parse_json_response(response)
            
            # 기존 정보와 병합
            if existing_location:
                enhanced_location = {**existing_location, **enhanced_location}
            
            return enhanced_location

        except Exception as e:
            logger.error(f"OCR 위치 보완 실패: {str(e)}")
            return existing_location or {}

    async def analyze_text_for_location(
        self, 
        text_data: Dict
    ) -> Dict:
        """
        추출된 텍스트를 분석하여 위치 정보 추출
        
        Args:
            text_data: 추출된 텍스트 데이터
            
        Returns:
            분석된 위치 정보
        """
        try:
            prompt = f"""
다음 텍스트를 분석하여 위치 정보를 추출해주세요:

추출된 텍스트:
{self._format_text_data(text_data)}

텍스트에서 국가, 도시, 지역, 랜드마크 등의 위치 정보를 찾아주세요.

다음 JSON 형식으로 응답해주세요:
{{
    "country": "국가명",
    "city": "도시명",
    "region": "지역명",
    "landmark": "주요 랜드마크",
    "business_name": "상호명",
    "confidence": 0.0-1.0,
    "extracted_from_text": true
}}

위치 정보만 JSON으로 응답하고 다른 설명은 포함하지 마세요.
"""

            response = await self.llm_service.provider.chat_completion(
                messages=[
                    {"role": "system", "content": "당신은 텍스트에서 위치 정보를 추출하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )

            return self.llm_service._parse_json_response(response)

        except Exception as e:
            logger.error(f"텍스트 위치 분석 실패: {str(e)}")
            return {
                "error": f"텍스트 위치 분석 중 오류가 발생했습니다: {str(e)}",
                "confidence": 0.0
            }
    
    def _format_location_data(self, location_data: Optional[Dict]) -> str:
        """위치 데이터 포맷팅"""
        import json
        if location_data:
            return json.dumps(location_data, indent=2, ensure_ascii=False)
        return "위치 정보 없음"
    
    def _format_text_data(self, text_data: Dict) -> str:
        """텍스트 데이터 포맷팅"""
        import json
        return json.dumps(text_data, indent=2, ensure_ascii=False)


# 서비스 인스턴스 생성
ocr_service = OCRAugmenterService() 