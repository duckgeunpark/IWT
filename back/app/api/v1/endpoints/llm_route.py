from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Optional, Dict, Any
import logging
import re

from app.core.rate_limit import limiter
from app.services.llm_location_search import LLMLocationSearchService
from app.services.llm_route_recommend import LLMRouteRecommendService
from app.services.ocr_augmenter import OCRAugmenterService
from app.core.auth import get_current_user
from app.core.cache import cache_get, cache_set
from app.schemas.llm import (
    LocationEstimateRequest,
    LocationEstimateResponse,
    OCREnhanceRequest,
    OCREnhanceResponse,
    RouteRecommendRequest,
    RouteRecommendResponse,
    AttractionsRequest,
    AttractionsResponse,
    ItineraryRequest,
    ItineraryResponse,
    CategoryRecommendationsRequest,
    CategoryRecommendationsResponse,
    BlogGenerateRequest,
    BlogGenerateResponse,
    HighlightPhotosRequest,
    HighlightPhotosResponse,
    TagGenerateRequest,
    TagGenerateResponse,
)

router = APIRouter(prefix="/llm", tags=["llm"])

# 서비스 인스턴스
llm_location_service = LLMLocationSearchService()
llm_route_service = LLMRouteRecommendService()
ocr_service = OCRAugmenterService()

logger = logging.getLogger(__name__)

@router.post("/location-estimate", response_model=LocationEstimateResponse)
@limiter.limit("10/minute")
async def estimate_location(
    request: Request,
    body: LocationEstimateRequest,
    current_user = Depends(get_current_user)
):
    """
    LLM 기반 위치 추정
    """
    try:
        location_data = await llm_location_service.analyze_location_from_image(
            body.image_url,
            body.exif_data
        )
        return LocationEstimateResponse(success=True, location_data=location_data)
    except Exception as e:
        logger.error(f"위치 추정 실패: {str(e)}")
        return LocationEstimateResponse(success=False, error_message=str(e))

@router.post("/ocr-enhance", response_model=OCREnhanceResponse)
async def enhance_location_with_ocr(
    request: OCREnhanceRequest,
    current_user = Depends(get_current_user)
):
    """
    OCR을 통한 위치 정보 보완
    """
    try:
        # OCR로 텍스트 추출
        extracted_text = await ocr_service.extract_text_from_image(request.file_key)
        
        # 추출된 텍스트에서 위치 정보 분석
        location_indicators = await ocr_service.analyze_location_indicators(extracted_text)
        
        # 기존 위치 정보와 결합
        enhanced_location = await llm_location_service.enhance_location_with_context(
            request.existing_location,
            location_indicators
        )
        
        return OCREnhanceResponse(
            success=True,
            enhanced_location=enhanced_location,
            extracted_text=extracted_text
        )
    except Exception as e:
        logger.error(f"OCR 위치 보완 실패: {str(e)}")
        return OCREnhanceResponse(
            success=False,
            error_message=str(e)
        )

@router.post("/route-recommend", response_model=RouteRecommendResponse)
@limiter.limit("10/minute")
async def recommend_travel_route(
    request: Request,
    body: RouteRecommendRequest,
    current_user = Depends(get_current_user)
):
    """
    여행 경로 추천
    """
    try:
        route_recommendation = await llm_route_service.recommend_travel_route(
            body.photos,
            body.user_preferences,
            body.duration_days
        )
        return RouteRecommendResponse(success=True, route_data=route_recommendation)
    except Exception as e:
        logger.error(f"경로 추천 실패: {str(e)}")
        return RouteRecommendResponse(success=False, error_message=str(e))

@router.post("/attractions", response_model=AttractionsResponse)
async def recommend_attractions(
    request: AttractionsRequest,
    current_user = Depends(get_current_user)
):
    """
    특정 지역의 명소 추천
    """
    try:
        attractions = await llm_route_service.recommend_attractions(
            request.location_info,
            request.categories,
            request.max_attractions
        )
        
        return AttractionsResponse(
            success=True,
            attractions=attractions
        )
    except Exception as e:
        logger.error(f"명소 추천 실패: {str(e)}")
        return AttractionsResponse(
            success=False,
            error_message=str(e)
        )

@router.post("/generate-itinerary", response_model=ItineraryResponse)
@limiter.limit("10/minute")
async def generate_travel_itinerary(
    request: Request,
    body: ItineraryRequest,
    current_user = Depends(get_current_user)
):
    """
    상세 여행 일정 생성 (제목 + 태그 자동 추출 포함)
    """
    try:
        itinerary = await llm_route_service.generate_travel_itinerary(
            body.route_data,
            body.user_preferences
        )
        title = None
        tags = None
        if itinerary:
            # 첫 번째 # 제목 추출
            m = re.match(r'^#\s+(.+)', itinerary.strip())
            if m:
                title = m.group(1).strip()
            # <!-- tags: ... --> 추출 후 본문에서 제거
            tag_match = re.search(r'<!--\s*tags:\s*(.+?)\s*-->', itinerary)
            if tag_match:
                raw_tags = tag_match.group(1)
                tags = [t.strip() for t in raw_tags.split(',') if t.strip()]
                itinerary = re.sub(r'\n?<!--\s*tags:.*?-->', '', itinerary).rstrip()
        return ItineraryResponse(success=True, itinerary=itinerary, title=title, tags=tags)
    except Exception as e:
        logger.error(f"일정 생성 실패: {str(e)}")
        return ItineraryResponse(success=False, error_message=str(e))


@router.post("/highlight-photos", response_model=HighlightPhotosResponse)
@limiter.limit("20/minute")
async def highlight_photos(
    request: Request,
    body: HighlightPhotosRequest,
    current_user = Depends(get_current_user)
):
    """
    사진 배치에서 AI가 하이라이트 사진 선정
    """
    try:
        highlighted_ids = await llm_route_service.select_highlight_photos(
            body.photos,
            body.max_highlights,
        )
        return HighlightPhotosResponse(success=True, highlighted_ids=highlighted_ids)
    except Exception as e:
        logger.error(f"하이라이트 선정 실패: {str(e)}")
        return HighlightPhotosResponse(success=False, error_message=str(e))


@router.post("/generate-tags", response_model=TagGenerateResponse)
@limiter.limit("20/minute")
async def generate_tags(
    request: Request,
    body: TagGenerateRequest,
    current_user = Depends(get_current_user)
):
    """
    위치 + 내용 기반 태그 자동 생성
    """
    try:
        tags = await llm_route_service.generate_tags_from_content(
            body.locations,
            body.content or "",
        )
        return TagGenerateResponse(success=True, tags=tags)
    except Exception as e:
        logger.error(f"태그 생성 실패: {str(e)}")
        return TagGenerateResponse(success=False, error_message=str(e))

@router.post("/category-recommendations", response_model=CategoryRecommendationsResponse)
async def get_category_recommendations(
    request: CategoryRecommendationsRequest,
    current_user = Depends(get_current_user)
):
    """
    카테고리 기반 추천
    """
    try:
        recommendations = await llm_route_service.get_category_recommendations(
            request.categories,
            request.location_info
        )
        
        return CategoryRecommendationsResponse(
            success=True,
            recommendations=recommendations
        )
    except Exception as e:
        logger.error(f"카테고리 추천 실패: {str(e)}")
        return CategoryRecommendationsResponse(
            success=False,
            error_message=str(e)
        )

@router.post("/enhance-location")
async def enhance_location_with_context(
    location_data: Dict[str, Any],
    user_context: Dict[str, Any],
    current_user = Depends(get_current_user)
):
    """
    사용자 컨텍스트를 활용한 위치 정보 보완
    """
    try:
        enhanced_location = await llm_location_service.enhance_location_with_context(
            location_data,
            user_context
        )

        return {
            "success": True,
            "enhanced_location": enhanced_location
        }
    except Exception as e:
        logger.error(f"위치 정보 보완 실패: {str(e)}")
        return {
            "success": False,
            "error_message": str(e)
        }


@router.post("/generate-blog", response_model=BlogGenerateResponse)
@limiter.limit("5/minute")
async def generate_travel_blog(
    request: Request,
    body: BlogGenerateRequest,
    current_user = Depends(get_current_user)
):
    """
    여행 사진/위치 데이터로 블로그 자동 생성
    """
    try:
        # 캐시 확인
        import hashlib
        cache_key = f"blog:{hashlib.md5(str(body.dict()).encode()).hexdigest()}"
        cached = await cache_get(cache_key)
        if cached:
            return BlogGenerateResponse(success=True, blog_content=cached)

        # LLM으로 블로그 생성
        location_summary = []
        for loc in body.locations:
            name = loc.get("name", "알 수 없는 장소")
            time = loc.get("time", "")
            coords = loc.get("coordinates", {})
            location_summary.append(f"- {name}: {time} ({coords.get('lat', 0):.4f}, {coords.get('lng', 0):.4f})")

        prompt = f"""다음 여행 데이터를 바탕으로 마크다운 형식의 여행 블로그를 작성해주세요.

제목: {body.title or '나의 여행 기록'}
스타일: {body.style}
사진 수: {len(body.photos)}장
방문 장소:
{chr(10).join(location_summary)}

요구사항:
- 마크다운 형식으로 작성
- 각 장소에 대한 감상 포함
- 여행 일정 요약 포함
- 자연스러운 {body.language} 문체
"""

        blog_content = await llm_route_service.generate_travel_itinerary(
            {"prompt": prompt, "locations": body.locations},
            {"language": body.language, "style": body.style}
        )

        result = blog_content if isinstance(blog_content, str) else str(blog_content)

        # 캐시 저장
        await cache_set(cache_key, result, ttl=1800)

        return BlogGenerateResponse(success=True, blog_content=result)
    except Exception as e:
        logger.error(f"블로그 생성 실패: {str(e)}")
        return BlogGenerateResponse(success=False, error_message=str(e))