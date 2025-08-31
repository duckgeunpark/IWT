"""
LLM 기반 경로 추천 서비스
카테고리(국가/도시/테마)별 DB 정보+LLM 기반 여행 경로/루트 추천
"""

from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import json

from app.services.llm_factory import get_llm_service
from app.schemas.photo import PhotoData, LocationInfo

logger = logging.getLogger(__name__)

class LLMRouteRecommendService:
    def __init__(self):
        self.llm = get_llm_service()
    
    async def generate_travel_summary(self, photos: List[PhotoData]) -> Dict[str, Any]:
        """
        여러 사진을 기반으로 여행 요약 생성
        """
        try:
            # 사진들을 촬영 시간순으로 정렬
            sorted_photos = sorted(photos, key=lambda x: x.exif_data.get("datetime") if x.exif_data else datetime.min)
            
            # 위치 정보 추출
            locations = []
            for photo in sorted_photos:
                if photo.location_info and photo.location_info.coordinates:
                    locations.append({
                        "latitude": photo.location_info.coordinates.latitude,
                        "longitude": photo.location_info.coordinates.longitude,
                        "landmark": photo.location_info.landmark,
                        "city": photo.location_info.city,
                        "country": photo.location_info.country,
                        "datetime": photo.exif_data.get("datetime") if photo.exif_data else None
                    })
            
            if not locations:
                return {
                    "title": "여행 기록",
                    "description": "사진으로 기록한 여행입니다.",
                    "tags": ["여행", "사진"],
                    "route_summary": "위치 정보가 없어 경로를 추정할 수 없습니다."
                }
            
            # LLM을 통한 여행 요약 생성
            prompt = self._create_travel_summary_prompt(locations)
            response = await self.llm.provider.chat_completion(
                messages=[
                    {"role": "system", "content": "당신은 여행 사진을 분석하여 여행 요약을 생성하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            # 응답 파싱
            try:
                summary_data = json.loads(response)
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 기본 형식으로 반환
                summary_data = {
                    "title": "여행 기록",
                    "description": response[:200] + "..." if len(response) > 200 else response,
                    "tags": ["여행", "사진"],
                    "route_summary": "여행 경로를 분석했습니다."
                }
            
            return summary_data
            
        except Exception as e:
            logger.error(f"여행 요약 생성 실패: {str(e)}")
            return {
                "title": "여행 기록",
                "description": "여행 사진을 업로드했습니다.",
                "tags": ["여행", "사진"],
                "route_summary": "여행 경로 분석 중 오류가 발생했습니다."
            }
    
    async def generate_photo_descriptions(self, photos: List[PhotoData]) -> List[Dict[str, Any]]:
        """
        각 사진에 대한 자동 설명 생성
        """
        try:
            descriptions = []
            
            for photo in photos:
                if not photo.location_info or not photo.location_info.coordinates:
                    descriptions.append({
                        "file_key": photo.file_key,
                        "description": "위치 정보가 없는 사진입니다.",
                        "tags": ["사진"]
                    })
                    continue
                
                # 개별 사진 설명 생성
                prompt = self._create_photo_description_prompt(photo)
                response = await self.llm.provider.chat_completion(
                    messages=[
                        {"role": "system", "content": "당신은 사진을 분석하여 설명을 생성하는 전문가입니다."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=300
                )
                
                try:
                    photo_data = json.loads(response)
                except json.JSONDecodeError:
                    photo_data = {
                        "description": response[:100] + "..." if len(response) > 100 else response,
                        "tags": ["사진"]
                    }
                
                descriptions.append({
                    "file_key": photo.file_key,
                    "description": photo_data.get("description", "사진입니다."),
                    "tags": photo_data.get("tags", ["사진"])
                })
            
            return descriptions
            
        except Exception as e:
            logger.error(f"사진 설명 생성 실패: {str(e)}")
            return []
    
    async def generate_travel_tags(self, photos: List[PhotoData]) -> List[str]:
        """
        여행 사진들을 기반으로 자동 태깅
        """
        try:
            # 위치 정보 수집
            countries = set()
            cities = set()
            landmarks = set()
            
            for photo in photos:
                if photo.location_info:
                    if photo.location_info.country:
                        countries.add(photo.location_info.country)
                    if photo.location_info.city:
                        cities.add(photo.location_info.city)
                    if photo.location_info.landmark:
                        landmarks.add(photo.location_info.landmark)
            
            # LLM을 통한 태그 생성
            prompt = self._create_tag_generation_prompt(list(countries), list(cities), list(landmarks))
            response = await self.llm.provider.chat_completion(
                messages=[
                    {"role": "system", "content": "당신은 여행 사진을 분석하여 태그를 생성하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            try:
                tags_data = json.loads(response)
                return tags_data.get("tags", ["여행", "사진"])
            except json.JSONDecodeError:
                # 기본 태그 반환
                basic_tags = ["여행", "사진"]
                if countries:
                    basic_tags.extend(list(countries))
                if cities:
                    basic_tags.extend(list(cities))
                return basic_tags
                
        except Exception as e:
            logger.error(f"태그 생성 실패: {str(e)}")
            return ["여행", "사진"]
    
    async def analyze_travel_route(self, photos: List[PhotoData]) -> Dict[str, Any]:
        """
        여행 경로 분석 및 시각화 데이터 생성
        """
        try:
            # 시간순으로 정렬된 위치 정보
            route_points = []
            
            for photo in photos:
                if photo.location_info and photo.location_info.coordinates:
                    route_points.append({
                        "latitude": photo.location_info.coordinates.latitude,
                        "longitude": photo.location_info.coordinates.longitude,
                        "timestamp": photo.exif_data.get("datetime") if photo.exif_data else None,
                        "landmark": photo.location_info.landmark,
                        "city": photo.location_info.city,
                        "country": photo.location_info.country
                    })
            
            if len(route_points) < 2:
                return {
                    "route_type": "single_location",
                    "total_distance": 0,
                    "duration": None,
                    "route_points": route_points
                }
            
            # 경로 분석
            total_distance = self._calculate_total_distance(route_points)
            duration = self._calculate_travel_duration(route_points)
            
            return {
                "route_type": "multi_location" if len(route_points) > 1 else "single_location",
                "total_distance": total_distance,
                "duration": duration,
                "route_points": route_points,
                "start_location": route_points[0] if route_points else None,
                "end_location": route_points[-1] if route_points else None
            }
            
        except Exception as e:
            logger.error(f"여행 경로 분석 실패: {str(e)}")
            return {
                "route_type": "unknown",
                "total_distance": 0,
                "duration": None,
                "route_points": []
            }
    
    def _create_travel_summary_prompt(self, locations: List[Dict[str, Any]]) -> str:
        """여행 요약 생성을 위한 프롬프트 생성"""
        location_text = "\n".join([
            f"- {loc.get('landmark', 'Unknown')} ({loc.get('city', 'Unknown')}, {loc.get('country', 'Unknown')})"
            for loc in locations
        ])
        
        return f"""
여행 사진들을 분석하여 여행 요약을 생성해주세요.

방문한 장소들:
{location_text}

다음 JSON 형식으로 응답해주세요:
{{
    "title": "여행 제목 (간결하고 매력적으로)",
    "description": "여행에 대한 간단한 설명 (100자 이내)",
    "tags": ["태그1", "태그2", "태그3"],
    "route_summary": "여행 경로에 대한 간단한 설명"
}}
"""
    
    def _create_photo_description_prompt(self, photo: PhotoData) -> str:
        """개별 사진 설명 생성을 위한 프롬프트 생성"""
        location_info = photo.location_info
        
        if not location_info or not location_info.coordinates:
            return """
다음 사진에 대한 설명을 생성해주세요:

위치 정보가 없는 사진입니다.

다음 JSON 형식으로 응답해주세요:
{
    "description": "사진에 대한 간단한 설명 (50자 이내)",
    "tags": ["태그1", "태그2"]
}
"""
        
        return f"""
다음 사진에 대한 설명을 생성해주세요:

위치: {location_info.landmark or 'Unknown'} ({location_info.city or 'Unknown'}, {location_info.country or 'Unknown'})
좌표: {location_info.coordinates.latitude}, {location_info.coordinates.longitude}

다음 JSON 형식으로 응답해주세요:
{{
    "description": "사진에 대한 간단한 설명 (50자 이내)",
    "tags": ["태그1", "태그2"]
}}
"""
    
    def _create_tag_generation_prompt(self, countries: List[str], cities: List[str], landmarks: List[str]) -> str:
        """태그 생성을 위한 프롬프트 생성"""
        return f"""
다음 여행 정보를 바탕으로 적절한 태그들을 생성해주세요:

방문한 국가: {', '.join(countries) if countries else '없음'}
방문한 도시: {', '.join(cities) if cities else '없음'}
방문한 장소: {', '.join(landmarks) if landmarks else '없음'}

다음 JSON 형식으로 응답해주세요:
{{
    "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"]
}}

태그는 여행의 성격, 방문한 장소, 활동 등을 반영해야 합니다.
"""
    
    def _calculate_total_distance(self, route_points: List[Dict[str, Any]]) -> float:
        """총 이동 거리 계산 (간단한 유클리드 거리)"""
        if len(route_points) < 2:
            return 0.0
        
        total_distance = 0.0
        for i in range(len(route_points) - 1):
            point1 = route_points[i]
            point2 = route_points[i + 1]
            
            # 간단한 유클리드 거리 계산 (실제로는 Haversine 공식 사용 권장)
            lat1, lon1 = point1["latitude"], point1["longitude"]
            lat2, lon2 = point2["latitude"], point2["longitude"]
            
            distance = ((lat2 - lat1) ** 2 + (lon2 - lon1) ** 2) ** 0.5
            total_distance += distance
        
        return total_distance
    
    def _calculate_travel_duration(self, route_points: List[Dict[str, Any]]) -> Optional[str]:
        """여행 기간 계산"""
        timestamps = [point.get("timestamp") for point in route_points if point.get("timestamp")]
        
        if len(timestamps) < 2:
            return None
        
        try:
            start_time = min(timestamps)
            end_time = max(timestamps)
            
            duration = end_time - start_time
            days = duration.days
            
            if days == 0:
                hours = duration.seconds // 3600
                return f"{hours}시간"
            elif days == 1:
                return "1일"
            else:
                return f"{days}일"
        except:
            return None 