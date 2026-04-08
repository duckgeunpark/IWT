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
        """JSON 응답 파싱 (Gemini 마크다운 코드블록 포함 처리)"""
        import json
        import re
        try:
            text = response.strip()

            # ```json ... ``` 또는 ``` ... ``` 블록 추출
            code_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if code_block:
                text = code_block.group(1).strip()

            data = json.loads(text)

            if lat is not None and lon is not None:
                data["coordinates"] = {"latitude": lat, "longitude": lon}

            return data
        except json.JSONDecodeError:
            logger.error(f"JSON 파싱 실패: {response}")
            return {
                "error": "응답 파싱에 실패했습니다.",
                "coordinates": {"latitude": lat, "longitude": lon} if lat and lon else None,
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

    # ── 올바른 LLM 역할: 정제된 구조화 데이터 → 자연어 게시글 ──

    async def generate_post_content(self, structured_data: Dict) -> Dict:
        """
        정제·구조화된 여행 데이터를 받아 자연어 게시글 콘텐츠 생성

        LLM은 GPS 분석·경로 계산을 하지 않는다.
        Nominatim + 코드 처리로 완성된 구조화 데이터만 입력으로 받는다.

        Args:
            structured_data: {
                "segments": [{"start_time", "end_time", "duration_hours",
                               "places": [{"name", "city", "country", "stay_minutes"}]}],
                "total_distance_km": float,
                "total_duration_hours": float,
                "photo_count": int,
            }

        Returns:
            {"title", "description", "tags", "photo_comments"}
        """
        import json
        try:
            prompt = f"""
다음은 여행 데이터입니다. 이 데이터를 바탕으로 여행 게시글 콘텐츠를 생성해주세요.

여행 데이터:
{json.dumps(structured_data, ensure_ascii=False, indent=2)}

다음 JSON 형식으로만 응답해주세요. JSON 외 다른 설명은 포함하지 마세요.
{{
    "title": "여행 제목 (20자 이내, 감성적으로)",
    "description": "여행 전체 설명 (150자 이내, 자연스럽게)",
    "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"],
    "photo_comments": [
        {{"place_name": "장소명", "comment": "이 장소에 대한 한줄 감상 (30자 이내)"}}
    ]
}}
"""
            response = await self.provider.chat_completion(
                messages=[
                    {"role": "system", "content": "당신은 여행 게시글을 감성적으로 작성하는 전문 작가입니다. 주어진 데이터를 바탕으로 정확하고 자연스러운 글을 작성합니다."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=600,
            )
            return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"게시글 콘텐츠 생성 실패: {str(e)}")
            return {
                "title": "나의 여행 기록",
                "description": "사진으로 기록한 소중한 여행입니다.",
                "tags": ["여행", "사진"],
                "photo_comments": [],
            }