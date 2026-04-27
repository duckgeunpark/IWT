"""관리자 — 사용자 관리

- GET  /admin/users        목록 (페이지네이션, 이메일/이름 검색, is_active 필터)
- GET  /admin/users/{id}   상세 (게시글 수, 팔로워/팔로잉 수)
- PATCH /admin/users/{id}  is_active 토글 (soft delete)
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.db.session import get_db
from app.models.db_models import User, Post, Follow

router = APIRouter(prefix="/admin/users", tags=["관리자-사용자"])


# ── 응답 스키마 ───────────────────────────────────────────────────────

class UserListItem(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    post_count: int = 0


class UserListResponse(BaseModel):
    items: List[UserListItem]
    total: int
    page: int
    size: int


class UserDetail(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    post_count: int = 0
    follower_count: int = 0
    following_count: int = 0


class UserUpdateRequest(BaseModel):
    is_active: Optional[bool] = None


# ── 엔드포인트 ────────────────────────────────────────────────────────

@router.get("", response_model=UserListResponse)
async def list_users(
    q: Optional[str] = Query(None, description="이메일 또는 이름 검색"),
    active: Optional[bool] = Query(None, description="True=활성, False=비활성, None=전체"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """사용자 목록 (페이지네이션 + 검색 + 상태 필터)"""
    query = db.query(User)

    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.email.ilike(like), User.name.ilike(like)))
    if active is not None:
        query = query.filter(User.is_active == active)

    total = query.count()
    rows = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    # 게시글 수 일괄 조회 (N+1 방지)
    user_ids = [u.id for u in rows]
    post_counts = {}
    if user_ids:
        results = (
            db.query(Post.user_id, func.count(Post.id))
            .filter(Post.user_id.in_(user_ids), Post.deleted_at.is_(None))
            .group_by(Post.user_id)
            .all()
        )
        post_counts = dict(results)

    items = [
        UserListItem(
            id=u.id,
            email=u.email,
            name=u.name,
            picture=u.picture,
            is_active=u.is_active,
            created_at=u.created_at,
            post_count=post_counts.get(u.id, 0),
        )
        for u in rows
    ]

    return UserListResponse(items=items, total=total, page=page, size=size)


@router.get("/{user_id}", response_model=UserDetail)
async def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """사용자 상세 + 통계"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    post_count = db.query(func.count(Post.id)).filter(Post.user_id == user_id, Post.deleted_at.is_(None)).scalar() or 0
    follower_count = db.query(func.count(Follow.id)).filter(Follow.following_id == user_id).scalar() or 0
    following_count = db.query(func.count(Follow.id)).filter(Follow.follower_id == user_id).scalar() or 0

    return UserDetail(
        id=user.id,
        email=user.email,
        name=user.name,
        picture=user.picture,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        post_count=post_count,
        follower_count=follower_count,
        following_count=following_count,
    )


@router.patch("/{user_id}", response_model=UserDetail)
async def update_user(
    user_id: str,
    body: UserUpdateRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """사용자 상태 변경 (is_active 토글 = soft delete/복구)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    # 자기 자신 비활성화 방지
    admin_sub = (admin.get("sub") or "").lower()
    admin_email = (admin.get("email") or "").lower()
    if body.is_active is False and (
        user.id.lower() == admin_sub or (user.email and user.email.lower() == admin_email)
    ):
        raise HTTPException(status_code=400, detail="자기 자신을 비활성화할 수 없습니다.")

    if body.is_active is not None:
        user.is_active = body.is_active

    db.commit()
    db.refresh(user)

    return await get_user(user_id, db, admin)
