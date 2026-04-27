from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
import logging
import json

from app.core.auth import get_current_user, get_optional_current_user
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
from app.models.db_models import Post, PostLike, PostBookmark, Comment, Follow, User, Photo, Location
from app.db.session import get_db
from app.services.notification_service import notification_service
from app.services.llm_route_recommend import LLMRouteRecommendService
from sqlalchemy.orm import Session
from sqlalchemy import func

_llm_service = LLMRouteRecommendService()

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

    post = db.query(Post).filter(Post.deleted_at.is_(None)).filter(Post.id == post_id).first()
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

    post = db.query(Post).filter(Post.deleted_at.is_(None)).filter(Post.id == post_id).first()
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
    posts = db.query(Post).filter(Post.deleted_at.is_(None)).filter(Post.id.in_(post_ids)).all() if post_ids else []

    return {
        "posts": [
            {
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "tags": json.loads(p.tags) if p.tags else [],
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
    current_user=Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """게시글 댓글 목록 조회"""
    post = db.query(Post).filter(Post.deleted_at.is_(None)).filter(Post.id == post_id).first()
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
        if author:
            _name = (
                author.name
                or (author.email.split('@')[0] if author.email else None)
                or c.user_id.split('|')[-1]
            )
            author_info = CommentAuthor(id=author.id, name=_name, picture=author.picture)
        else:
            author_info = None
        result.append(
            CommentResponse(
                id=c.id,
                post_id=c.post_id,
                user_id=c.user_id,
                content=c.content,
                parent_id=c.parent_id,
                created_at=c.created_at,
                updated_at=c.updated_at,
                author=author_info,
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

    post = db.query(Post).filter(Post.deleted_at.is_(None)).filter(Post.id == post_id).first()
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
    if author:
        _author_name = (
            author.name
            or (author.email.split('@')[0] if author.email else None)
            or user_id.split('|')[-1]
        )
        author_info = CommentAuthor(id=author.id, name=_author_name, picture=author.picture)
    else:
        _author_name = user_id.split('|')[-1]
        author_info = None

    if request.parent_id:
        parent_comment = db.query(Comment).filter(Comment.id == request.parent_id).first()
        if parent_comment:
            notification_service.create_notification(
                db, parent_comment.user_id, "reply",
                f"{_author_name}님이 회원님의 댓글에 답글을 달았습니다.",
                actor_id=user_id, post_id=post_id, comment_id=comment.id,
            )
    else:
        notification_service.create_notification(
            db, post.user_id, "comment",
            f"{_author_name}님이 회원님의 게시글에 댓글을 달았습니다.",
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
        author=author_info,
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
        pc = db.query(func.count(Post.id)).filter(Post.deleted_at.is_(None)).filter(Post.user_id == u.id).scalar()
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
        pc = db.query(func.count(Post.id)).filter(Post.deleted_at.is_(None)).filter(Post.user_id == u.id).scalar()
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
# 유저 공개 프로필
# ═══════════════════════════════════════════

@router.get("/users/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: str,
    current_user=Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """특정 유저의 공개 프로필 조회"""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    my_id = current_user["sub"] if current_user else None
    is_following = False
    if my_id and my_id != user_id:
        is_following = (
            db.query(Follow)
            .filter(Follow.follower_id == my_id, Follow.following_id == user_id)
            .first()
            is not None
        )

    posts_count = db.query(func.count(Post.id)).filter(Post.deleted_at.is_(None)).filter(Post.user_id == user_id).scalar()
    followers_count = db.query(func.count(Follow.id)).filter(Follow.following_id == user_id).scalar()
    following_count = db.query(func.count(Follow.id)).filter(Follow.follower_id == user_id).scalar()

    _name = (
        target.name
        or (target.email.split('@')[0] if target.email else None)
        or user_id.split('|')[-1]
    )

    return UserProfileResponse(
        id=target.id,
        name=_name,
        picture=target.picture,
        posts_count=posts_count,
        followers_count=followers_count,
        following_count=following_count,
        is_following=is_following,
    )


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

    total = db.query(func.count(Post.id)).filter(Post.deleted_at.is_(None)).filter(Post.user_id.in_(following_ids)).scalar()

    posts = (
        db.query(Post).filter(Post.deleted_at.is_(None))
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
    current_user=Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """게시글의 소셜 정보 (좋아요/댓글/북마크 수 및 현재 유저 상태)"""
    user_id = current_user["sub"] if current_user else None

    post = db.query(Post).filter(Post.deleted_at.is_(None)).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    likes_count = db.query(func.count(PostLike.id)).filter(PostLike.post_id == post_id).scalar()
    comments_count = db.query(func.count(Comment.id)).filter(Comment.post_id == post_id).scalar()
    bookmarks_count = db.query(func.count(PostBookmark.id)).filter(PostBookmark.post_id == post_id).scalar()

    is_liked = False
    is_bookmarked = False
    if user_id:
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


# ═══════════════════════════════════════════
# 개인 여행 패턴 분석
# ═══════════════════════════════════════════

@router.get("/users/{user_id}/travel-pattern")
async def get_travel_pattern(
    user_id: str,
    db: Session = Depends(get_db),
):
    """
    개인 여행 패턴 AI 분석:
    - 자주 방문한 나라/도시
    - 선호 여행 시기
    - 평균 여행 기간
    - 여행 테마 (태그 분석)
    """
    try:
        posts = db.query(Post).filter(Post.deleted_at.is_(None)).filter(Post.user_id == user_id).order_by(Post.created_at.desc()).all()
        if not posts:
            return {"success": True, "pattern": None, "message": "아직 여행 기록이 없습니다."}

        # 위치 집계
        country_count: dict = {}
        city_count: dict = {}
        months: list = []
        all_tags: list = []

        for p in posts:
            locs = (
                db.query(Location)
                .join(Photo, Photo.id == Location.photo_id)
                .filter(Photo.post_id == p.id)
                .all()
            )
            for loc in locs:
                if loc.country:
                    country_count[loc.country] = country_count.get(loc.country, 0) + 1
                if loc.city:
                    city_count[loc.city] = city_count.get(loc.city, 0) + 1
            if p.created_at:
                months.append(p.created_at.month)
            if p.tags:
                try:
                    tags = json.loads(p.tags) if isinstance(p.tags, str) else p.tags
                    if isinstance(tags, list):
                        all_tags.extend(tags)
                except Exception:
                    pass

        top_countries = sorted(country_count.items(), key=lambda x: -x[1])[:5]
        top_cities = sorted(city_count.items(), key=lambda x: -x[1])[:5]

        # 태그 빈도
        tag_freq: dict = {}
        for t in all_tags:
            tag_freq[t] = tag_freq.get(t, 0) + 1
        top_tags = sorted(tag_freq.items(), key=lambda x: -x[1])[:8]

        # 선호 월
        from collections import Counter
        month_names = ["1월", "2월", "3월", "4월", "5월", "6월",
                       "7월", "8월", "9월", "10월", "11월", "12월"]
        month_counter = Counter(months)
        peak_months = [month_names[m - 1] for m, _ in month_counter.most_common(3)]

        # LLM 인사이트 생성
        summary_prompt = f"""다음 여행자의 데이터를 분석하여 여행 패턴 인사이트를 한국어로 작성해주세요.

총 여행 기록: {len(posts)}개
자주 방문한 나라: {', '.join(c for c, _ in top_countries) or '데이터 없음'}
자주 방문한 도시: {', '.join(c for c, _ in top_cities) or '데이터 없음'}
선호 여행 시기: {', '.join(peak_months) or '데이터 없음'}
주요 태그: {', '.join(t for t, _ in top_tags) or '데이터 없음'}

아래 JSON 형식으로만 응답하세요:
{{
  "summary": "전체 여행 스타일 한 줄 요약 (30자 이내)",
  "insight": "여행 패턴에 대한 구체적인 인사이트 (100자 이내)",
  "recommendation": "다음 여행지 추천과 이유 (50자 이내)"
}}"""

        try:
            resp = await _llm_service.llm.provider.chat_completion(
                messages=[
                    {"role": "system", "content": "당신은 여행 데이터를 분석하는 전문가입니다."},
                    {"role": "user", "content": summary_prompt},
                ],
                temperature=0.3,
                max_tokens=300,
            )
            llm_data = _llm_service._parse_llm_json(resp)
        except Exception:
            llm_data = {}

        pattern = {
            "total_trips": len(posts),
            "top_countries": [{"name": c, "count": n} for c, n in top_countries],
            "top_cities": [{"name": c, "count": n} for c, n in top_cities],
            "peak_months": peak_months,
            "top_tags": [{"tag": t, "count": n} for t, n in top_tags],
            "summary": llm_data.get("summary", ""),
            "insight": llm_data.get("insight", ""),
            "recommendation": llm_data.get("recommendation", ""),
        }

        return {"success": True, "pattern": pattern}

    except Exception as e:
        logger.error(f"여행 패턴 분석 실패: {str(e)}")
        return {"success": False, "pattern": None, "message": str(e)}
