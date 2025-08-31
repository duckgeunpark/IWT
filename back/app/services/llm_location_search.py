"""
LLM 기반 위치 인식 서비스
이미지/EXIF 기반으로 LLM이 위치 정보를 추정하고 지명을 인식
"""

from typing import Dict, Optional, List
import logging
from .llm_factory import get_llm_service

logger = logging.getLogger(__name__)


class LLMLocationSearchService:
    """LLM 기반 위치 인식 서비스"""
    
    def __init__(self):
        self.llm_service = get_llm_service()
    
    async def analyze_location_from_exif(
        self, 
        gps_data: Dict, 
        datetime_info: Optional[str] = None
    ) -> Dict:
        """
        EXIF GPS 데이터를 기반으로 LLM이 위치 정보 추정
        
        Args:
            gps_data: GPS 좌표 데이터
            datetime_info: 촬영 시간 정보
            
        Returns:
            LLM이 추정한 위치 정보
        """
        return await self.llm_service.analyze_location_from_exif(gps_data, datetime_info)

    async def analyze_location_from_image(
        self, 
        image_url: str, 
        exif_data: Optional[Dict] = None
    ) -> Dict:
        """
        이미지 URL과 EXIF 데이터를 기반으로 LLM이 위치 정보 추정
        
        Args:
            image_url: 이미지 URL
            exif_data: EXIF 메타데이터
            
        Returns:
            LLM이 추정한 위치 정보
        """
        return await self.llm_service.analyze_location_from_image(image_url, exif_data)

    async def enhance_location_with_context(
        self, 
        location_data: Dict, 
        user_context: Dict
    ) -> Dict:
        """
        사용자 컨텍스트를 활용하여 위치 정보 보완
        
        Args:
            location_data: 기존 위치 데이터
            user_context: 사용자 컨텍스트 (여행 기간, 선호도 등)
            
        Returns:
            보완된 위치 정보
        """
        try:
            prompt = f"""
기존 위치 정보를 사용자 컨텍스트를 바탕으로 보완해주세요:

기존 위치 정보:
{self._format_location_data(location_data)}

사용자 컨텍스트:
{self._format_user_context(user_context)}

더 정확하고 상세한 위치 정보로 보완해주세요.

다음 JSON 형식으로 응답해주세요:
{{
    "country": "국가명",
    "city": "도시명", 
    "region": "지역명",
    "landmark": "주요 랜드마크",
    "confidence": 0.0-1.0,
    "enhanced_details": {{
        "timezone": "시간대",
        "language": "주요 언어",
        "currency": "통화",
        "best_time_to_visit": "최적 방문 시기"
    }}
}}

위치 정보만 JSON으로 응답하고 다른 설명은 포함하지 마세요.
"""

            response = await self.llm_service.provider.chat_completion(
                messages=[
                    {"role": "system", "content": "당신은 위치 정보를 사용자 컨텍스트에 맞게 보완하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=400
            )

            return self.llm_service._parse_json_response(response)

        except Exception as e:
            logger.error(f"위치 정보 보완 실패: {str(e)}")
            return location_data
    
    def _format_location_data(self, location_data: Dict) -> str:
        """위치 데이터 포맷팅"""
        import json
        return json.dumps(location_data, indent=2, ensure_ascii=False)
    
    def _format_user_context(self, user_context: Dict) -> str:
        """사용자 컨텍스트 포맷팅"""
        import json
        return json.dumps(user_context, indent=2, ensure_ascii=False)


# 서비스 인스턴스 생성
llm_location_service = LLMLocationSearchService() 