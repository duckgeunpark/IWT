"""
User Schemas - 사용자 관련 Pydantic 스키마
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    """사용자 기본 스키마"""
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None


class UserCreate(UserBase):
    """사용자 생성 스키마"""
    id: str
    email_verified: Optional[bool] = None
    given_name: Optional[str] = None
    nickname: Optional[str] = None
    updated_at: Optional[str] = None


class UserUpdate(BaseModel):
    """사용자 업데이트 스키마"""
    name: Optional[str] = None
    picture: Optional[str] = None
    email: Optional[str] = None


class UserResponse(UserBase):
    """사용자 응답 스키마"""
    id: str
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """사용자 목록 응답 스키마"""
    users: list[UserResponse]
    total: int
    page: int
    per_page: int


class AuthTokenPayload(BaseModel):
    """JWT 토큰 페이로드 스키마"""
    sub: str  # user ID
    email: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None