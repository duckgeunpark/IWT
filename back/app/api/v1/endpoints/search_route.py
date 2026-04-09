from fastapi import APIRouter, Depends, Query, Request
from typing import Optional, List
import logging
import json

from app.models.db_models import Post, Photo, Location, Category, PostLike
from app.db.session import get_db
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, and_, distinct
from app.services.llm_route_recommend import LLMRouteRecommendService

llm_route_service = LLMRouteRecommendService()

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
    query = db.query(Post).options(joinedload(Post.photos))

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
            photo_count_sub.c.cnt.desc().nullslast()
        )
    elif sort == "most_liked":
        like_count_sub = (
            db.query(PostLike.post_id, func.count(PostLike.id).label("cnt"))
            .group_by(PostLike.post_id)
            .subquery()
        )
        query = query.outerjoin(like_count_sub, Post.id == like_count_sub.c.post_id).order_by(
            like_count_sub.c.cnt.desc().nullslast()
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
                "categories": category_map,
                "locations": [
                    {
                        "country": loc.country,
                        "city": loc.city,
                        "lat": loc.latitude,
                        "lng": loc.longitude,
                    }
                    for loc in locations[:5]  # 최대 5개 위치만
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

        response = await llm_route_service.llm.provider.chat_completion(
            messages=[
                {"role": "system", "content": "당신은 여행 검색 전문가입니다. 검색어를 관련 키워드로 확장합니다."},
                {"role": "user", "content": expand_prompt},
            ],
            temperature=0.1,
            max_tokens=150,
        )
        data = llm_route_service._parse_llm_json(response)
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

    query = db.query(Post).filter(or_(*conditions)) if conditions else db.query(Post)
    query = query.order_by(Post.created_at.desc())

    posts = query.limit(limit * 2).all()

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
        thumbnail = next((ph for ph in p.photos if ph.file_key), None)
        results.append({
            "id": p.id,
            "title": p.title,
            "description": p.description,
            "tags": tags,
            "created_at": p.created_at.isoformat(),
            "user_id": p.user_id,
            "photo_count": len(p.photos),
            "likes_count": likes_count,
        })

    return {
        "posts": results,
        "query": q,
        "expanded_keywords": keywords,
        "total": len(results),
    }
