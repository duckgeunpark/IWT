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

다음 JSON 형식으로만 응답해주세요. JSON 외 다른 설명은 포함하지 마세요.
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
위치 정보가 없는 사진입니다.

다음 JSON 형식으로만 응답해주세요. JSON 외 다른 설명은 포함하지 마세요.
{
    "description": "사진에 대한 간단한 설명 (50자 이내)",
    "tags": ["태그1", "태그2"]
}
"""

        return f"""
다음 사진에 대한 설명을 생성해주세요.

위치: {location_info.landmark or 'Unknown'} ({location_info.city or 'Unknown'}, {location_info.country or 'Unknown'})
좌표: {location_info.coordinates.latitude}, {location_info.coordinates.longitude}

다음 JSON 형식으로만 응답해주세요. JSON 외 다른 설명은 포함하지 마세요.
{{
    "description": "사진에 대한 간단한 설명 (50자 이내)",
    "tags": ["태그1", "태그2"]
}}
"""
    
    def _create_tag_generation_prompt(self, countries: List[str], cities: List[str], landmarks: List[str]) -> str:
        """태그 생성을 위한 프롬프트 생성"""
        return f"""
다음 여행 정보를 바탕으로 적절한 태그들을 생성해주세요.

방문한 국가: {', '.join(countries) if countries else '없음'}
방문한 도시: {', '.join(cities) if cities else '없음'}
방문한 장소: {', '.join(landmarks) if landmarks else '없음'}

태그는 여행의 성격, 방문한 장소, 활동 등을 반영해야 합니다.
다음 JSON 형식으로만 응답해주세요. JSON 외 다른 설명은 포함하지 마세요.
{{
    "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"]
}}
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
    
    async def recommend_attractions(
        self,
        location_info: Dict[str, Any],
        categories: Optional[List[str]] = None,
        max_attractions: int = 5,
    ) -> List[Dict[str, Any]]:
        """특정 지역의 명소 추천"""
        try:
            cat_text = ", ".join(categories) if categories else "전반적인 관광"
            prompt = f"""
다음 지역의 명소를 추천해주세요.

지역 정보: {json.dumps(location_info, ensure_ascii=False)}
추천 카테고리: {cat_text}
추천 개수: {max_attractions}개

다음 JSON 형식으로만 응답해주세요. JSON 외 다른 설명은 포함하지 마세요.
{{
    "attractions": [
        {{
            "name": "명소명",
            "category": "카테고리",
            "description": "간단한 설명 (50자 이내)",
            "estimated_duration_hours": 1.5
        }}
    ]
}}
"""
            response = await self.llm.provider.chat_completion(
                messages=[
                    {"role": "system", "content": "당신은 여행 명소를 추천하는 전문가입니다. 실제 존재하는 유명 명소만 추천합니다."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            data = self._parse_llm_json(response)
            return data.get("attractions", [])
        except Exception as e:
            logger.error(f"명소 추천 실패: {str(e)}")
            return []

    async def generate_travel_itinerary(
        self,
        route_data: Dict[str, Any],
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        구조화된 경로 데이터 → 상세 여행 일정 텍스트 생성
        (블로그 생성에도 재사용)
        마지막 줄에 <!-- tags: 태그1, 태그2 --> 형식으로 태그 포함
        """
        try:
            pref_text = json.dumps(user_preferences, ensure_ascii=False) if user_preferences else "없음"
            prompt = route_data.get("prompt") or f"""
다음 여행 사진 데이터를 바탕으로 여행 기록을 마크다운 형식으로 작성해주세요.

경로 데이터:
{json.dumps(route_data, ensure_ascii=False, indent=2)}

사용자 선호도: {pref_text}

요구사항:
1. 첫 줄은 반드시 # 으로 시작하는 제목. 제목은 방문 지역과 여행 특징이 담긴 구체적인 제목으로 작성 (예: "도쿄 3박 4일, 신주쿠에서 아사쿠사까지" / "제주 당일치기 올레길 트레킹" / "오사카 먹방 여행 2박 3일")
2. GPS가 있는 경우 방문 장소별로 일정을 구성하고 이동 경로를 자연스럽게 서술
3. 감성적이고 여행 블로그 스타일의 자연스러운 한국어 문체
4. 마크다운 형식 (소제목, 목록, 강조 활용)
5. 마지막 줄에 반드시 아래 형식으로 태그를 포함:
<!-- tags: 태그1, 태그2, 태그3, 태그4, 태그5 -->
태그는 국가/도시명, 여행 테마(맛집/힐링/액티비티 등), 계절감 등 5~8개 포함
"""
            response = await self.llm.provider.chat_completion(
                messages=[
                    {"role": "system", "content": "당신은 여행 일정을 감성적으로 작성하는 전문 여행 작가입니다. 구체적인 제목과 태그를 반드시 포함합니다."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=1200,
            )
            return response
        except Exception as e:
            logger.error(f"여행 일정 생성 실패: {str(e)}")
            return "여행 일정을 생성할 수 없습니다."

    async def select_highlight_photos(
        self,
        photos: List[Dict[str, Any]],
        max_highlights: int = 5,
    ) -> List[str]:
        """
        사진 메타데이터를 분석하여 하이라이트 사진 ID 목록 반환
        GPS 다양성, 촬영 시간 분포, 파일 크기(화질 프록시)를 고려
        """
        try:
            if not photos:
                return []
            if len(photos) <= max_highlights:
                return [str(p["id"]) for p in photos]

            # GPS 있는 사진 우선 선별
            gps_photos = [p for p in photos if p.get("gps")]
            no_gps_photos = [p for p in photos if not p.get("gps")]

            # GPS 사진이 충분하면 LLM으로 선별
            if gps_photos:
                prompt = f"""다음 여행 사진 목록에서 여행 기록에 가장 대표적인 사진 {max_highlights}장을 선택해주세요.

사진 목록:
{json.dumps(gps_photos, ensure_ascii=False, indent=2)}

선택 기준:
1. GPS 위치 다양성 (다른 장소 우선)
2. 촬영 시간 분포 (여행 전체를 골고루 커버)
3. 파일 크기가 클수록 화질 좋은 사진으로 간주
4. 정확히 {max_highlights}개의 id를 선택

반드시 아래 JSON 형식으로만 응답하세요:
{{"highlighted_ids": ["id1", "id2", "id3"]}}"""

                response = await self.llm.provider.chat_completion(
                    messages=[
                        {"role": "system", "content": "당신은 여행 사진을 분석하여 대표 사진을 선별하는 전문가입니다."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=200,
                )
                data = self._parse_llm_json(response)
                ids = data.get("highlighted_ids", [])
                if ids:
                    return [str(i) for i in ids[:max_highlights]]

            # 폴백: 파일 크기 기준 + 시간 분포 기반 단순 선별
            sorted_photos = sorted(photos, key=lambda p: p.get("file_size", 0), reverse=True)
            return [str(p["id"]) for p in sorted_photos[:max_highlights]]

        except Exception as e:
            logger.error(f"하이라이트 사진 선별 실패: {str(e)}")
            # 폴백: 처음 N장
            return [str(p["id"]) for p in photos[:max_highlights]]

    async def generate_tags_from_content(
        self,
        locations: List[Dict[str, Any]],
        content: str = "",
    ) -> List[str]:
        """
        위치 정보 + 콘텐츠 텍스트에서 태그 생성
        """
        try:
            loc_summary = []
            for loc in locations:
                parts = [v for v in [loc.get("country"), loc.get("city"), loc.get("landmark")] if v]
                if parts:
                    loc_summary.append(", ".join(parts))

            content_preview = content[:300] if content else ""

            prompt = f"""다음 여행 정보를 바탕으로 태그를 생성해주세요.

방문 장소:
{chr(10).join(f"- {s}" for s in loc_summary) if loc_summary else "위치 정보 없음"}

내용 미리보기:
{content_preview}

아래 JSON 형식으로만 응답하세요. 태그는 국가/도시명, 여행 테마, 계절감 등 5~8개:
{{"tags": ["태그1", "태그2", "태그3"]}}"""

            response = await self.llm.provider.chat_completion(
                messages=[
                    {"role": "system", "content": "당신은 여행 콘텐츠에서 검색 가능한 태그를 생성하는 전문가입니다."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=150,
            )
            data = self._parse_llm_json(response)
            return data.get("tags", ["여행"])
        except Exception as e:
            logger.error(f"태그 생성 실패: {str(e)}")
            return ["여행"]

    async def get_category_recommendations(
        self,
        categories: List[str],
        location_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """카테고리 기반 여행 추천"""
        try:
            loc_text = json.dumps(location_info, ensure_ascii=False) if location_info else "미지정"
            prompt = f"""
다음 카테고리와 지역을 기반으로 여행 추천 정보를 제공해주세요.

카테고리: {', '.join(categories)}
지역: {loc_text}

다음 JSON 형식으로만 응답해주세요. JSON 외 다른 설명은 포함하지 마세요.
{{
    "recommendations": [
        {{
            "category": "카테고리명",
            "places": ["장소1", "장소2"],
            "tips": "이 카테고리 여행 팁 (50자 이내)"
        }}
    ],
    "overall_tip": "전체 여행 팁"
}}
"""
            response = await self.llm.provider.chat_completion(
                messages=[
                    {"role": "system", "content": "당신은 카테고리별 여행 정보를 제공하는 전문가입니다."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=400,
            )
            return self._parse_llm_json(response)
        except Exception as e:
            logger.error(f"카테고리 추천 실패: {str(e)}")
            return {"recommendations": [], "overall_tip": ""}

    def _parse_llm_json(self, response: str) -> Dict[str, Any]:
        """LLM JSON 응답 파싱 (마크다운 코드블록 포함 처리)"""
        import re
        try:
            text = response.strip()
            block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if block:
                text = block.group(1).strip()
            return json.loads(text)
        except json.JSONDecodeError:
            logger.error(f"JSON 파싱 실패: {response}")
            return {}

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