from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from .photo import PhotoData, LocationInfo


class PostAuthor(BaseModel):
    id: str
    name: Optional[str] = None
    picture: Optional[str] = None


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
    thumbnail_url: Optional[str] = None
    likes_count: int = 0
    comments_count: int = 0
    is_liked: bool = False
    is_bookmarked: bool = False
    author: Optional[PostAuthor] = None


class PostListResponse(BaseModel):
    posts: List[PostResponse]
    total: int
    skip: int
    limit: int


class PostUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    keep_photo_ids: Optional[List[int]] = None  # 유지할 기존 사진 DB ID 목록
    new_photos: Optional[List[Dict[str, Any]]] = None  # 새로 추가할 사진 목록


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
