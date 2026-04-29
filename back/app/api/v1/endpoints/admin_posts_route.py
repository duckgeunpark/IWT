"""관리자 — 게시글 관리

- GET    /admin/posts            목록 (status/user/검색/삭제포함, 페이지네이션)
- GET    /admin/posts/{id}       상세
- PATCH  /admin/posts/{id}       status 변경 (published/draft 등 강제 전환)
- DELETE /admin/posts/{id}       soft delete (deleted_at 기록)
- POST   /admin/posts/{id}/restore  소프트 삭제 복구
"""

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.auth import require_admin
from app.db.session import get_db
from app.models.db_models import Post, User

router = APIRouter(prefix="/admin/posts", tags=["관리자-게시글"])


# ── 응답 스키마 ───────────────────────────────────────────────────────

class AuthorBrief(BaseModel):
    id: str
    email: Optional[str] = None
    name: Optional[str] = None


class PostListItem(BaseModel):
    id: int
    title: str
    status: str
    user_id: str
    author: Optional[AuthorBrief] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    photo_count: int = 0


class PostListResponse(BaseModel):
    items: List[PostListItem]
    total: int
    page: int
    size: int


class PostDetail(PostListItem):
    description: Optional[str] = None
    tags: Optional[str] = None


class PostStatusUpdate(BaseModel):
    status: str


# ── 헬퍼 ──────────────────────────────────────────────────────────────

def _to_list_item(post: Post, author: Optional[User]) -> PostListItem:
    return PostListItem(
        id=post.id,
        title=post.title,
        status=post.status,
        user_id=post.user_id,
        author=AuthorBrief(id=author.id, email=author.email, name=author.name) if author else None,
        created_at=post.created_at,
        updated_at=post.updated_at,
        deleted_at=post.deleted_at,
        photo_count=len(post.photos) if post.photos else 0,
    )


# ── 엔드포인트 ────────────────────────────────────────────────────────

@router.get("", response_model=PostListResponse)
async def list_posts(
    q: Optional[str] = Query(None, description="제목 검색"),
    status: Optional[str] = Query(None, description="published / draft 등"),
    user_id: Optional[str] = Query(None, description="특정 사용자 게시글만"),
    include_deleted: bool = Query(False, description="삭제된 게시글 포함"),
    only_deleted: bool = Query(False, description="삭제된 게시글만"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """게시글 목록 (필터링/페이지네이션). 관리자는 deleted 포함 조회 가능."""
    query = db.query(Post).options(joinedload(Post.photos))

    if only_deleted:
        query = query.filter(Post.deleted_at.is_not(None))
    elif not include_deleted:
        query = query.filter(Post.deleted_at.is_(None))

    if q:
        query = query.filter(Post.title.ilike(f"%{q}%"))
    if status:
        query = query.filter(Post.status == status)
    if user_id:
        query = query.filter(Post.user_id == user_id)

    total = query.with_entities(Post.id).count()
    rows = (
        query.order_by(Post.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    # 작성자 일괄 조회 (N+1 방지)
    user_ids = list({p.user_id for p in rows})
    authors = {}
    if user_ids:
        for u in db.query(User).filter(User.id.in_(user_ids)).all():
            authors[u.id] = u

    items = [_to_list_item(p, authors.get(p.user_id)) for p in rows]

    return PostListResponse(items=items, total=total, page=page, size=size)


@router.get("/{post_id}", response_model=PostDetail)
async def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """게시글 상세 (deleted 포함)"""
    post = db.query(Post).options(joinedload(Post.photos)).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    author = db.query(User).filter(User.id == post.user_id).first()
    base = _to_list_item(post, author)

    return PostDetail(
        **base.model_dump(),
        description=post.description,
        tags=post.tags,
    )


@router.patch("/{post_id}", response_model=PostDetail)
async def update_post_status(
    post_id: int,
    body: PostStatusUpdate,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """게시글 status 강제 변경 (published/draft 등)"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    valid_statuses = {"published", "draft", "private"}
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"허용된 status: {', '.join(sorted(valid_statuses))}",
        )

    post.status = body.status
    db.commit()
    return await get_post(post_id, db, admin)


@router.delete("/{post_id}", response_model=PostDetail)
async def soft_delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """게시글 soft delete (deleted_at 기록). 일반 조회에서 제외됨."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    if post.deleted_at is None:
        post.deleted_at = datetime.utcnow()
        db.commit()

    return await get_post(post_id, db, admin)


@router.post("/{post_id}/restore", response_model=PostDetail)
async def restore_post(
    post_id: int,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """soft delete된 게시글 복구"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    if post.deleted_at is not None:
        post.deleted_at = None
        db.commit()

    return await get_post(post_id, db, admin)
