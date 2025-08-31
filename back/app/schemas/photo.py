from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class PresignedUrlRequest(BaseModel):
    file_name: str
    content_type: str

class PresignedUrlResponse(BaseModel):
    presigned_url: str
    file_key: str
    expires_in: int

class ExifExtractRequest(BaseModel):
    file_key: str
    exif_data: Optional[Dict[str, Any]] = None

class ExifExtractResponse(BaseModel):
    extraction_success: bool
    exif_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

class PhotoPreviewResponse(BaseModel):
    file_key: str
    file_info: Optional[Dict[str, Any]] = None
    exif_data: Optional[Dict[str, Any]] = None

class MoveFileRequest(BaseModel):
    temp_key: str
    permanent_key: str

class Coordinates(BaseModel):
    latitude: float
    longitude: float
    altitude: Optional[float] = None

class LocationInfo(BaseModel):
    country: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    landmark: Optional[str] = None
    address: Optional[str] = None
    coordinates: Optional[Coordinates] = None
    confidence: Optional[float] = None

class PhotoData(BaseModel):
    file_key: str
    file_name: str
    file_size: int
    content_type: str
    location_info: Optional[LocationInfo] = None
    exif_data: Optional[Dict[str, Any]] = None
    llm_analysis: Optional[Dict[str, Any]] = None
    labeling_data: Optional[Dict[str, Any]] = None 