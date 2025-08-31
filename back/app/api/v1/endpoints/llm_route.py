from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional, Dict, Any
import logging

from app.services.llm_location_search import LLMLocationSearchService
from app.services.llm_route_recommend import LLMRouteRecommendService
from app.services.ocr_augmenter import OCRAugmenterService
from app.core.auth import get_current_user
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
    CategoryRecommendationsResponse
)

router = APIRouter(prefix="/llm", tags=["llm"])

# 서비스 인스턴스
llm_location_service = LLMLocationSearchService()
llm_route_service = LLMRouteRecommendService()
ocr_service = OCRAugmenterService()

logger = logging.getLogger(__name__)

@router.post("/location-estimate", response_model=LocationEstimateResponse)
async def estimate_location(
    request: LocationEstimateRequest,
    current_user = Depends(get_current_user)
):
    """
    LLM 기반 위치 추정
    """
    try:
        # 이미지 URL과 EXIF 데이터를 기반으로 위치 추정
        location_data = await llm_location_service.analyze_location_from_image(
            request.image_url,
            request.exif_data
        )
        
        return LocationEstimateResponse(
            success=True,
            location_data=location_data
        )
    except Exception as e:
        logger.error(f"위치 추정 실패: {str(e)}")
        return LocationEstimateResponse(
            success=False,
            error_message=str(e)
        )

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
async def recommend_travel_route(
    request: RouteRecommendRequest,
    current_user = Depends(get_current_user)
):
    """
    여행 경로 추천
    """
    try:
        # 사진들과 사용자 선호도를 기반으로 경로 추천
        route_recommendation = await llm_route_service.recommend_travel_route(
            request.photos,
            request.user_preferences,
            request.duration_days
        )
        
        return RouteRecommendResponse(
            success=True,
            route_data=route_recommendation
        )
    except Exception as e:
        logger.error(f"경로 추천 실패: {str(e)}")
        return RouteRecommendResponse(
            success=False,
            error_message=str(e)
        )

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
async def generate_travel_itinerary(
    request: ItineraryRequest,
    current_user = Depends(get_current_user)
):
    """
    상세 여행 일정 생성
    """
    try:
        itinerary = await llm_route_service.generate_travel_itinerary(
            request.route_data,
            request.user_preferences
        )
        
        return ItineraryResponse(
            success=True,
            itinerary=itinerary
        )
    except Exception as e:
        logger.error(f"일정 생성 실패: {str(e)}")
        return ItineraryResponse(
            success=False,
            error_message=str(e)
        )

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