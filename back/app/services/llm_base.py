"""
LLM 서비스 기본 인터페이스
다양한 LLM 제공자(Groq, OpenAI, Anthropic 등)를 쉽게 교체할 수 있도록 추상화
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """LLM 제공자 기본 인터페이스"""
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 500,
        **kwargs
    ) -> str:
        """
        채팅 완성 API 호출
        
        Args:
            messages: 메시지 리스트
            temperature: 창의성 (0.0-1.0)
            max_tokens: 최대 토큰 수
            **kwargs: 추가 파라미터
            
        Returns:
            LLM 응답 텍스트
        """
        pass
    
    @abstractmethod
    async def vision_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: int = 500,
        **kwargs
    ) -> str:
        """
        비전 완성 API 호출 (이미지 분석)
        
        Args:
            messages: 메시지 리스트 (이미지 포함)
            temperature: 창의성 (0.0-1.0)
            max_tokens: 최대 토큰 수
            **kwargs: 추가 파라미터
            
        Returns:
            LLM 응답 텍스트
        """
        pass


class LLMService:
    """LLM 서비스 관리자"""
    
    def __init__(self, provider: LLMProvider):
        self.provider = provider
    
    async def analyze_location_from_exif(
        self, 
        gps_data: Dict, 
        datetime_info: Optional[str] = None
    ) -> Dict:
        """EXIF GPS 데이터 기반 위치 분석"""
        try:
            if not gps_data or not gps_data.get('latitude') or not gps_data.get('longitude'):
                return {
                    "error": "GPS 데이터가 없습니다.",
                    "coordinates": None
                }

            lat = gps_data['latitude']
            lon = gps_data['longitude']
            
            prompt = f"""
다음 GPS 좌표를 기반으로 위치 정보를 추정해주세요:
위도: {lat}, 경도: {lon}
촬영 시간: {datetime_info or '알 수 없음'}

다음 JSON 형식으로 응답해주세요:
{{
    "country": "국가명",
    "city": "도시명", 
    "region": "지역명 (선택사항)",
    "landmark": "주요 랜드마크 (선택사항)",
    "confidence": 0.0-1.0
}}

위치 정보만 JSON으로 응답하고 다른 설명은 포함하지 마세요.
"""

            response = await self.provider.chat_completion(
                messages=[
                    {"role": "system", "content": "당신은 GPS 좌표를 기반으로 정확한 위치 정보를 제공하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            return self._parse_json_response(response, lat, lon)
            
        except Exception as e:
            logger.error(f"LLM 위치 추정 실패: {str(e)}")
            return {
                "error": f"위치 추정 중 오류가 발생했습니다: {str(e)}",
                "coordinates": None
            }
    
    async def analyze_location_from_image(
        self, 
        image_url: str, 
        exif_data: Optional[Dict] = None
    ) -> Dict:
        """이미지 URL 기반 위치 분석"""
        try:
            prompt = f"""
다음 이미지를 분석하여 위치 정보를 추정해주세요:
이미지 URL: {image_url}

EXIF 데이터:
{self._format_exif_data(exif_data)}

이미지에서 보이는 건물, 풍경, 표지판 등을 바탕으로 위치를 추정해주세요.

다음 JSON 형식으로 응답해주세요:
{{
    "country": "국가명",
    "city": "도시명",
    "region": "지역명 (선택사항)", 
    "landmark": "주요 랜드마크 (선택사항)",
    "confidence": 0.0-1.0,
    "description": "위치 추정 근거 설명"
}}

위치 정보만 JSON으로 응답하고 다른 설명은 포함하지 마세요.
"""

            response = await self.provider.vision_completion(
                messages=[
                    {"role": "system", "content": "당신은 이미지를 분석하여 정확한 위치 정보를 제공하는 전문가입니다."},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]}
                ],
                temperature=0.2,
                max_tokens=300
            )
            
            return self._parse_json_response(response)
            
        except Exception as e:
            logger.error(f"LLM 이미지 위치 추정 실패: {str(e)}")
            return {
                "error": f"이미지 위치 추정 중 오류가 발생했습니다: {str(e)}",
                "coordinates": None
            }
    
    async def recommend_travel_route(
        self, 
        photos: List[Dict], 
        user_preferences: Optional[Dict] = None,
        duration_days: Optional[int] = None
    ) -> Dict:
        """여행 경로 추천"""
        try:
            locations = []
            for photo in photos:
                if photo.get('locationInfo'):
                    locations.append(photo['locationInfo'])
            
            if not locations:
                return {"error": "위치 정보가 없습니다."}
            
            prompt = f"""
다음 위치들을 기반으로 여행 경로를 추천해주세요:

방문할 위치들:
{self._format_locations(locations)}

사용자 선호도:
{self._format_preferences(user_preferences)}

여행 기간: {duration_days or "미정"}일

다음 JSON 형식으로 응답해주세요:
{{
    "route_name": "경로 이름",
    "description": "경로 설명",
    "duration_days": 여행_기간,
    "total_estimated_cost": "예상 비용",
    "best_season": "최적 시기",
    "difficulty_level": "난이도",
    "locations": [
        {{
            "name": "장소명",
            "country": "국가",
            "latitude": 위도,
            "longitude": 경도,
            "visit_order": 방문_순서,
            "stay_days": 체류_일수,
            "description": "장소 설명"
        }}
    ]
}}

경로 정보만 JSON으로 응답하고 다른 설명은 포함하지 마세요.
"""

            response = await self.provider.chat_completion(
                messages=[
                    {"role": "system", "content": "당신은 여행 경로를 추천하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            
            return self._parse_json_response(response)
            
        except Exception as e:
            logger.error(f"경로 추천 실패: {str(e)}")
            return {"error": f"경로 추천 중 오류가 발생했습니다: {str(e)}"}
    
    async def extract_text_from_image(self, image_url: str) -> Dict:
        """이미지에서 텍스트 추출"""
        try:
            prompt = f"""
다음 이미지에서 텍스트를 추출해주세요:
이미지 URL: {image_url}

이미지에서 보이는 모든 텍스트, 표지판, 간판, 메뉴 등을 읽어서 알려주세요.

다음 JSON 형식으로 응답해주세요:
{{
    "extracted_text": ["추출된 텍스트들"],
    "location_clues": ["위치 관련 단서들"],
    "business_names": ["상호명들"],
    "confidence": 0.0-1.0
}}

텍스트 정보만 JSON으로 응답하고 다른 설명은 포함하지 마세요.
"""

            response = await self.provider.vision_completion(
                messages=[
                    {"role": "system", "content": "당신은 이미지에서 텍스트를 추출하는 전문가입니다."},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]}
                ],
                temperature=0.1,
                max_tokens=400
            )
            
            return self._parse_json_response(response)
            
        except Exception as e:
            logger.error(f"텍스트 추출 실패: {str(e)}")
            return {
                "error": f"텍스트 추출 중 오류가 발생했습니다: {str(e)}",
                "extracted_text": [],
                "location_clues": [],
                "business_names": [],
                "confidence": 0.0
            }
    
    def _parse_json_response(self, response: str, lat: Optional[float] = None, lon: Optional[float] = None) -> Dict:
        """JSON 응답 파싱"""
        import json
        try:
            result = response.strip()
            location_data = json.loads(result)
            
            if lat is not None and lon is not None:
                location_data["coordinates"] = {
                    "latitude": lat,
                    "longitude": lon
                }
            
            return location_data
        except json.JSONDecodeError:
            logger.error(f"JSON 파싱 실패: {response}")
            return {
                "error": "응답 파싱에 실패했습니다.",
                "coordinates": {"latitude": lat, "longitude": lon} if lat and lon else None
            }
    
    def _format_exif_data(self, exif_data: Optional[Dict]) -> str:
        """EXIF 데이터 포맷팅"""
        import json
        if exif_data:
            return json.dumps(exif_data, indent=2, ensure_ascii=False)
        return "EXIF 데이터 없음"
    
    def _format_locations(self, locations: List[Dict]) -> str:
        """위치 데이터 포맷팅"""
        import json
        return json.dumps(locations, indent=2, ensure_ascii=False)
    
    def _format_preferences(self, preferences: Optional[Dict]) -> str:
        """선호도 데이터 포맷팅"""
        import json
        if preferences:
            return json.dumps(preferences, indent=2, ensure_ascii=False)
        return "특별한 선호도 없음" 