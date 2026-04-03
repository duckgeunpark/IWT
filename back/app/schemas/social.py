from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ── 좋아요 ──
class LikeResponse(BaseModel):
    liked: bool
    likes_count: int


# ── 북마크 ──
class BookmarkResponse(BaseModel):
    bookmarked: bool
    bookmarks_count: int


# ── 댓글 ──
class CommentCreateRequest(BaseModel):
    content: str
    parent_id: Optional[int] = None


class CommentUpdateRequest(BaseModel):
    content: str


class CommentAuthor(BaseModel):
    id: str
    name: Optional[str] = None
    picture: Optional[str] = None


class CommentResponse(BaseModel):
    id: int
    post_id: int
    user_id: str
    content: str
    parent_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    author: Optional[CommentAuthor] = None
    reply_count: int = 0


class CommentListResponse(BaseModel):
    comments: List[CommentResponse]
    total: int


# ── 팔로우 ──
class FollowResponse(BaseModel):
    following: bool
    followers_count: int
    following_count: int


class UserProfileResponse(BaseModel):
    id: str
    name: Optional[str] = None
    picture: Optional[str] = None
    posts_count: int = 0
    followers_count: int = 0
    following_count: int = 0
    is_following: bool = False


class UserListResponse(BaseModel):
    users: List[UserProfileResponse]
    total: int


# ── 게시글 소셜 정보 (기존 PostResponse 확장용) ──
class PostSocialInfo(BaseModel):
    likes_count: int = 0
    comments_count: int = 0
    bookmarks_count: int = 0
    is_liked: bool = False
    is_bookmarked: bool = False
