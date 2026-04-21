from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
import logging
import json
from datetime import datetime

from app.core.auth import get_current_user, get_optional_current_user
from app.models.db_models import PostLike, PostBookmark, Comment, Post, Photo, Location, Category, User, UserLLMPreference
from sqlalchemy import func, or_
from app.schemas.post import (
    PostCreateRequest,
    PostResponse,
    PostListResponse,
    PostUpdateRequest
)
from app.db.session import get_db
from sqlalchemy.orm import Session, joinedload
from app.services.s3_presigned_url import S3PresignedURLService
from app.services.labeling_service import LabelingService
from app.services.photo_filter_service import photo_filter
from app.services.reverse_geocoder import geocoder_service
from app.services.llm_pipeline import get_llm_pipeline
from app.services.photo_cluster import cluster_photos_by_location

router = APIRouter(prefix="/posts", tags=["posts"])

logger = logging.getLogger(__name__)

# 서비스 인스턴스
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

        # ── 3단계: 클러스터링 ────────────────────────────────────────
        cluster_input = []
        for p in usable_photos:
            lat = p.get("_lat")
            lon = p.get("_lon")
            cluster_input.append({
                **p,
                "gps": {"lat": lat, "lng": lon} if (lat and lon) else None,
                "taken_at": (p.get("exif_data") or {}).get("datetime"),
            })

        raw_clusters = cluster_photos_by_location(cluster_input)

        # 날짜 기준 일차 계산
        date_to_day: dict = {}
        for cluster in raw_clusters:
            start = cluster.get("start_time")
            if start:
                d = start[:10]
                if d not in date_to_day:
                    date_to_day[d] = len(date_to_day) + 1

        # 파이프라인용 클러스터 구성 (대표사진 URL 포함)
        pipeline_clusters = []
        for i, cluster in enumerate(raw_clusters):
            start = cluster.get("start_time")
            date_str = start[:10] if start else None
            day = date_to_day.get(date_str, 1)

            cluster_photo_list = cluster["photos"]
            rep_photo = max(cluster_photo_list, key=lambda p: p.get("file_size", 0))
            try:
                rep_url = await s3_service.generate_download_url(rep_photo["file_key"])
            except Exception:
                rep_url = ""

            loc_info = next(
                (p["location_info"] for p in cluster_photo_list if p.get("location_info")),
                None,
            )
            location_name = (
                loc_info.get("landmark") or loc_info.get("city") or loc_info.get("region") or "알 수 없는 장소"
                if loc_info else "알 수 없는 장소"
            )

            pipeline_clusters.append({
                "cluster_id": i,
                "day": day,
                "location_name": location_name,
                "location_info": {
                    "country": loc_info.get("country", "") if loc_info else "",
                    "city": loc_info.get("city", "") if loc_info else "",
                    "address": loc_info.get("address", "") if loc_info else "",
                },
                # photos 포함 → 증분 업데이트 fingerprint 계산에 사용
                "photos": [{"file_key": p.get("file_key", "")} for p in cluster_photo_list],
                "representative_photo_url": rep_url,
                "photo_count": cluster["photo_count"],
                "start_time": cluster.get("start_time"),
                "end_time": cluster.get("end_time"),
            })

        # ── 4단계: 사용자 LLM 설정 로드 ─────────────────────────────
        user_id = current_user["sub"]
        user_pref_row = db.query(UserLLMPreference).filter(
            UserLLMPreference.user_id == user_id
        ).first()
        user_prefs = {
            "tone": user_pref_row.tone,
            "style": user_pref_row.style,
            "lang": user_pref_row.lang,
            "stage1_extra": user_pref_row.stage1_extra,
            "stage2_extra": user_pref_row.stage2_extra,
            "stage3_extra": user_pref_row.stage3_extra,
        } if user_pref_row else None

        # ── 5단계: LLM 파이프라인 실행 ───────────────────────────────
        pipeline = get_llm_pipeline()
        pipeline_result = await pipeline.run(pipeline_clusters, user_prefs)

        # 유저 자동 등록 (FK 제약 조건)
        existing_user = db.query(User).filter(User.id == user_id).first()
        if not existing_user:
            db.add(User(
                id=user_id,
                email=current_user.get("email", f"{user_id}@unknown.com"),
                name=current_user.get("name"),
                picture=current_user.get("picture"),
            ))
            db.flush()

        # 게시글 생성
        post = Post(
            title=pipeline_result["title"],
            description=pipeline_result["markdown"],
            tags=json.dumps(pipeline_result["tags"], ensure_ascii=False),
            status="published",
            user_id=user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            recommended_route=json.dumps({
                "itinerary_table": pipeline_result["itinerary_table"],
                "stage2_cache":    pipeline_result.get("stage2_cache", {}),
                "segments":        clean_result["segments"],
                "usage_report":    clean_result["usage_report"],
                "clean_summary":   clean_result["summary"],
            }, ensure_ascii=False),
        )
        db.add(post)
        db.flush()

        # ── 6단계: 사진 S3 이동 + DB 저장 ────────────────────────────
        for photo_dict in usable_photos:
            temp_key = photo_dict["file_key"]
            permanent_key = f"post/{user_id}/{post.id}/{photo_dict['file_name']}"

            move_success = await s3_service.move_temp_to_permanent(
                temp_key=temp_key,
                permanent_key=permanent_key,
            )

            if move_success:
                photo = Photo(
                    post_id=post.id,
                    file_key=permanent_key,
                    file_name=photo_dict["file_name"],
                    file_size=photo_dict["file_size"],
                    content_type=photo_dict["content_type"],
                    upload_time=datetime.utcnow(),
                )
                db.add(photo)
                db.flush()

                loc_info = photo_dict.get("location_info")
                if loc_info:
                    coords = loc_info.get("coordinates") or {}
                    db.add(Location(
                        photo_id=photo.id,
                        country=loc_info.get("country"),
                        city=loc_info.get("city"),
                        region=loc_info.get("region"),
                        landmark=loc_info.get("landmark"),
                        address=loc_info.get("address"),
                        latitude=coords.get("latitude") if coords else photo_dict.get("_lat"),
                        longitude=coords.get("longitude") if coords else photo_dict.get("_lon"),
                        confidence=loc_info.get("confidence"),
                    ))

        # 카테고리 저장 (국가/도시)
        countries = {
            p["location_info"]["country"]
            for p in usable_photos
            if (p.get("location_info") or {}).get("country")
        }
        cities = {
            p["location_info"]["city"]
            for p in usable_photos
            if (p.get("location_info") or {}).get("city")
        }
        for country in countries:
            db.add(Category(post_id=post.id, category_type="country", category_name=country))
        for city in cities:
            db.add(Category(post_id=post.id, category_type="city", category_name=city))

        db.commit()

        return PostResponse(
            id=post.id,
            title=post.title,
            description=post.description,
            tags=json.loads(post.tags) if post.tags else [],
            created_at=post.created_at,
            photo_count=len(usable_photos),
            user_id=post.user_id,
        )

    except HTTPException:
        raise
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
        # 클러스터링
        cluster_input = []
        for p in photos:
            lat = p.get("_lat") or (p.get("location_info") or {}).get("coordinates", {}).get("latitude")
            lon = p.get("_lon") or (p.get("location_info") or {}).get("coordinates", {}).get("longitude")
            cluster_input.append({
                **p,
                "gps": {"lat": lat, "lng": lon} if (lat and lon) else None,
                "taken_at": (p.get("exif_data") or {}).get("datetime"),
            })

        raw_clusters = cluster_photos_by_location(cluster_input)

        date_to_day: dict = {}
        for cluster in raw_clusters:
            start = cluster.get("start_time")
            if start:
                d = start[:10]
                if d not in date_to_day:
                    date_to_day[d] = len(date_to_day) + 1

        pipeline_clusters = []
        for i, cluster in enumerate(raw_clusters):
            start = cluster.get("start_time")
            date_str = start[:10] if start else None
            day = date_to_day.get(date_str, 1)

            cluster_photo_list = cluster["photos"]
            rep_photo = max(cluster_photo_list, key=lambda p: p.get("file_size", 0))
            try:
                rep_url = await s3_service.generate_download_url(rep_photo["file_key"])
            except Exception:
                rep_url = ""

            loc_info = next(
                (p["location_info"] for p in cluster_photo_list if p.get("location_info")),
                None,
            )
            location_name = (
                loc_info.get("landmark") or loc_info.get("city") or loc_info.get("region") or "알 수 없는 장소"
                if loc_info else "알 수 없는 장소"
            )

            pipeline_clusters.append({
                "cluster_id": i,
                "day": day,
                "location_name": location_name,
                "location_info": {
                    "country": loc_info.get("country", "") if loc_info else "",
                    "city": loc_info.get("city", "") if loc_info else "",
                    "address": loc_info.get("address", "") if loc_info else "",
                },
                "representative_photo_url": rep_url,
                "photo_count": cluster["photo_count"],
                "start_time": cluster.get("start_time"),
                "end_time": cluster.get("end_time"),
            })

        # 미리보기는 기본 preferences 사용
        pipeline = get_llm_pipeline()
        pipeline_result = await pipeline.run(pipeline_clusters, None)

        return {
            "preview": {
                "title": pipeline_result["title"],
                "markdown": pipeline_result["markdown"],
                "tags": pipeline_result["tags"],
                "itinerary_table": pipeline_result["itinerary_table"],
                "photo_count": len(photos),
                "cluster_count": len(pipeline_clusters),
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
                "file_key": photo.file_key,
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


@router.post("/{post_id}/ai-update")
async def ai_update_post(
    post_id: int,
    photos: List[dict],
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    편집창에서 'AI로 게시글 생성' 버튼 클릭 시 호출.

    - 변경된 클러스터만 Stage 2 재실행 (캐시 히트 시 재사용)
    - Stage 1 · Stage 3은 항상 재실행
    - post.description(마크다운) + recommended_route(캐시) 갱신
    """
    try:
        user_id = current_user["sub"]

        # 게시글 조회 + 권한 확인
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
        if post.user_id != user_id:
            raise HTTPException(status_code=403, detail="수정 권한이 없습니다.")

        # 기존 stage2_cache 추출
        existing_route = {}
        if post.recommended_route:
            try:
                existing_route = json.loads(post.recommended_route)
            except Exception:
                pass
        stage2_cache: dict = existing_route.get("stage2_cache", {})

        # ── 1단계: Nominatim 역지오코딩 ─────────────────────────────
        for photo_dict in photos:
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

        # ── 2단계: 클러스터링 ────────────────────────────────────────
        cluster_input = []
        for p in photos:
            lat = p.get("_lat")
            lon = p.get("_lon")
            cluster_input.append({
                **p,
                "gps": {"lat": lat, "lng": lon} if (lat and lon) else None,
                "taken_at": (p.get("exif_data") or {}).get("datetime"),
            })

        raw_clusters = cluster_photos_by_location(cluster_input)

        date_to_day: dict = {}
        for cluster in raw_clusters:
            start = cluster.get("start_time")
            if start:
                d = start[:10]
                if d not in date_to_day:
                    date_to_day[d] = len(date_to_day) + 1

        pipeline_clusters = []
        for i, cluster in enumerate(raw_clusters):
            start = cluster.get("start_time")
            date_str = start[:10] if start else None
            day = date_to_day.get(date_str, 1)

            cluster_photo_list = cluster["photos"]
            rep_photo = max(cluster_photo_list, key=lambda p: p.get("file_size", 0))
            try:
                rep_url = await s3_service.generate_download_url(rep_photo["file_key"])
            except Exception:
                rep_url = ""

            loc_info = next(
                (p["location_info"] for p in cluster_photo_list if p.get("location_info")),
                None,
            )
            location_name = (
                loc_info.get("landmark") or loc_info.get("city") or loc_info.get("region") or "알 수 없는 장소"
                if loc_info else "알 수 없는 장소"
            )

            pipeline_clusters.append({
                "cluster_id": i,
                "day": day,
                "location_name": location_name,
                "location_info": {
                    "country": loc_info.get("country", "") if loc_info else "",
                    "city":    loc_info.get("city", "") if loc_info else "",
                    "address": loc_info.get("address", "") if loc_info else "",
                },
                # photos 포함 → fingerprint 계산에 사용
                "photos": [{"file_key": p.get("file_key", "")} for p in cluster_photo_list],
                "representative_photo_url": rep_url,
                "photo_count": cluster["photo_count"],
                "start_time": cluster.get("start_time"),
                "end_time":   cluster.get("end_time"),
            })

        # ── 3단계: 사용자 LLM 설정 ───────────────────────────────────
        user_pref_row = db.query(UserLLMPreference).filter(
            UserLLMPreference.user_id == user_id
        ).first()
        user_prefs = {
            "tone":         user_pref_row.tone,
            "style":        user_pref_row.style,
            "lang":         user_pref_row.lang,
            "stage1_extra": user_pref_row.stage1_extra,
            "stage2_extra": user_pref_row.stage2_extra,
            "stage3_extra": user_pref_row.stage3_extra,
        } if user_pref_row else None

        # ── 4단계: 증분 파이프라인 실행 ──────────────────────────────
        pipeline = get_llm_pipeline()
        result = await pipeline.run_incremental(pipeline_clusters, stage2_cache, user_prefs)

        cache_stats = result.get("cache_stats", {})
        logger.info(
            f"ai-update post={post_id} | "
            f"hit={cache_stats.get('hit',0)} "
            f"miss={cache_stats.get('miss',0)} "
            f"removed={cache_stats.get('removed',0)}"
        )

        # ── 5단계: 포스트 갱신 ───────────────────────────────────────
        post.title       = result["title"]
        post.description = result["markdown"]
        post.tags        = json.dumps(result["tags"], ensure_ascii=False)
        post.updated_at  = datetime.utcnow()
        post.recommended_route = json.dumps({
            **existing_route,
            "itinerary_table": result["itinerary_table"],
            "stage2_cache":    result["stage2_cache"],
        }, ensure_ascii=False)

        db.commit()
        db.refresh(post)

        return {
            "id":           post.id,
            "title":        post.title,
            "markdown":     post.description,
            "tags":         json.loads(post.tags) if post.tags else [],
            "updated_at":   post.updated_at.isoformat(),
            "cache_stats":  cache_stats,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"AI 업데이트 실패 post={post_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="AI 게시글 업데이트에 실패했습니다.")


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

