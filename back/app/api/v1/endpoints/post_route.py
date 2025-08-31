from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
import logging
from datetime import datetime

from app.core.auth import get_current_user
from app.schemas.post import (
    PostCreateRequest,
    PostResponse,
    PostListResponse,
    PostUpdateRequest
)
from app.models.db_models import Post, Photo, Location, Category
from app.db.session import get_db
from sqlalchemy.orm import Session
from app.services.llm_route_recommend import LLMRouteRecommendService
from app.services.s3_presigned_url import S3PresignedURLService
from app.services.labeling_service import LabelingService

router = APIRouter(prefix="/posts", tags=["posts"])

logger = logging.getLogger(__name__)

# 서비스 인스턴스
llm_service = LLMRouteRecommendService()
s3_service = S3PresignedURLService()
labeling_service = LabelingService()

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
        # 게시글 생성
        post = Post(
            title=request.title,
            description=request.description,
            tags=request.tags,
            user_id=current_user['sub'],
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
                        model_used="groq"
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
        
        return PostResponse(
            id=post.id,
            title=post.title,
            description=post.description,
            tags=post.tags,
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
        
        # LLM을 통한 자동 분석
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
            recommended_route=route_analysis
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
                            model_used="groq"
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
            tags=post.tags,
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

@router.get("/", response_model=PostListResponse)
async def get_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    user_id: Optional[str] = None,
    category: Optional[str] = None,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    게시글 목록 조회
    """
    try:
        query = db.query(Post)
        
        # 사용자별 필터링
        if user_id:
            query = query.filter(Post.user_id == user_id)
        
        # 카테고리별 필터링
        if category:
            query = query.join(Category).filter(Category.category_name == category)
        
        # 최신순 정렬
        query = query.order_by(Post.created_at.desc())
        
        # 페이지네이션
        total = query.count()
        posts = query.offset(skip).limit(limit).all()
        
        return PostListResponse(
            posts=[
                PostResponse(
                    id=post.id,
                    title=post.title,
                    description=post.description,
                    tags=post.tags,
                    created_at=post.created_at,
                    photo_count=len(post.photos),
                    user_id=post.user_id
                ) for post in posts
            ],
            total=total,
            skip=skip,
            limit=limit
        )
        
    except Exception as e:
        logger.error(f"게시글 목록 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="게시글 목록 조회에 실패했습니다.")

@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    특정 게시글 조회
    """
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        
        if not post:
            raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
        
        return PostResponse(
            id=post.id,
            title=post.title,
            description=post.description,
            tags=post.tags,
            created_at=post.created_at,
            photo_count=len(post.photos),
            user_id=post.user_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"게시글 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="게시글 조회에 실패했습니다.")

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
        
        # 업데이트
        if request.title is not None:
            post.title = request.title
        if request.description is not None:
            post.description = request.description
        if request.tags is not None:
            post.tags = request.tags
        
        post.updated_at = datetime.utcnow()
        
        db.commit()
        
        return PostResponse(
            id=post.id,
            title=post.title,
            description=post.description,
            tags=post.tags,
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

@router.get("/user/{user_id}", response_model=PostListResponse)
async def get_user_posts(
    user_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    특정 사용자의 게시글 목록 조회
    """
    try:
        posts = db.query(Post).filter(
            Post.user_id == user_id
        ).order_by(
            Post.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        total = db.query(Post).filter(Post.user_id == user_id).count()
        
        return PostListResponse(
            posts=[
                PostResponse(
                    id=post.id,
                    title=post.title,
                    description=post.description,
                    tags=post.tags,
                    created_at=post.created_at,
                    photo_count=len(post.photos),
                    user_id=post.user_id
                ) for post in posts
            ],
            total=total,
            skip=skip,
            limit=limit
        )
        
    except Exception as e:
        logger.error(f"사용자 게시글 목록 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="사용자 게시글 목록 조회에 실패했습니다.") 