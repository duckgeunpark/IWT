from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
import logging
import json
from datetime import datetime

from app.core.auth import get_current_user, get_optional_current_user
from app.models.db_models import PostLike, PostBookmark, Comment
from sqlalchemy import func, or_
from app.schemas.post import (
    PostCreateRequest,
    PostResponse,
    PostListResponse,
    PostUpdateRequest
)
from app.models.db_models import Post, Photo, Location, Category, User
from app.db.session import get_db
from sqlalchemy.orm import Session, joinedload
from app.services.llm_route_recommend import LLMRouteRecommendService
from app.services.s3_presigned_url import S3PresignedURLService
from app.services.labeling_service import LabelingService
from app.services.photo_filter_service import photo_filter
from app.services.reverse_geocoder import geocoder_service

router = APIRouter(prefix="/posts", tags=["posts"])

logger = logging.getLogger(__name__)

# 서비스 인스턴스
llm_service = LLMRouteRecommendService()
s3_service = S3PresignedURLService()
labeling_service = LabelingService()


def _build_post_response(post: Post, db: Session, current_user_id: Optional[str] = None) -> PostResponse:
    """Post 모델 → PostResponse 변환 (소셜 정보 포함)"""
    likes_count = db.query(func.count(PostLike.id)).filter(PostLike.post_id == post.id).scalar() or 0
    comments_count = db.query(func.count(Comment.id)).filter(Comment.post_id == post.id).scalar() or 0

    is_liked = False
    is_bookmarked = False
    if current_user_id:
        is_liked = db.query(PostLike).filter(
            PostLike.post_id == post.id, PostLike.user_id == current_user_id
        ).first() is not None
        is_bookmarked = db.query(PostBookmark).filter(
            PostBookmark.post_id == post.id, PostBookmark.user_id == current_user_id
        ).first() is not None

    # 썸네일: 첫 번째 사진의 presigned URL (동기)
    thumbnail_url = None
    if post.photos:
        thumbnail_url = s3_service.generate_download_url_sync(post.photos[0].file_key)

    # 작성자 정보
    author_obj = db.query(User).filter(User.id == post.user_id).first()
    from app.schemas.post import PostAuthor
    if author_obj:
        _display_name = (
            author_obj.name
            or (author_obj.email.split('@')[0] if author_obj.email else None)
            or post.user_id.split('|')[-1]
        )
        author = PostAuthor(id=author_obj.id, name=_display_name, picture=author_obj.picture)
    else:
        author = None

    return PostResponse(
        id=post.id,
        title=post.title,
        description=post.description,
        tags=json.loads(post.tags) if post.tags else [],
        status=getattr(post, 'status', 'published'),
        created_at=post.created_at,
        updated_at=post.updated_at,
        photo_count=len(post.photos),
        user_id=post.user_id,
        thumbnail_url=thumbnail_url,
        likes_count=likes_count,
        comments_count=comments_count,
        is_liked=is_liked,
        is_bookmarked=is_bookmarked,
        author=author,
    )

@router.post("/", response_model=PostResponse)
async def create_post(
    request: PostCreateRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    새로운 여행 게시글 생성
    """
    try:
        # 사용자 자동 등록 (FK 제약 조건 충족)
        user_id = current_user['sub']
        existing_user = db.query(User).filter(User.id == user_id).first()
        if not existing_user:
            new_user = User(
                id=user_id,
                email=current_user.get('email', f'{user_id}@unknown.com'),
                name=current_user.get('name'),
                picture=current_user.get('picture'),
            )
            db.add(new_user)
            db.flush()

        # 게시글 생성
        post = Post(
            title=request.title,
            description=request.description,
            tags=json.dumps(request.tags, ensure_ascii=False),
            status=request.status,
            user_id=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(post)
        db.flush()  # ID 생성
        
        # 사진 정보 저장
        for photo_data in request.photos:
            photo = Photo(
                post_id=post.id,
                file_key=photo_data.file_key,
                file_name=photo_data.file_name,
                file_size=photo_data.file_size,
                content_type=photo_data.content_type,
                upload_time=datetime.utcnow()
            )
            db.add(photo)
            db.flush()  # photo.id 생성
            
            # 위치 정보 저장
            if photo_data.location_info:
                location = Location(
                    photo_id=photo.id,
                    country=photo_data.location_info.country,
                    city=photo_data.location_info.city,
                    region=photo_data.location_info.region,
                    landmark=photo_data.location_info.landmark,
                    address=photo_data.location_info.address,
                    latitude=photo_data.location_info.coordinates.latitude if photo_data.location_info.coordinates else None,
                    longitude=photo_data.location_info.coordinates.longitude if photo_data.location_info.coordinates else None,
                    confidence=photo_data.location_info.confidence
                )
                db.add(location)
            
            # 라벨링 데이터 저장 (LLM 분석 결과가 있는 경우)
            if hasattr(photo_data, 'llm_analysis') and photo_data.llm_analysis:
                # EXIF 라벨 저장
                if hasattr(photo_data, 'exif_data') and photo_data.exif_data:
                    await labeling_service.save_exif_labels(db, photo.id, photo_data.exif_data)
                
                # LLM 분석 결과 저장
                for analysis_type, analysis_data in photo_data.llm_analysis.get('results', {}).items():
                    await labeling_service.save_llm_analysis(
                        db, photo.id, analysis_type, analysis_data, 
                        confidence=analysis_data.get('confidence', 0.8), 
                        model_used="gemini"
                    )
                
                # LLM 라벨 저장
                if hasattr(photo_data, 'labeling_data') and photo_data.labeling_data:
                    await labeling_service.save_llm_labels(db, photo.id, photo_data.labeling_data)
                
                # 이미지 메타데이터 저장
                if hasattr(photo_data, 'exif_data') and photo_data.exif_data:
                    await labeling_service.save_image_metadata(db, photo.id, "exif", photo_data.exif_data)
        
        # 카테고리 정보 저장
        if request.categories:
            for category_type, category_names in request.categories.items():
                for category_name in category_names:
                    category = Category(
                        post_id=post.id,
                        category_type=category_type,
                        category_name=category_name
                    )
                    db.add(category)
        
        # 추천 경로 정보 저장
        if request.selected_route:
            # 추천 경로 정보를 JSON으로 저장하거나 별도 테이블에 저장
            post.recommended_route = request.selected_route
        
        db.commit()
        
        tags_list = json.loads(post.tags) if post.tags else []
        return PostResponse(
            id=post.id,
            title=post.title,
            description=post.description,
            tags=tags_list,
            created_at=post.created_at,
            photo_count=len(request.photos),
            user_id=post.user_id
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"게시글 생성 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="게시글 생성에 실패했습니다.")

@router.post("/auto-create", response_model=PostResponse)
async def auto_create_post(
    photos: List[dict],  # PhotoData 형식의 리스트
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사진들을 자동으로 분석하여 게시글 생성
    """
    try:
        # PhotoData 객체로 변환
        from app.schemas.photo import PhotoData, LocationInfo, Coordinates
        
        # ── 1단계: 묶음 데이터 정제 (GPS 이상치 + 구간 분리) ────
        clean_result = photo_filter.clean_batch(photos)
        logger.info(
            f"사진 정제 완료 | 입력 {clean_result['summary']['total_input']}장 → "
            f"활용 {clean_result['summary']['total_usable']}장 / "
            f"제거 {clean_result['summary']['total_removed']}장"
        )

        # 활용 가능한 사진만 추출 (전체 구간 펼치기)
        usable_photos = [
            p for seg in clean_result["segments"] for p in seg["photos"]
        ]

        if not usable_photos:
            raise HTTPException(status_code=422, detail="활용 가능한 사진이 없습니다. GPS 데이터 또는 촬영 날짜를 확인해주세요.")

        # ── 2단계: Nominatim으로 GPS → 위치명 변환 ──────────────
        for photo_dict in usable_photos:
            lat = photo_dict.get("_lat")
            lon = photo_dict.get("_lon")
            if lat and lon and not photo_dict.get("location_info"):
                try:
                    addr = await geocoder_service.reverse_geocode(lat, lon)
                    photo_dict["location_info"] = {
                        "country": addr.get("country"),
                        "city": addr.get("city"),
                        "region": addr.get("state"),
                        "address": addr.get("full_address"),
                        "coordinates": {"latitude": lat, "longitude": lon},
                    }
                except Exception as geo_err:
                    logger.warning(f"역지오코딩 실패: {geo_err}")

        # ── 3단계: PhotoData 객체 변환 ───────────────────────────
        photo_data_list = []
        for photo_dict in usable_photos:
            location_info = None
            if photo_dict.get("location_info"):
                loc = photo_dict["location_info"]
                coordinates = None
                if loc.get("coordinates"):
                    coordinates = Coordinates(
                        latitude=loc["coordinates"]["latitude"],
                        longitude=loc["coordinates"]["longitude"],
                    )
                location_info = LocationInfo(
                    country=loc.get("country"),
                    city=loc.get("city"),
                    region=loc.get("region"),
                    landmark=loc.get("landmark"),
                    address=loc.get("address"),
                    coordinates=coordinates,
                    confidence=loc.get("confidence"),
                )

            photo_data = PhotoData(
                file_key=photo_dict["file_key"],
                file_name=photo_dict["file_name"],
                file_size=photo_dict["file_size"],
                content_type=photo_dict["content_type"],
                location_info=location_info,
                exif_data=photo_dict.get("exif_data"),
            )
            photo_data_list.append(photo_data)

        # ── 4단계: LLM — 정제된 데이터로 게시글 콘텐츠 생성 ─────
        travel_summary = await llm_service.generate_travel_summary(photo_data_list)
        travel_tags = await llm_service.generate_travel_tags(photo_data_list)
        route_analysis = await llm_service.analyze_travel_route(photo_data_list)
        
        # 게시글 생성
        post = Post(
            title=travel_summary.get("title", "여행 기록"),
            description=travel_summary.get("description", "여행 사진을 업로드했습니다."),
            tags=travel_tags,
            user_id=current_user['sub'],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            recommended_route={
                **route_analysis,
                "segments": clean_result["segments"],
                "usage_report": clean_result["usage_report"],
                "clean_summary": clean_result["summary"],
            },
        )
        
        db.add(post)
        db.flush()
        
        # 사진 정보 저장 및 임시 파일을 영구 저장소로 이동
        for photo_data in photo_data_list:
            # 임시 파일을 영구 저장소로 이동
            temp_key = photo_data.file_key
            permanent_key = f"post/{current_user['sub']}/{post.id}/{photo_data.file_name}"
            
            move_success = await s3_service.move_temp_to_permanent(
                temp_key=temp_key,
                permanent_key=permanent_key
            )
            
            if move_success:
                photo = Photo(
                    post_id=post.id,
                    file_key=permanent_key,
                    file_name=photo_data.file_name,
                    file_size=photo_data.file_size,
                    content_type=photo_data.content_type,
                    upload_time=datetime.utcnow()
                )
                db.add(photo)
                
                # 위치 정보 저장
                if photo_data.location_info:
                    location = Location(
                        photo_id=photo.id,
                        country=photo_data.location_info.country,
                        city=photo_data.location_info.city,
                        region=photo_data.location_info.region,
                        landmark=photo_data.location_info.landmark,
                        address=photo_data.location_info.address,
                        latitude=photo_data.location_info.coordinates.latitude if photo_data.location_info.coordinates else None,
                        longitude=photo_data.location_info.coordinates.longitude if photo_data.location_info.coordinates else None,
                        confidence=photo_data.location_info.confidence
                    )
                    db.add(location)
                
                # 라벨링 데이터 저장 (LLM 분석 결과가 있는 경우)
                if hasattr(photo_data, 'llm_analysis') and photo_data.llm_analysis:
                    # EXIF 라벨 저장
                    if hasattr(photo_data, 'exif_data') and photo_data.exif_data:
                        await labeling_service.save_exif_labels(db, photo.id, photo_data.exif_data)
                    
                    # LLM 분석 결과 저장
                    for analysis_type, analysis_data in photo_data.llm_analysis.get('results', {}).items():
                        await labeling_service.save_llm_analysis(
                            db, photo.id, analysis_type, analysis_data, 
                            confidence=analysis_data.get('confidence', 0.8), 
                            model_used="gemini"
                        )
                    
                    # LLM 라벨 저장
                    if hasattr(photo_data, 'labeling_data') and photo_data.labeling_data:
                        await labeling_service.save_llm_labels(db, photo.id, photo_data.labeling_data)
                    
                    # 이미지 메타데이터 저장
                    if hasattr(photo_data, 'exif_data') and photo_data.exif_data:
                        await labeling_service.save_image_metadata(db, photo.id, "exif", photo_data.exif_data)
        
        # 카테고리 정보 자동 생성
        countries = set()
        cities = set()
        for photo_data in photo_data_list:
            if photo_data.location_info:
                if photo_data.location_info.country:
                    countries.add(photo_data.location_info.country)
                if photo_data.location_info.city:
                    cities.add(photo_data.location_info.city)
        
        # 카테고리 저장
        for country in countries:
            category = Category(
                post_id=post.id,
                category_type="country",
                category_name=country
            )
            db.add(category)
        
        for city in cities:
            category = Category(
                post_id=post.id,
                category_type="city",
                category_name=city
            )
            db.add(category)
        
        db.commit()
        
        return PostResponse(
            id=post.id,
            title=post.title,
            description=post.description,
            tags=json.loads(post.tags) if post.tags else [],
            created_at=post.created_at,
            photo_count=len(photo_data_list),
            user_id=post.user_id
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"자동 게시글 생성 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="자동 게시글 생성에 실패했습니다.")

@router.post("/preview")
async def preview_post(
    photos: List[dict],
    current_user = Depends(get_current_user)
):
    """
    게시글 미리보기 생성 (DB 저장 없이)
    """
    try:
        # PhotoData 객체로 변환
        from app.schemas.photo import PhotoData, LocationInfo, Coordinates
        
        photo_data_list = []
        for photo_dict in photos:
            location_info = None
            if photo_dict.get("location_info"):
                loc = photo_dict["location_info"]
                coordinates = None
                if loc.get("coordinates"):
                    coordinates = Coordinates(
                        latitude=loc["coordinates"]["latitude"],
                        longitude=loc["coordinates"]["longitude"]
                    )
                location_info = LocationInfo(
                    country=loc.get("country"),
                    city=loc.get("city"),
                    region=loc.get("region"),
                    landmark=loc.get("landmark"),
                    address=loc.get("address"),
                    coordinates=coordinates,
                    confidence=loc.get("confidence")
                )
            
            photo_data = PhotoData(
                file_key=photo_dict["file_key"],
                file_name=photo_dict["file_name"],
                file_size=photo_dict["file_size"],
                content_type=photo_dict["content_type"],
                location_info=location_info,
                exif_data=photo_dict.get("exif_data")
            )
            photo_data_list.append(photo_data)
        
        # LLM을 통한 미리보기 생성
        travel_summary = await llm_service.generate_travel_summary(photo_data_list)
        travel_tags = await llm_service.generate_travel_tags(photo_data_list)
        route_analysis = await llm_service.analyze_travel_route(photo_data_list)
        photo_descriptions = await llm_service.generate_photo_descriptions(photo_data_list)
        
        return {
            "preview": {
                "title": travel_summary.get("title", "여행 기록"),
                "description": travel_summary.get("description", "여행 사진을 업로드했습니다."),
                "tags": travel_tags,
                "route_analysis": route_analysis,
                "photo_descriptions": photo_descriptions,
                "photo_count": len(photo_data_list)
            }
        }
        
    except Exception as e:
        logger.error(f"게시글 미리보기 생성 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="게시글 미리보기 생성에 실패했습니다.")

@router.get("/user/{user_id}", response_model=PostListResponse)
async def get_user_posts(
    user_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    include_drafts: bool = Query(False),
    current_user = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """특정 사용자의 게시글 목록 조회 (본인 요청 시 draft 포함)"""
    try:
        current_user_id = current_user["sub"] if current_user else None
        is_owner = current_user_id == user_id

        base_filter = [Post.user_id == user_id]
        if not (is_owner and include_drafts):
            base_filter.append(Post.status == 'published')

        query = db.query(Post).options(joinedload(Post.photos)).filter(
            *base_filter
        ).order_by(Post.created_at.desc())

        total = db.query(func.count(Post.id)).filter(*base_filter).scalar()
        posts = query.offset(skip).limit(limit).all()

        return PostListResponse(
            posts=[_build_post_response(p, db, current_user_id) for p in posts],
            total=total,
            skip=skip,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"사용자 게시글 목록 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="사용자 게시글 목록 조회에 실패했습니다.")


@router.get("/", response_model=PostListResponse)
async def get_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    user_id: Optional[str] = None,
    category: Optional[str] = None,
    current_user = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """게시글 목록 조회"""
    try:
        count_query = db.query(Post).filter(Post.status == 'published')

        if user_id:
            count_query = count_query.filter(Post.user_id == user_id)
        if category:
            count_query = count_query.join(Category).filter(Category.category_name == category)

        total = count_query.count()
        posts = count_query.options(
            joinedload(Post.photos)
        ).order_by(Post.created_at.desc()).offset(skip).limit(limit).all()

        current_user_id = current_user["sub"] if current_user else None
        return PostListResponse(
            posts=[_build_post_response(p, db, current_user_id) for p in posts],
            total=total,
            skip=skip,
            limit=limit,
        )

    except Exception as e:
        logger.error(f"게시글 목록 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="게시글 목록 조회에 실패했습니다.")

@router.get("/bookmarked", response_model=dict)
async def get_bookmarked_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """북마크한 게시글 목록 (post_route에서 /{post_id} 보다 먼저 처리)"""
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
        "posts": [_build_post_response(p, db, user_id) for p in posts],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: int,
    current_user = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """특정 게시글 조회"""
    try:
        post = db.query(Post).options(joinedload(Post.photos)).filter(Post.id == post_id).first()

        if not post:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

        current_user_id = current_user["sub"] if current_user else None
        return _build_post_response(post, db, current_user_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"게시글 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="게시글 조회에 실패했습니다.")

@router.get("/{post_id}/photos")
async def get_post_photos(
    post_id: int,
    current_user = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    게시글 사진 목록 조회 (S3 presigned URL 포함)
    """
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

        photos = db.query(Photo).filter(Photo.post_id == post_id).order_by(Photo.upload_time).all()

        photo_list = []
        for photo in photos:
            url = await s3_service.generate_download_url(photo.file_key)
            location = None
            if photo.location:
                loc = photo.location
                location = {
                    "lat": loc.latitude,
                    "lng": loc.longitude,
                    "country": loc.country,
                    "city": loc.city,
                    "address": loc.address,
                }
            photo_list.append({
                "id": photo.id,
                "file_name": photo.file_name,
                "file_size": photo.file_size,
                "content_type": photo.content_type,
                "url": url,
                "location": location,
                "upload_time": photo.upload_time.isoformat() if photo.upload_time else None,
            })

        return {"photos": photo_list, "total": len(photo_list)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"게시글 사진 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="게시글 사진 조회에 실패했습니다.")


@router.get("/{post_id}/similar")
async def get_similar_posts(
    post_id: int,
    limit: int = Query(6, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """
    유사 여행 추천: 같은 나라/도시 방문, 공통 태그, 비슷한 시기 기준
    """
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")

        # 이 게시글의 태그와 방문 국가/도시 수집
        post_tags = []
        if post.tags:
            try:
                post_tags = json.loads(post.tags) if isinstance(post.tags, str) else post.tags
            except Exception:
                pass

        locations = (
            db.query(Location)
            .join(Photo, Photo.id == Location.photo_id)
            .filter(Photo.post_id == post_id)
            .all()
        )
        countries = list({loc.country for loc in locations if loc.country})
        cities = list({loc.city for loc in locations if loc.city})

        # 유사 게시글 쿼리: 공통 나라/도시 또는 공통 태그
        conditions = []
        for tag in post_tags[:5]:
            if tag:
                conditions.append(Post.tags.ilike(f"%{tag}%"))
        for country in countries[:3]:
            post_ids_country = (
                db.query(Photo.post_id)
                .join(Location, Location.photo_id == Photo.id)
                .filter(Location.country == country)
                .subquery()
            )
            conditions.append(Post.id.in_(post_ids_country))
        for city in cities[:3]:
            post_ids_city = (
                db.query(Photo.post_id)
                .join(Location, Location.photo_id == Photo.id)
                .filter(Location.city == city)
                .subquery()
            )
            conditions.append(Post.id.in_(post_ids_city))

        if not conditions:
            # 공통점이 없으면 최신 인기 게시글
            similar = (
                db.query(Post)
                .filter(Post.id != post_id)
                .order_by(Post.created_at.desc())
                .limit(limit)
                .all()
            )
        else:
            similar = (
                db.query(Post)
                .filter(Post.id != post_id, or_(*conditions))
                .order_by(Post.created_at.desc())
                .limit(limit * 2)
                .all()
            )

        # 중복 제거 및 결과 구성
        seen = set()
        results = []
        for p in similar:
            if p.id in seen or len(results) >= limit:
                continue
            seen.add(p.id)
            likes_count = db.query(func.count(PostLike.id)).filter(PostLike.post_id == p.id).scalar()
            p_tags = p.tags
            if isinstance(p_tags, str):
                try:
                    p_tags = json.loads(p_tags)
                except Exception:
                    p_tags = []
            thumbnail_url = None
            if p.photos:
                try:
                    thumbnail_url = await s3_service.generate_download_url(p.photos[0].file_key)
                except Exception:
                    pass
            results.append({
                "id": p.id,
                "title": p.title,
                "description": (p.description or "")[:100],
                "tags": p_tags,
                "created_at": p.created_at.isoformat(),
                "user_id": p.user_id,
                "photo_count": len(p.photos),
                "likes_count": likes_count,
                "thumbnail_url": thumbnail_url,
            })

        return {"posts": results, "total": len(results)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"유사 게시글 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="유사 게시글 조회에 실패했습니다.")


@router.put("/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: int,
    request: PostUpdateRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    게시글 수정
    """
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        
        if not post:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
        
        # 권한 확인
        if post.user_id != current_user['sub']:
            raise HTTPException(status_code=403, detail="게시글을 수정할 권한이 없습니다.")
        
        # 제목/내용/태그/상태 업데이트
        if request.title is not None:
            post.title = request.title
        if request.description is not None:
            post.description = request.description
        if request.tags is not None:
            post.tags = json.dumps(request.tags, ensure_ascii=False)
        if request.status is not None:
            post.status = request.status

        # 사진 업데이트 (keep_photo_ids가 전달된 경우)
        if request.keep_photo_ids is not None:
            # 유지 목록에 없는 기존 사진 삭제
            for photo in list(post.photos):
                if photo.id not in request.keep_photo_ids:
                    db.delete(photo)

            # 새 사진 추가
            if request.new_photos:
                for photo_data in request.new_photos:
                    new_photo = Photo(
                        post_id=post.id,
                        file_key=photo_data['file_key'],
                        file_name=photo_data['file_name'],
                        file_size=photo_data.get('file_size', 0),
                        content_type=photo_data.get('content_type', 'image/jpeg'),
                    )
                    db.add(new_photo)

        post.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(post)

        return PostResponse(
            id=post.id,
            title=post.title,
            description=post.description,
            tags=json.loads(post.tags) if post.tags else [],
            status=getattr(post, 'status', 'published'),
            created_at=post.created_at,
            photo_count=len(post.photos),
            user_id=post.user_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"게시글 수정 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="게시글 수정에 실패했습니다.")

@router.delete("/{post_id}")
async def delete_post(
    post_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    게시글 삭제
    """
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        
        if not post:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
        
        # 권한 확인
        if post.user_id != current_user['sub']:
            raise HTTPException(status_code=403, detail="게시글을 삭제할 권한이 없습니다.")
        
        # 관련 데이터 삭제 (CASCADE 설정에 따라 자동 삭제될 수도 있음)
        db.delete(post)
        db.commit()
        
        return {"message": "게시글이 삭제되었습니다."}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"게시글 삭제 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="게시글 삭제에 실패했습니다.")

