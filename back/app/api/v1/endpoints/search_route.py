from fastapi import APIRouter, Depends, Query, Request
from typing import Optional, List
import logging
import json

from app.models.db_models import Post, Photo, Location, Category, PostLike, User
from app.db.session import get_db
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, and_, distinct
from app.services.llm_route_recommend import llm_route_service
from app.services.s3_presigned_url import S3PresignedURLService
from app.services.utils import parse_llm_json

s3_service = S3PresignedURLService()

router = APIRouter(prefix="/search", tags=["검색"])
logger = logging.getLogger(__name__)


@router.get("/posts")
async def search_posts(
    q: Optional[str] = Query(None, description="검색어 (제목, 설명, 태그)"),
    region: Optional[str] = Query(None, description="지역 (국가/도시)"),
    theme: Optional[str] = Query(None, description="테마 카테고리"),
    duration_min: Optional[int] = Query(None, ge=1, description="최소 기간 (일)"),
    duration_max: Optional[int] = Query(None, ge=1, description="최대 기간 (일)"),
    sort: Optional[str] = Query("newest", description="정렬: newest, popular, most_liked"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    고급 게시글 검색

    - q: 제목, 설명, 태그에서 키워드 검색
    - region: 국가/도시 기반 검색 (카테고리 + 위치)
    - theme: 테마 카테고리 (맛집, 자연, 문화...)
    - duration_min/max: 사진 촬영일 기간 필터
    - sort: newest(최신), popular(사진 많은 순), most_liked(좋아요 순)
    """
    query = db.query(Post).filter(Post.deleted_at.is_(None)).options(joinedload(Post.photos))

    # 키워드 검색
    if q:
        keyword = f"%{q}%"
        query = query.filter(
            or_(
                Post.title.ilike(keyword),
                Post.description.ilike(keyword),
                Post.tags.ilike(keyword),
            )
        )

    # 지역 검색: 카테고리(country/city) 또는 Location(country/city)
    if region:
        region_kw = f"%{region}%"
        post_ids_by_category = (
            db.query(Category.post_id)
            .filter(
                Category.category_type.in_(["country", "city", "region"]),
                Category.category_name.ilike(region_kw),
            )
            .subquery()
        )
        post_ids_by_location = (
            db.query(Post.id)
            .join(Photo, Photo.post_id == Post.id)
            .join(Location, Location.photo_id == Photo.id)
            .filter(
                or_(
                    Location.country.ilike(region_kw),
                    Location.city.ilike(region_kw),
                    Location.region.ilike(region_kw),
                    Location.address.ilike(region_kw),
                )
            )
            .subquery()
        )
        query = query.filter(
            or_(
                Post.id.in_(post_ids_by_category),
                Post.id.in_(post_ids_by_location),
            )
        )

    # 테마 검색
    if theme:
        theme_kw = f"%{theme}%"
        post_ids_theme = (
            db.query(Category.post_id)
            .filter(
                Category.category_type == "theme",
                Category.category_name.ilike(theme_kw),
            )
            .subquery()
        )
        # 태그에서도 테마 검색
        query = query.filter(
            or_(
                Post.id.in_(post_ids_theme),
                Post.tags.ilike(theme_kw),
            )
        )

    # 정렬
    if sort == "popular":
        # 사진 많은 순
        photo_count_sub = (
            db.query(Photo.post_id, func.count(Photo.id).label("cnt"))
            .group_by(Photo.post_id)
            .subquery()
        )
        query = query.outerjoin(photo_count_sub, Post.id == photo_count_sub.c.post_id).order_by(
            photo_count_sub.c.cnt.desc()
        )
    elif sort == "most_liked":
        like_count_sub = (
            db.query(PostLike.post_id, func.count(PostLike.id).label("cnt"))
            .group_by(PostLike.post_id)
            .subquery()
        )
        query = query.outerjoin(like_count_sub, Post.id == like_count_sub.c.post_id).order_by(
            like_count_sub.c.cnt.desc()
        )
    else:
        query = query.order_by(Post.created_at.desc())

    # 카운트 (정렬 전에 수행 - 같은 필터로)
    total = query.with_entities(func.count(distinct(Post.id))).scalar()

    posts = query.offset(skip).limit(limit).all()

    # 중복 제거 (JOIN으로 인한)
    seen = set()
    unique_posts = []
    for p in posts:
        if p.id not in seen:
            seen.add(p.id)
            unique_posts.append(p)

    # 작성자 캐시 (같은 user_id 반복 쿼리 방지)
    author_cache: dict = {}

    def _get_author(user_id: str):
        if user_id in author_cache:
            return author_cache[user_id]
        user_obj = db.query(User).filter(User.id == user_id).first()
        if user_obj:
            display_name = (
                user_obj.name
                or (user_obj.email.split('@')[0] if user_obj.email else None)
                or user_id.split('|')[-1]
            )
            info = {"id": user_obj.id, "name": display_name, "picture": user_obj.picture}
        else:
            info = {"id": user_id, "name": user_id.split('|')[-1], "picture": None}
        author_cache[user_id] = info
        return info

    # 결과 구성
    results = []
    for p in unique_posts:
        # 카테고리 수집
        categories = db.query(Category).filter(Category.post_id == p.id).all()
        category_map = {}
        for c in categories:
            if c.category_type not in category_map:
                category_map[c.category_type] = []
            category_map[c.category_type].append(c.category_name)

        # 좋아요 수
        likes_count = db.query(func.count(PostLike.id)).filter(PostLike.post_id == p.id).scalar()

        # 위치 정보
        locations = (
            db.query(Location)
            .join(Photo, Photo.id == Location.photo_id)
            .filter(Photo.post_id == p.id, Location.latitude.isnot(None))
            .all()
        )

        # tags가 JSON 문자열로 저장된 경우 파싱
        tags = p.tags
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (json.JSONDecodeError, TypeError):
                tags = []

        # 썸네일 URL (첫 번째 사진)
        thumbnail_url = None
        if p.photos:
            thumbnail_url = s3_service.generate_download_url_sync(p.photos[0].file_key)

        results.append(
            {
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "tags": tags,
                "created_at": p.created_at.isoformat(),
                "user_id": p.user_id,
                "photo_count": len(p.photos),
                "likes_count": likes_count,
                "thumbnail_url": thumbnail_url,
                "author": _get_author(p.user_id),
                "categories": category_map,
                "locations": [
                    {
                        "country": loc.country,
                        "city": loc.city,
                        "lat": loc.latitude,
                        "lng": loc.longitude,
                    }
                    for loc in locations[:5]
                ],
            }
        )

    return {
        "posts": results,
        "total": total,
        "skip": skip,
        "limit": limit,
        "query": {
            "q": q,
            "region": region,
            "theme": theme,
            "sort": sort,
        },
    }


@router.get("/suggestions")
async def get_search_suggestions(
    q: str = Query(..., min_length=1, description="자동완성 검색어"),
    db: Session = Depends(get_db),
):
    """검색 자동완성 제안"""
    keyword = f"%{q}%"
    limit = 10

    # 지역 제안 (카테고리)
    regions = (
        db.query(Category.category_name)
        .filter(
            Category.category_type.in_(["country", "city", "region"]),
            Category.category_name.ilike(keyword),
        )
        .distinct()
        .limit(limit)
        .all()
    )

    # 태그 제안 (게시글 태그에서)
    posts_with_tags = (
        db.query(Post.tags)
        .filter(Post.tags.ilike(keyword))
        .limit(50)
        .all()
    )
    tag_set = set()
    for (tags_str,) in posts_with_tags:
        if tags_str:
            try:
                tags = json.loads(tags_str) if isinstance(tags_str, str) else tags_str
                if isinstance(tags, list):
                    for t in tags:
                        if q.lower() in t.lower():
                            tag_set.add(t)
            except (json.JSONDecodeError, TypeError):
                pass

    return {
        "regions": [r[0] for r in regions],
        "tags": list(tag_set)[:limit],
    }


@router.get("/semantic")
async def semantic_search(
    q: str = Query(..., min_length=1, description="자연어 검색어 (예: 바다 보이는 카페)"),
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """
    LLM 기반 의미 검색: 자연어 질의 → 키워드 확장 → DB 검색
    예) "바다 보이는 카페" → [바다, 카페, 해변, 오션뷰, 해안, ...]
    """
    try:
        # LLM으로 검색어 확장
        expand_prompt = f"""다음 여행 검색어를 한국어 검색 키워드 목록으로 확장해주세요.

검색어: "{q}"

아래 JSON 형식으로만 응답하세요. 관련 장소/테마/활동을 포함한 5~10개의 키워드:
{{"keywords": ["키워드1", "키워드2", "키워드3"]}}"""

        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser
        from app.services.llm_factory import get_default_llm
        _expand_prompt = ChatPromptTemplate.from_messages([
            ("system", "당신은 여행 검색 전문가입니다. 검색어를 관련 키워드로 확장합니다."),
            ("human", expand_prompt),
        ])
        _expand_chain = _expand_prompt | get_default_llm() | StrOutputParser()
        response = await _expand_chain.ainvoke({})
        data = parse_llm_json(response)
        keywords = data.get("keywords", [q])
    except Exception:
        keywords = [q]

    # 확장된 키워드로 DB 검색
    conditions = []
    for kw in keywords[:8]:  # 최대 8개 키워드
        kw_like = f"%{kw}%"
        conditions.append(Post.title.ilike(kw_like))
        conditions.append(Post.description.ilike(kw_like))
        conditions.append(Post.tags.ilike(kw_like))

    query = db.query(Post).filter(Post.deleted_at.is_(None)).options(joinedload(Post.photos)).filter(or_(*conditions)) if conditions else db.query(Post).filter(Post.deleted_at.is_(None)).options(joinedload(Post.photos))
    query = query.order_by(Post.created_at.desc())

    posts = query.limit(limit * 2).all()

    # 작성자 캐시
    sem_author_cache: dict = {}

    def _get_sem_author(user_id: str):
        if user_id in sem_author_cache:
            return sem_author_cache[user_id]
        user_obj = db.query(User).filter(User.id == user_id).first()
        if user_obj:
            display_name = (
                user_obj.name
                or (user_obj.email.split('@')[0] if user_obj.email else None)
                or user_id.split('|')[-1]
            )
            info = {"id": user_obj.id, "name": display_name, "picture": user_obj.picture}
        else:
            info = {"id": user_id, "name": user_id.split('|')[-1], "picture": None}
        sem_author_cache[user_id] = info
        return info

    # 중복 제거 + 결과 구성
    seen = set()
    results = []
    for p in posts:
        if p.id in seen or len(results) >= limit:
            continue
        seen.add(p.id)
        likes_count = db.query(func.count(PostLike.id)).filter(PostLike.post_id == p.id).scalar()
        tags = p.tags
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except Exception:
                tags = []
        thumbnail_url = None
        if p.photos:
            thumbnail_url = s3_service.generate_download_url_sync(p.photos[0].file_key)
        results.append({
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "tags": tags,
            "created_at": p.created_at.isoformat(),
            "user_id": p.user_id,
            "photo_count": len(p.photos),
            "likes_count": likes_count,
            "thumbnail_url": thumbnail_url,
            "author": _get_sem_author(p.user_id),
        })

    return {
        "posts": results,
        "query": q,
        "expanded_keywords": keywords,
        "total": len(results),
    }


@router.get("/similar/{post_id}")
async def get_similar_posts(
    post_id: int,
    k: int = Query(5, ge=1, le=20, description="반환할 유사 게시글 수"),
    db: Session = Depends(get_db),
):
    """
    RAG 벡터 검색 기반 유사 여행 게시글 추천.
    TripDetailPage '이런 여행은 어때요?' 섹션에서 호출.
    """
    post = db.query(Post).filter(Post.deleted_at.is_(None)).filter(Post.id == post_id).first()
    if not post:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

    try:
        from app.services.rag_service import rag_service
        query_text = f"{post.title or ''} {post.tags or ''}"
        similar = await rag_service.search_similar(query=query_text, k=k + 1)
        # 자기 자신 제외
        similar = [s for s in similar if s.get("post_id") != str(post_id)][:k]

        # DB에서 상세 정보 보완
        results = []
        for item in similar:
            p = db.query(Post).filter(Post.deleted_at.is_(None)).options(joinedload(Post.photos)).filter(
                Post.id == int(item["post_id"]),
                Post.status == "published",
            ).first()
            if not p:
                continue
            thumbnail_url = None
            if p.photos:
                thumbnail_url = s3_service.generate_download_url_sync(p.photos[0].file_key)
            tags = p.tags
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except Exception:
                    tags = []
            results.append({
                "id": p.id,
                "title": p.title,
                "tags": tags,
                "thumbnail_url": thumbnail_url,
                "similarity_score": item.get("score"),
            })

        return {"post_id": post_id, "similar_posts": results}

    except Exception as e:
        logger.error(f"유사 게시글 추천 실패: {e}")
        return {"post_id": post_id, "similar_posts": []}
