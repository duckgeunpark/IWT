from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from .photo import PhotoData, LocationInfo

class PostCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    tags: List[str] = []
    photos: List[PhotoData]
    categories: Optional[Dict[str, List[str]]] = None
    selected_route: Optional[Dict[str, Any]] = None

class PostResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    tags: List[str] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    photo_count: int
    user_id: str

class PostListResponse(BaseModel):
    posts: List[PostResponse]
    total: int
    skip: int
    limit: int

class PostUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None

class PostDetailResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    tags: List[str] = []
    created_at: datetime
    updated_at: Optional[datetime] = None
    user_id: str
    photos: List[PhotoData]
    categories: Optional[Dict[str, List[str]]] = None
    selected_route: Optional[Dict[str, Any]] = None 