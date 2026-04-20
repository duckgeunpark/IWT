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
    itinerary: Optional[str] = None
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    error_message: Optional[str] = None


class HighlightPhotosRequest(BaseModel):
    photos: List[Dict[str, Any]]  # [{id, file_name, gps, taken_at, file_size}]
    max_highlights: int = 5


class HighlightPhotosResponse(BaseModel):
    success: bool
    highlighted_ids: Optional[List[str]] = None
    error_message: Optional[str] = None


class TagGenerateRequest(BaseModel):
    locations: List[Dict[str, Any]]  # [{country, city, landmark}]
    content: Optional[str] = None   # existing description text


class TagGenerateResponse(BaseModel):
    success: bool
    tags: Optional[List[str]] = None
    error_message: Optional[str] = None


class SimilarTripsRequest(BaseModel):
    post_id: int
    limit: int = 6


class SimilarTripsResponse(BaseModel):
    success: bool
    similar_posts: Optional[List[Dict[str, Any]]] = None
    error_message: Optional[str] = None


class TravelPatternRequest(BaseModel):
    user_id: str


class TravelPatternResponse(BaseModel):
    success: bool
    pattern: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

class ClusteredItineraryRequest(BaseModel):
    photos: List[Dict[str, Any]]  # [{id, gps, taken_at, file_name, file_size}]
    user_preferences: Optional[Dict[str, Any]] = None
    distance_km: float = 0.5
    time_hours: float = 2.0

class ClusterInfo(BaseModel):
    cluster_id: int
    photo_ids: List[str]
    location_name: str
    section_heading: str

class ClusteredItineraryResponse(BaseModel):
    success: bool
    itinerary: Optional[str] = None
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    cluster_count: Optional[int] = None
    clusters: Optional[List[ClusterInfo]] = None
    error_message: Optional[str] = None

class CategoryRecommendationsRequest(BaseModel):
    categories: List[str]
    location_info: Optional[Dict[str, Any]] = None

class CategoryRecommendationsResponse(BaseModel):
    success: bool
    recommendations: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

class BlogGenerateRequest(BaseModel):
    photos: List[Dict[str, Any]]
    locations: List[Dict[str, Any]]
    title: Optional[str] = None
    style: str = "casual"  # casual, formal, travel-blog
    language: str = "ko"

class BlogGenerateResponse(BaseModel):
    success: bool
    blog_content: Optional[str] = None
    error_message: Optional[str] = None