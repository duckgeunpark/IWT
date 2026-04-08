from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import logging
import json

from app.core.auth import get_current_user
from app.schemas.social import (
    LikeResponse,
    BookmarkResponse,
    CommentCreateRequest,
    CommentUpdateRequest,
    CommentResponse,
    CommentListResponse,
    CommentAuthor,
    FollowResponse,
    UserProfileResponse,
    UserListResponse,
    PostSocialInfo,
)
from app.models.db_models import Post, PostLike, PostBookmark, Comment, Follow, User
from app.db.session import get_db
from app.services.notification_service import notification_service
from sqlalchemy.orm import Session
from sqlalchemy import func

router = APIRouter(tags=["소셜"])

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 좋아요
# ═══════════════════════════════════════════

@router.post("/posts/{post_id}/like", response_model=LikeResponse)
async def toggle_like(
    post_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """게시글 좋아요 토글"""
    user_id = current_user["sub"]

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    existing = (
        db.query(PostLike)
        .filter(PostLike.post_id == post_id, PostLike.user_id == user_id)
        .first()
    )

    if existing:
        db.delete(existing)
        db.commit()
        liked = False
    else:
        db.add(PostLike(post_id=post_id, user_id=user_id))
        db.commit()
        liked = True
        actor = db.query(User).filter(User.id == user_id).first()
        actor_name = actor.name if actor else "누군가"
        notification_service.create_notification(
            db, post.user_id, "like",
            f"{actor_name}님이 회원님의 게시글을 좋아합니다.",
            actor_id=user_id, post_id=post_id,
        )

    count = db.query(func.count(PostLike.id)).filter(PostLike.post_id == post_id).scalar()
    return LikeResponse(liked=liked, likes_count=count)


# ═══════════════════════════════════════════
# 북마크
# ═══════════════════════════════════════════

@router.post("/posts/{post_id}/bookmark", response_model=BookmarkResponse)
async def toggle_bookmark(
    post_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """게시글 북마크 토글"""
    user_id = current_user["sub"]

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    existing = (
        db.query(PostBookmark)
        .filter(PostBookmark.post_id == post_id, PostBookmark.user_id == user_id)
        .first()
    )

    if existing:
        db.delete(existing)
        db.commit()
        bookmarked = False
    else:
        db.add(PostBookmark(post_id=post_id, user_id=user_id))
        db.commit()
        bookmarked = True

    count = db.query(func.count(PostBookmark.id)).filter(PostBookmark.post_id == post_id).scalar()
    return BookmarkResponse(bookmarked=bookmarked, bookmarks_count=count)


@router.get("/posts/bookmarked", response_model=dict)
async def get_bookmarked_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """북마크한 게시글 목록"""
    user_id = current_user["sub"]

    total = (
        db.query(func.count(PostBookmark.id))
        .filter(PostBookmark.user_id == user_id)
        .scalar()
    )

    bookmarks = (
        db.query(PostBookmark)
        .filter(PostBookmark.user_id == user_id)
        .order_by(PostBookmark.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    post_ids = [b.post_id for b in bookmarks]
    posts = db.query(Post).filter(Post.id.in_(post_ids)).all() if post_ids else []

    return {
        "posts": [
            {
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "tags": p.tags,
                "created_at": p.created_at.isoformat(),
                "user_id": p.user_id,
                "photo_count": len(p.photos),
            }
            for p in posts
        ],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


# ═══════════════════════════════════════════
# 댓글
# ═══════════════════════════════════════════

@router.get("/posts/{post_id}/comments", response_model=CommentListResponse)
async def get_comments(
    post_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """게시글 댓글 목록 조회"""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    total = (
        db.query(func.count(Comment.id))
        .filter(Comment.post_id == post_id, Comment.parent_id.is_(None))
        .scalar()
    )

    comments = (
        db.query(Comment)
        .filter(Comment.post_id == post_id, Comment.parent_id.is_(None))
        .order_by(Comment.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    result = []
    for c in comments:
        author = db.query(User).filter(User.id == c.user_id).first()
        reply_count = (
            db.query(func.count(Comment.id))
            .filter(Comment.parent_id == c.id)
            .scalar()
        )
        result.append(
            CommentResponse(
                id=c.id,
                post_id=c.post_id,
                user_id=c.user_id,
                content=c.content,
                parent_id=c.parent_id,
                created_at=c.created_at,
                updated_at=c.updated_at,
                author=CommentAuthor(
                    id=author.id,
                    name=author.name,
                    picture=author.picture,
                )
                if author
                else None,
                reply_count=reply_count,
            )
        )

    return CommentListResponse(comments=result, total=total)


@router.post("/posts/{post_id}/comments", response_model=CommentResponse)
async def create_comment(
    post_id: int,
    request: CommentCreateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """댓글 작성"""
    user_id = current_user["sub"]

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    if request.parent_id:
        parent = db.query(Comment).filter(Comment.id == request.parent_id, Comment.post_id == post_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="상위 댓글을 찾을 수 없습니다.")

    comment = Comment(
        post_id=post_id,
        user_id=user_id,
        content=request.content,
        parent_id=request.parent_id,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    author = db.query(User).filter(User.id == user_id).first()
    actor_name = author.name if author else "누군가"

    if request.parent_id:
        parent_comment = db.query(Comment).filter(Comment.id == request.parent_id).first()
        if parent_comment:
            notification_service.create_notification(
                db, parent_comment.user_id, "reply",
                f"{actor_name}님이 회원님의 댓글에 답글을 달았습니다.",
                actor_id=user_id, post_id=post_id, comment_id=comment.id,
            )
    else:
        notification_service.create_notification(
            db, post.user_id, "comment",
            f"{actor_name}님이 회원님의 게시글에 댓글을 달았습니다.",
            actor_id=user_id, post_id=post_id, comment_id=comment.id,
        )

    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        user_id=comment.user_id,
        content=comment.content,
        parent_id=comment.parent_id,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        author=CommentAuthor(
            id=author.id, name=author.name, picture=author.picture
        )
        if author
        else None,
        reply_count=0,
    )


@router.put("/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
    comment_id: int,
    request: CommentUpdateRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """댓글 수정"""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    if comment.user_id != current_user["sub"]:
        raise HTTPException(status_code=403, detail="댓글을 수정할 권한이 없습니다.")

    comment.content = request.content
    db.commit()
    db.refresh(comment)

    author = db.query(User).filter(User.id == comment.user_id).first()
    reply_count = db.query(func.count(Comment.id)).filter(Comment.parent_id == comment.id).scalar()

    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        user_id=comment.user_id,
        content=comment.content,
        parent_id=comment.parent_id,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        author=CommentAuthor(id=author.id, name=author.name, picture=author.picture) if author else None,
        reply_count=reply_count,
    )


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """댓글 삭제"""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    if comment.user_id != current_user["sub"]:
        raise HTTPException(status_code=403, detail="댓글을 삭제할 권한이 없습니다.")

    db.delete(comment)
    db.commit()
    return {"message": "댓글이 삭제되었습니다."}


# ═══════════════════════════════════════════
# 팔로우
# ═══════════════════════════════════════════

@router.post("/users/{user_id}/follow", response_model=FollowResponse)
async def toggle_follow(
    user_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """유저 팔로우/언팔로우 토글"""
    follower_id = current_user["sub"]

    if follower_id == user_id:
        raise HTTPException(status_code=400, detail="자기 자신을 팔로우할 수 없습니다.")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    existing = (
        db.query(Follow)
        .filter(Follow.follower_id == follower_id, Follow.following_id == user_id)
        .first()
    )

    if existing:
        db.delete(existing)
        db.commit()
        following = False
    else:
        db.add(Follow(follower_id=follower_id, following_id=user_id))
        db.commit()
        following = True
        actor = db.query(User).filter(User.id == follower_id).first()
        actor_name = actor.name if actor else "누군가"
        notification_service.create_notification(
            db, user_id, "follow",
            f"{actor_name}님이 회원님을 팔로우하기 시작했습니다.",
            actor_id=follower_id,
        )

    followers_count = db.query(func.count(Follow.id)).filter(Follow.following_id == user_id).scalar()
    following_count = db.query(func.count(Follow.id)).filter(Follow.follower_id == user_id).scalar()

    return FollowResponse(
        following=following,
        followers_count=followers_count,
        following_count=following_count,
    )


@router.get("/users/{user_id}/followers", response_model=UserListResponse)
async def get_followers(
    user_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """팔로워 목록"""
    total = db.query(func.count(Follow.id)).filter(Follow.following_id == user_id).scalar()
    follows = (
        db.query(Follow)
        .filter(Follow.following_id == user_id)
        .order_by(Follow.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    my_id = current_user["sub"]
    users = []
    for f in follows:
        u = db.query(User).filter(User.id == f.follower_id).first()
        if not u:
            continue
        is_following = (
            db.query(Follow)
            .filter(Follow.follower_id == my_id, Follow.following_id == u.id)
            .first()
            is not None
        )
        fc = db.query(func.count(Follow.id)).filter(Follow.following_id == u.id).scalar()
        fgc = db.query(func.count(Follow.id)).filter(Follow.follower_id == u.id).scalar()
        pc = db.query(func.count(Post.id)).filter(Post.user_id == u.id).scalar()
        users.append(
            UserProfileResponse(
                id=u.id,
                name=u.name,
                picture=u.picture,
                posts_count=pc,
                followers_count=fc,
                following_count=fgc,
                is_following=is_following,
            )
        )

    return UserListResponse(users=users, total=total)


@router.get("/users/{user_id}/following", response_model=UserListResponse)
async def get_following(
    user_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """팔로잉 목록"""
    total = db.query(func.count(Follow.id)).filter(Follow.follower_id == user_id).scalar()
    follows = (
        db.query(Follow)
        .filter(Follow.follower_id == user_id)
        .order_by(Follow.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    my_id = current_user["sub"]
    users = []
    for f in follows:
        u = db.query(User).filter(User.id == f.following_id).first()
        if not u:
            continue
        is_following = (
            db.query(Follow)
            .filter(Follow.follower_id == my_id, Follow.following_id == u.id)
            .first()
            is not None
        )
        fc = db.query(func.count(Follow.id)).filter(Follow.following_id == u.id).scalar()
        fgc = db.query(func.count(Follow.id)).filter(Follow.follower_id == u.id).scalar()
        pc = db.query(func.count(Post.id)).filter(Post.user_id == u.id).scalar()
        users.append(
            UserProfileResponse(
                id=u.id,
                name=u.name,
                picture=u.picture,
                posts_count=pc,
                followers_count=fc,
                following_count=fgc,
                is_following=is_following,
            )
        )

    return UserListResponse(users=users, total=total)


# ═══════════════════════════════════════════
# 피드
# ═══════════════════════════════════════════

@router.get("/feed", response_model=dict)
async def get_feed(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """팔로우 기반 피드"""
    user_id = current_user["sub"]

    following_ids = [
        f.following_id
        for f in db.query(Follow.following_id).filter(Follow.follower_id == user_id).all()
    ]

    if not following_ids:
        return {"posts": [], "total": 0, "skip": skip, "limit": limit}

    total = db.query(func.count(Post.id)).filter(Post.user_id.in_(following_ids)).scalar()

    posts = (
        db.query(Post)
        .filter(Post.user_id.in_(following_ids))
        .order_by(Post.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    result = []
    for p in posts:
        author = db.query(User).filter(User.id == p.user_id).first()
        likes_count = db.query(func.count(PostLike.id)).filter(PostLike.post_id == p.id).scalar()
        comments_count = db.query(func.count(Comment.id)).filter(Comment.post_id == p.id).scalar()
        is_liked = (
            db.query(PostLike)
            .filter(PostLike.post_id == p.id, PostLike.user_id == user_id)
            .first()
            is not None
        )
        is_bookmarked = (
            db.query(PostBookmark)
            .filter(PostBookmark.post_id == p.id, PostBookmark.user_id == user_id)
            .first()
            is not None
        )

        # tags가 JSON 문자열로 저장된 경우 파싱
        tags = p.tags
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                tags = []

        result.append(
            {
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "tags": tags,
                "created_at": p.created_at.isoformat(),
                "user_id": p.user_id,
                "photo_count": len(p.photos),
                "author": {
                    "id": author.id,
                    "name": author.name,
                    "picture": author.picture,
                }
                if author
                else None,
                "likes_count": likes_count,
                "comments_count": comments_count,
                "is_liked": is_liked,
                "is_bookmarked": is_bookmarked,
            }
        )

    return {"posts": result, "total": total, "skip": skip, "limit": limit}


# ═══════════════════════════════════════════
# 게시글 소셜 정보
# ═══════════════════════════════════════════

@router.get("/posts/{post_id}/social", response_model=PostSocialInfo)
async def get_post_social_info(
    post_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """게시글의 소셜 정보 (좋아요/댓글/북마크 수 및 현재 유저 상태)"""
    user_id = current_user["sub"]

    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    likes_count = db.query(func.count(PostLike.id)).filter(PostLike.post_id == post_id).scalar()
    comments_count = db.query(func.count(Comment.id)).filter(Comment.post_id == post_id).scalar()
    bookmarks_count = db.query(func.count(PostBookmark.id)).filter(PostBookmark.post_id == post_id).scalar()

    is_liked = (
        db.query(PostLike)
        .filter(PostLike.post_id == post_id, PostLike.user_id == user_id)
        .first()
        is not None
    )
    is_bookmarked = (
        db.query(PostBookmark)
        .filter(PostBookmark.post_id == post_id, PostBookmark.user_id == user_id)
        .first()
        is not None
    )

    return PostSocialInfo(
        likes_count=likes_count,
        comments_count=comments_count,
        bookmarks_count=bookmarks_count,
        is_liked=is_liked,
        is_bookmarked=is_bookmarked,
    )
