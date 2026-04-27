"""
LLM 기반 경로 추천 서비스 (LangChain LCEL 기반)
카테고리(국가/도시/테마)별 DB 정보+LLM 기반 여행 경로/루트 추천
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.services.llm_factory import get_default_llm
from app.services.utils import parse_llm_json
from app.schemas.photo import PhotoData, LocationInfo

logger = logging.getLogger(__name__)

# ── 프롬프트 템플릿 ──────────────────────────────────────────────────

_TRAVEL_SUMMARY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 여행 사진을 분석하여 여행 요약을 생성하는 전문가입니다."),
    ("human", """여행 사진들을 분석하여 여행 요약을 생성해주세요.

방문한 장소들:
{location_text}

다음 JSON 형식으로만 응답해주세요. JSON 외 다른 설명은 포함하지 마세요.
{{
    "title": "여행 제목 (간결하고 매력적으로)",
    "description": "여행에 대한 간단한 설명 (100자 이내)",
    "tags": ["태그1", "태그2", "태그3"],
    "route_summary": "여행 경로에 대한 간단한 설명"
}}"""),
])

_PHOTO_DESC_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 사진을 분석하여 설명을 생성하는 전문가입니다."),
    ("human", """다음 사진에 대한 설명을 생성해주세요.

위치: {landmark} ({city}, {country})
좌표: {lat}, {lon}

다음 JSON 형식으로만 응답해주세요. JSON 외 다른 설명은 포함하지 마세요.
{{
    "description": "사진에 대한 간단한 설명 (50자 이내)",
    "tags": ["태그1", "태그2"]
}}"""),
])

_TAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 여행 사진을 분석하여 태그를 생성하는 전문가입니다."),
    ("human", """다음 여행 정보를 바탕으로 적절한 태그들을 생성해주세요.

방문한 국가: {countries}
방문한 도시: {cities}
방문한 장소: {landmarks}

태그는 여행의 성격, 방문한 장소, 활동 등을 반영해야 합니다.
다음 JSON 형식으로만 응답해주세요. JSON 외 다른 설명은 포함하지 마세요.
{{"tags": ["태그1", "태그2", "태그3", "태그4", "태그5"]}}"""),
])

_ATTRACTIONS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 여행 명소를 추천하는 전문가입니다. 실제 존재하는 유명 명소만 추천합니다."),
    ("human", """다음 지역의 명소를 추천해주세요.

지역 정보: {location_info_text}
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
}}"""),
])

_ITINERARY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 여행 경험을 감성적으로 기록하는 한국어 여행 블로거입니다."),
    ("human", """{prompt_text}"""),
])

_CLUSTER_PARAGRAPH_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 실제 여행 경험을 생생하게 기록하는 한국어 여행 블로거입니다."),
    ("human", """아래 여행 장소 정보를 바탕으로 여행 블로그 단락을 마크다운으로 작성해주세요.

{context_lines}

작성 규칙:
1. 첫 줄: ## 장소명 (소제목)
2. 본문: 2~3개 문단, 총 350~700자
3. 장소의 분위기·특징·인상을 생생하게 묘사 (실제 여행자 시점)
4. 자연스럽고 감성적인 한국어 블로그 문체
5. 소제목(##) 외 다른 마크다운 헤딩(#, ###) 사용 금지
6. 마크다운 이미지 문법(![이미지](URL))을 절대 임의로 생성하지 마세요.
7. 장소 유형(카페·신사·거리·역·공원·시장 등)을 유추해 현장감 있는 묘사 추가
8. 방문자가 실제로 느낄 법한 소소한 디테일(냄새·소리·분위기·계절감·사람들) 포함
9. 이 단락의 첫 문장 시작 방식을 다양하게 (질문형·감탄형·묘사형·회상형 중 하나 선택)"""),
])

_HIGHLIGHT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 여행 사진을 분석하여 대표 사진을 선별하는 전문가입니다."),
    ("human", """다음 여행 사진 목록에서 여행 기록에 가장 대표적인 사진 {max_highlights}장을 선택해주세요.

사진 목록:
{photos_text}

선택 기준:
1. GPS 위치 다양성 (다른 장소 우선)
2. 촬영 시간 분포 (여행 전체를 골고루 커버)
3. 파일 크기가 클수록 화질 좋은 사진으로 간주
4. 정확히 {max_highlights}개의 id를 선택

반드시 아래 JSON 형식으로만 응답하세요:
{{"highlighted_ids": ["id1", "id2", "id3"]}}"""),
])

_TAGS_FROM_CONTENT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "여행 콘텐츠에서 검색 최적화 태그를 추출합니다. JSON만 출력합니다."),
    ("human", """다음 여행 정보를 바탕으로 태그를 생성해주세요.

방문 장소:
{loc_summary_text}

내용 미리보기:
{content_preview}

아래 JSON 형식으로만 응답하세요. 태그는 국가/도시명, 여행 테마, 계절감 등 5~8개:
{{"tags": ["태그1", "태그2", "태그3"]}}"""),
])

_CATEGORY_RECOMMEND_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "당신은 카테고리별 여행 정보를 제공하는 전문가입니다."),
    ("human", """다음 카테고리와 지역을 기반으로 여행 추천 정보를 제공해주세요.

카테고리: {categories_text}
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
}}"""),
])


class LLMRouteRecommendService:
    """LLM 기반 경로 추천 서비스 (LCEL)"""

    def __init__(self):
        llm = get_default_llm()
        parser = StrOutputParser()
        self._summary_chain    = _TRAVEL_SUMMARY_PROMPT    | llm | parser
        self._photo_desc_chain = _PHOTO_DESC_PROMPT        | llm | parser
        self._tag_chain        = _TAG_PROMPT               | llm | parser
        self._attractions_chain = _ATTRACTIONS_PROMPT      | llm | parser
        self._itinerary_chain  = _ITINERARY_PROMPT         | llm | parser
        self._cluster_chain    = _CLUSTER_PARAGRAPH_PROMPT | llm | parser
        self._highlight_chain  = _HIGHLIGHT_PROMPT         | llm | parser
        self._tags_chain       = _TAGS_FROM_CONTENT_PROMPT | llm | parser
        self._category_chain   = _CATEGORY_RECOMMEND_PROMPT| llm | parser

    async def generate_travel_summary(self, photos: List[PhotoData]) -> Dict[str, Any]:
        """여러 사진 기반 여행 요약 생성"""
        try:
            sorted_photos = sorted(
                photos,
                key=lambda x: x.exif_data.get("datetime") if x.exif_data else datetime.min,
            )
            locations = []
            for photo in sorted_photos:
                if photo.location_info and photo.location_info.coordinates:
                    locations.append({
                        "landmark": photo.location_info.landmark,
                        "city": photo.location_info.city,
                        "country": photo.location_info.country,
                    })
            if not locations:
                return {
                    "title": "여행 기록",
                    "description": "사진으로 기록한 여행입니다.",
                    "tags": ["여행", "사진"],
                    "route_summary": "위치 정보가 없어 경로를 추정할 수 없습니다.",
                }

            location_text = "\n".join(
                f"- {loc.get('landmark', 'Unknown')} ({loc.get('city', 'Unknown')}, {loc.get('country', 'Unknown')})"
                for loc in locations
            )
            raw = await self._summary_chain.ainvoke({"location_text": location_text})
            return parse_llm_json(raw) or {
                "title": "여행 기록",
                "description": "사진으로 기록한 여행입니다.",
                "tags": ["여행", "사진"],
                "route_summary": "경로를 분석했습니다.",
            }
        except Exception as e:
            logger.error(f"여행 요약 생성 실패: {e}")
            return {"title": "여행 기록", "description": "여행 사진을 업로드했습니다.", "tags": ["여행", "사진"], "route_summary": ""}

    async def generate_photo_descriptions(self, photos: List[PhotoData]) -> List[Dict[str, Any]]:
        """각 사진에 대한 자동 설명 생성"""
        descriptions = []
        for photo in photos:
            if not photo.location_info or not photo.location_info.coordinates:
                descriptions.append({"file_key": photo.file_key, "description": "위치 정보가 없는 사진입니다.", "tags": ["사진"]})
                continue
            try:
                loc = photo.location_info
                raw = await self._photo_desc_chain.ainvoke({
                    "landmark": loc.landmark or "Unknown",
                    "city": loc.city or "Unknown",
                    "country": loc.country or "Unknown",
                    "lat": loc.coordinates.latitude,
                    "lon": loc.coordinates.longitude,
                })
                data = parse_llm_json(raw)
                descriptions.append({
                    "file_key": photo.file_key,
                    "description": data.get("description", "사진입니다."),
                    "tags": data.get("tags", ["사진"]),
                })
            except Exception as e:
                logger.error(f"사진 설명 생성 실패: {e}")
                descriptions.append({"file_key": photo.file_key, "description": "사진입니다.", "tags": ["사진"]})
        return descriptions

    async def generate_travel_tags(self, photos: List[PhotoData]) -> List[str]:
        """여행 사진 기반 자동 태깅"""
        try:
            countries, cities, landmarks = set(), set(), set()
            for photo in photos:
                if photo.location_info:
                    if photo.location_info.country: countries.add(photo.location_info.country)
                    if photo.location_info.city: cities.add(photo.location_info.city)
                    if photo.location_info.landmark: landmarks.add(photo.location_info.landmark)

            raw = await self._tag_chain.ainvoke({
                "countries": ", ".join(countries) or "없음",
                "cities": ", ".join(cities) or "없음",
                "landmarks": ", ".join(landmarks) or "없음",
            })
            data = parse_llm_json(raw)
            return data.get("tags", ["여행", "사진"])
        except Exception as e:
            logger.error(f"태그 생성 실패: {e}")
            return ["여행", "사진"]

    def analyze_travel_route(self, photos: List[PhotoData]) -> Dict[str, Any]:
        """여행 경로 분석 (LLM 없이 계산 기반)"""
        route_points = []
        for photo in photos:
            if photo.location_info and photo.location_info.coordinates:
                route_points.append({
                    "latitude": photo.location_info.coordinates.latitude,
                    "longitude": photo.location_info.coordinates.longitude,
                    "timestamp": photo.exif_data.get("datetime") if photo.exif_data else None,
                    "landmark": photo.location_info.landmark,
                    "city": photo.location_info.city,
                    "country": photo.location_info.country,
                })
        if len(route_points) < 2:
            return {"route_type": "single_location", "total_distance": 0, "duration": None, "route_points": route_points}

        total_distance = self._calculate_total_distance(route_points)
        duration = self._calculate_travel_duration(route_points)
        return {
            "route_type": "multi_location",
            "total_distance": total_distance,
            "duration": duration,
            "route_points": route_points,
            "start_location": route_points[0],
            "end_location": route_points[-1],
        }

    async def recommend_attractions(
        self,
        location_info: Dict[str, Any],
        categories: Optional[List[str]] = None,
        max_attractions: int = 5,
    ) -> List[Dict[str, Any]]:
        """특정 지역의 명소 추천"""
        try:
            raw = await self._attractions_chain.ainvoke({
                "location_info_text": json.dumps(location_info, ensure_ascii=False),
                "cat_text": ", ".join(categories) if categories else "전반적인 관광",
                "max_attractions": max_attractions,
            })
            data = parse_llm_json(raw)
            return data.get("attractions", [])
        except Exception as e:
            logger.error(f"명소 추천 실패: {e}")
            return []

    async def generate_travel_itinerary(
        self,
        route_data: Dict[str, Any],
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> str:
        """구조화된 경로 데이터 → 상세 여행 일정 텍스트 생성"""
        try:
            if route_data.get("prompt"):
                prompt_text = route_data["prompt"]
            else:
                photos = route_data.get("photos", [])
                locations = route_data.get("locations", [])
                loc_lines = []
                for loc in locations:
                    parts = [loc.get("name"), loc.get("time")]
                    coords = loc.get("coordinates", {})
                    if coords.get("lat"):
                        parts.append(f"({coords['lat']:.4f}, {coords['lng']:.4f})")
                    loc_lines.append("- " + " | ".join(p for p in parts if p))

                prompt_text = f"""다음 여행 데이터를 바탕으로 여행 기록을 마크다운으로 작성해주세요.

총 사진: {len(photos)}장
방문 장소:
{chr(10).join(loc_lines) if loc_lines else "- 위치 정보 없음"}

작성 규칙:
1. 첫 줄: # 제목 (방문 지역과 여행 특징 포함)
2. 장소별 ## 소제목으로 구분, 각 장소당 2~3문단
3. 실제 여행자 시점의 감성적인 한국어 블로그 문체
4. 장소별 문단이 단순 나열이 되지 않도록 감정 변화·날씨·음식·소소한 에피소드 등 맥락 삽입
5. 각 ## 섹션의 첫 문장 시작 방식을 다양하게 (질문형, 감탄형, 묘사형, 회상형 등)
6. 마크다운 이미지 문법(![이미지](URL))을 절대 임의로 생성하지 마세요.
7. 마지막 줄: <!-- tags: 태그1, 태그2, 태그3 --> (국가/도시명, 여행 테마 5~8개)"""

            return await self._itinerary_chain.ainvoke({"prompt_text": prompt_text})
        except Exception as e:
            logger.error(f"여행 일정 생성 실패: {e}")
            return "여행 일정을 생성할 수 없습니다."

    async def generate_cluster_paragraph(
        self,
        cluster: Dict[str, Any],
        location_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """단일 위치 클러스터 → 마크다운 단락 생성"""
        try:
            location_name = "알 수 없는 장소"
            location_details = []
            if location_info:
                landmark = location_info.get("landmark") or location_info.get("region")
                city     = location_info.get("city")
                country  = location_info.get("country")
                address  = location_info.get("address") or location_info.get("display_name")
                name_parts = [p for p in [landmark, city, country] if p]
                location_name = ", ".join(name_parts) if name_parts else location_name
                if address: location_details.append(f"주소: {address}")
                if city and country: location_details.append(f"도시: {city}, {country}")

            photo_count = cluster.get("photo_count", len(cluster.get("photos", [])))
            visit_time  = self._format_visit_time(cluster.get("start_time", ""), cluster.get("end_time", ""))

            context_lines = [f"- 장소: {location_name}"]
            context_lines += [f"- {d}" for d in location_details]
            context_lines.append(f"- 촬영 사진: {photo_count}장")
            if visit_time:
                context_lines.append(f"- 방문 시간대: {visit_time}")

            return await self._cluster_chain.ainvoke({"context_lines": "\n".join(context_lines)}) or ""
        except Exception as e:
            logger.error(f"클러스터 단락 생성 실패: {e}")
            return ""

    async def select_highlight_photos(
        self,
        photos: List[Dict[str, Any]],
        max_highlights: int = 5,
    ) -> List[str]:
        """하이라이트 사진 ID 목록 반환 (GPS 다양성 + 시간 분포 + 화질)"""
        try:
            if not photos:
                return []
            if len(photos) <= max_highlights:
                return [str(p["id"]) for p in photos]

            gps_photos = [p for p in photos if p.get("gps")]
            if gps_photos:
                raw = await self._highlight_chain.ainvoke({
                    "photos_text": json.dumps(gps_photos, ensure_ascii=False, indent=2),
                    "max_highlights": max_highlights,
                })
                data = parse_llm_json(raw)
                ids = data.get("highlighted_ids", [])
                if ids:
                    return [str(i) for i in ids[:max_highlights]]

            sorted_photos = sorted(photos, key=lambda p: p.get("file_size", 0), reverse=True)
            return [str(p["id"]) for p in sorted_photos[:max_highlights]]
        except Exception as e:
            logger.error(f"하이라이트 사진 선별 실패: {e}")
            return [str(p["id"]) for p in photos[:max_highlights]]

    async def generate_tags_from_content(
        self,
        locations: List[Dict[str, Any]],
        content: str = "",
    ) -> List[str]:
        """위치 정보 + 콘텐츠 텍스트에서 태그 생성"""
        try:
            loc_summary = []
            for loc in locations:
                parts = [v for v in [loc.get("country"), loc.get("city"), loc.get("landmark")] if v]
                if parts:
                    loc_summary.append(", ".join(parts))

            raw = await self._tags_chain.ainvoke({
                "loc_summary_text": "\n".join(f"- {s}" for s in loc_summary) if loc_summary else "위치 정보 없음",
                "content_preview": content[:300],
            })
            data = parse_llm_json(raw)
            return data.get("tags", ["여행"])
        except Exception as e:
            logger.error(f"태그 생성 실패: {e}")
            return ["여행"]

    async def get_category_recommendations(
        self,
        categories: List[str],
        location_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """카테고리 기반 여행 추천"""
        try:
            raw = await self._category_chain.ainvoke({
                "categories_text": ", ".join(categories),
                "loc_text": json.dumps(location_info, ensure_ascii=False) if location_info else "미지정",
            })
            return parse_llm_json(raw)
        except Exception as e:
            logger.error(f"카테고리 추천 실패: {e}")
            return {"recommendations": [], "overall_tip": ""}

    # ── 헬퍼 ────────────────────────────────────────────────────────

    def _format_visit_time(self, start: str, end: str) -> str:
        try:
            from datetime import datetime as dt
            fmts = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"]
            def parse(s):
                for f in fmts:
                    try: return dt.strptime(s[:19], f[:19])
                    except ValueError: continue
                return None
            def label(d):
                h = d.hour
                if h < 6:   return f"새벽 {d.strftime('%H:%M')}"
                if h < 12:  return f"오전 {d.strftime('%H:%M')}"
                if h < 14:  return f"점심 {d.strftime('%H:%M')}"
                if h < 18:  return f"오후 {d.strftime('%H:%M')}"
                return f"저녁 {d.strftime('%H:%M')}"
            s = parse(start) if start else None
            e = parse(end) if end else None
            if s and e:
                delta_min = int((e - s).total_seconds() / 60)
                duration = f"{delta_min // 60}시간 {delta_min % 60}분" if delta_min >= 60 else f"{delta_min}분"
                return f"{label(s)} ~ {label(e)} (약 {duration})"
            if s: return label(s)
            return ""
        except Exception:
            return ""

    def _calculate_total_distance(self, route_points: List[Dict[str, Any]]) -> float:
        total = 0.0
        for i in range(len(route_points) - 1):
            p1, p2 = route_points[i], route_points[i + 1]
            total += ((p2["latitude"] - p1["latitude"]) ** 2 + (p2["longitude"] - p1["longitude"]) ** 2) ** 0.5
        return total

    def _calculate_travel_duration(self, route_points: List[Dict[str, Any]]) -> Optional[str]:
        timestamps = [p.get("timestamp") for p in route_points if p.get("timestamp")]
        if len(timestamps) < 2:
            return None
        try:
            start_time = min(timestamps)
            end_time   = max(timestamps)
            days = (end_time - start_time).days
            if days == 0:
                return f"{(end_time - start_time).seconds // 3600}시간"
            return f"{days}일"
        except Exception:
            return None


# 서비스 싱글톤
llm_route_service = LLMRouteRecommendService()
