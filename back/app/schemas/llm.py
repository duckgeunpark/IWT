from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class LocationEstimateRequest(BaseModel):
    image_url: str
    exif_data: Optional[Dict[str, Any]] = None

class LocationEstimateResponse(BaseModel):
    success: bool
    location_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

class OCREnhanceRequest(BaseModel):
    file_key: str
    existing_location: Optional[Dict[str, Any]] = None

class OCREnhanceResponse(BaseModel):
    success: bool
    enhanced_location: Optional[Dict[str, Any]] = None
    extracted_text: Optional[str] = None
    error_message: Optional[str] = None

class RouteRecommendRequest(BaseModel):
    photos: List[Dict[str, Any]]
    user_preferences: Optional[Dict[str, Any]] = None
    duration_days: Optional[int] = None

class RouteRecommendResponse(BaseModel):
    success: bool
    route_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

class AttractionsRequest(BaseModel):
    location_info: Dict[str, Any]
    categories: List[str]
    max_attractions: int = 10

class AttractionsResponse(BaseModel):
    success: bool
    attractions: Optional[List[Dict[str, Any]]] = None
    error_message: Optional[str] = None

class ItineraryRequest(BaseModel):
    route_data: Dict[str, Any]
    user_preferences: Optional[Dict[str, Any]] = None

class ItineraryResponse(BaseModel):
    success: bool
    itinerary: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

class CategoryRecommendationsRequest(BaseModel):
    categories: List[str]
    location_info: Optional[Dict[str, Any]] = None

class CategoryRecommendationsResponse(BaseModel):
    success: bool
    recommendations: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None 