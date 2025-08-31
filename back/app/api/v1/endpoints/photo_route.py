from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import List, Optional
import logging
from datetime import datetime
import os
import json

from app.core.auth import get_current_user
from app.schemas.photo import (
    PresignedUrlRequest,
    PresignedUrlResponse,
    ExifExtractRequest,
    ExifExtractResponse,
    PhotoPreviewResponse,
    MoveFileRequest,
    PhotoData,
    LocationInfo,
    Coordinates
)
from app.services.s3_presigned_url import S3PresignedURLService
from app.services.exif_extract_service import ExifExtractService
from app.services.reverse_geocoder import ReverseGeocoderService
from app.services.llm_location_search import LLMLocationSearchService
from app.services.labeling_service import LabelingService
from app.db.session import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/photos", tags=["photos"])

logger = logging.getLogger(__name__)

# 서비스 인스턴스
s3_service = S3PresignedURLService()
exif_service = ExifExtractService()
geocoder_service = ReverseGeocoderService()
llm_location_service = LLMLocationSearchService()
labeling_service = LabelingService()

@router.post("/presigned-url", response_model=PresignedUrlResponse)
async def get_presigned_url(
    request: PresignedUrlRequest,
    current_user = Depends(get_current_user)
):
    """
    S3 업로드를 위한 presigned URL 생성
    """
    try:
        file_key = f"temp/{current_user['sub']}/{request.file_name}"
        presigned_url_data = await s3_service.generate_presigned_url(
            file_key=file_key,
            content_type=request.content_type
        )
        
        return PresignedUrlResponse(
            presigned_url=presigned_url_data["presigned_url"],
            file_key=presigned_url_data["file_key"],
            expires_in=presigned_url_data["expires_in"]
        )
    except Exception as e:
        logger.error(f"Presigned URL 생성 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="업로드 URL 생성에 실패했습니다.")

@router.post("/batch-presigned-urls", response_model=List[PresignedUrlResponse])
async def get_batch_presigned_urls(
    files: List[PresignedUrlRequest],
    current_user = Depends(get_current_user)
):
    """
    여러 파일의 presigned URL을 한 번에 생성
    """
    try:
        responses = []
        for file_request in files:
            file_key = f"temp/{current_user['sub']}/{file_request.file_name}"
            presigned_url_data = await s3_service.generate_presigned_url(
                file_key=file_key,
                content_type=file_request.content_type
            )
            
            responses.append(PresignedUrlResponse(
                presigned_url=presigned_url_data["presigned_url"],
                file_key=presigned_url_data["file_key"],
                expires_in=presigned_url_data["expires_in"]
            ))
        
        return responses
    except Exception as e:
        logger.error(f"배치 presigned URL 생성 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="업로드 URL 생성에 실패했습니다.")

@router.post("/extract-exif", response_model=ExifExtractResponse)
async def extract_exif(
    request: ExifExtractRequest,
    current_user = Depends(get_current_user)
):
    """
    프론트엔드에서 전송된 EXIF 데이터 처리
    """
    try:
        # 프론트엔드에서 전송된 EXIF 데이터 처리
        processed_exif_data = await exif_service.process_exif_data(request.exif_data)
        
        if processed_exif_data:
            return ExifExtractResponse(
                extraction_success=True,
                exif_data=processed_exif_data
            )
        else:
            return ExifExtractResponse(
                extraction_success=False,
                error_message="EXIF 데이터 처리에 실패했습니다."
            )
    except Exception as e:
        logger.error(f"EXIF 처리 실패: {str(e)}")
        return ExifExtractResponse(
            extraction_success=False,
            error_message=f"EXIF 처리 중 오류가 발생했습니다: {str(e)}"
        )

@router.post("/process-exif-with-llm")
async def process_exif_with_llm(
    request: ExifExtractRequest,
    current_user = Depends(get_current_user)
):
    """
    EXIF 데이터를 LLM 분석하여 결과를 프론트엔드로 반환
    (데이터베이스 저장은 게시글 생성 시 수행)
    """
    try:
        logger.info(f"EXIF 데이터 LLM 처리 시작 - user: {current_user['sub']}")
        
        # 1. EXIF 데이터 처리
        processed_exif_data = await exif_service.process_exif_data(request.exif_data)
        
        if not processed_exif_data:
            raise HTTPException(status_code=400, detail="EXIF 데이터 처리에 실패했습니다.")
        
        # 2. LLM 분석을 위한 데이터 준비
        llm_data = await exif_service.prepare_exif_for_llm(processed_exif_data)
        
        # 3. LLM 분석 수행
        llm_analysis_results = {}
        
        # 위치 정보가 있는 경우 LLM 분석
        if llm_data.get("location") and llm_data["location"].get("coordinates_available"):
            try:
                # LLM 위치 분석
                location_analysis = {
                    "type": "location_analysis",
                    "coordinates": {
                        "latitude": llm_data["location"]["latitude"],
                        "longitude": llm_data["location"]["longitude"]
                    },
                    "analysis": "위치 정보가 포함된 사진입니다.",
                    "confidence": 0.9
                }
                llm_analysis_results["location"] = location_analysis
            except Exception as e:
                logger.warning(f"LLM 위치 분석 실패: {str(e)}")
        
        # 시간 정보가 있는 경우 LLM 분석
        if llm_data.get("datetime"):
            try:
                time_analysis = {
                    "type": "time_analysis",
                    "datetime": llm_data["datetime"],
                    "analysis": "촬영 시간 정보가 포함된 사진입니다.",
                    "confidence": 0.8
                }
                llm_analysis_results["time"] = time_analysis
            except Exception as e:
                logger.warning(f"LLM 시간 분석 실패: {str(e)}")
        
        # 4. 라벨링 데이터 준비
        labeling_data = await exif_service.prepare_exif_for_labeling(processed_exif_data)
        
        # 5. 결과 반환 (데이터베이스 저장하지 않음)
        result = {
            "exif_processing": {
                "success": True,
                "data": processed_exif_data
            },
            "llm_analysis": {
                "success": len(llm_analysis_results) > 0,
                "results": llm_analysis_results
            },
            "labeling": {
                "success": True,
                "labels": labeling_data
            },
            "file_key": request.file_key,  # S3 파일 키 포함
            "user_id": current_user['sub']
        }
        
        logger.info(f"EXIF 데이터 LLM 처리 완료 - user: {current_user['sub']}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"EXIF 데이터 LLM 처리 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="EXIF 데이터 LLM 처리에 실패했습니다.")

@router.post("/enhance-location", response_model=LocationInfo)
async def enhance_location_info(
    location_info: LocationInfo,
    current_user = Depends(get_current_user)
):
    """
    위치 정보 보정 및 강화
    """
    try:
        enhanced_location = location_info
        
        # 좌표가 있는 경우 역지오코딩으로 주소 정보 보완
        if location_info.coordinates:
            geocoded_info = await geocoder_service.reverse_geocode(
                location_info.coordinates.latitude,
                location_info.coordinates.longitude
            )
            
            if geocoded_info:
                enhanced_location.country = enhanced_location.country or geocoded_info.get("country")
                enhanced_location.city = enhanced_location.city or geocoded_info.get("city")
                enhanced_location.region = enhanced_location.region or geocoded_info.get("region")
                enhanced_location.address = enhanced_location.address or geocoded_info.get("address")
        
        # LLM을 통한 장소명 추출 및 보정
        if location_info.coordinates:
            llm_location_info = await llm_location_service.search_location(
                latitude=location_info.coordinates.latitude,
                longitude=location_info.coordinates.longitude
            )
            
            if llm_location_info:
                enhanced_location.landmark = enhanced_location.landmark or llm_location_info.get("landmark")
                enhanced_location.confidence = llm_location_info.get("confidence", 0.8)
        
        return enhanced_location
    except Exception as e:
        logger.error(f"위치 정보 보정 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="위치 정보 보정에 실패했습니다.")

@router.post("/move-to-permanent")
async def move_to_permanent(
    request: MoveFileRequest,
    current_user = Depends(get_current_user)
):
    """
    임시 파일을 영구 저장소로 이동
    """
    try:
        success = await s3_service.move_temp_to_permanent(
            temp_key=request.temp_key,
            permanent_key=request.permanent_key
        )
        
        if success:
            return {"message": "파일이 성공적으로 이동되었습니다."}
        else:
            raise HTTPException(status_code=500, detail="파일 이동에 실패했습니다.")
    except Exception as e:
        logger.error(f"파일 이동 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="파일 이동에 실패했습니다.")

@router.delete("/temp-files")
async def cleanup_temp_files(
    file_keys: List[str],
    current_user = Depends(get_current_user)
):
    """
    임시 파일들 삭제
    """
    try:
        deleted_count = 0
        for file_key in file_keys:
            if file_key.startswith(f"temp/{current_user['sub']}/"):
                if await s3_service.delete_file(file_key):
                    deleted_count += 1
        
        return {"message": f"{deleted_count}개의 임시 파일이 삭제되었습니다."}
    except Exception as e:
        logger.error(f"임시 파일 삭제 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="임시 파일 삭제에 실패했습니다.")

@router.get("/preview/{file_key}", response_model=PhotoPreviewResponse)
async def get_photo_preview(
    file_key: str,
    current_user = Depends(get_current_user)
):
    """
    사진 미리보기 정보 조회
    """
    try:
        # 파일 정보 조회
        file_info = await s3_service.get_file_info(file_key)
        
        # EXIF 정보는 프론트엔드에서 처리하므로 기본값 반환
        exif_data = None
        
        return PhotoPreviewResponse(
            file_key=file_key,
            file_info=file_info,
            exif_data=exif_data
        )
    except Exception as e:
        logger.error(f"사진 미리보기 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="사진 미리보기 조회에 실패했습니다.")

@router.post("/batch-process", response_model=List[PhotoData])
async def batch_process_photos(
    photo_data_list: List[PhotoData],
    current_user = Depends(get_current_user)
):
    """
    여러 사진을 일괄 처리하여 위치 정보 보정
    """
    try:
        processed_photos = []
        
        for photo_data in photo_data_list:
            # 위치 정보가 있는 경우 보정
            if photo_data.location_info and photo_data.location_info.coordinates:
                enhanced_location = await geocoder_service.reverse_geocode(
                    photo_data.location_info.coordinates.latitude,
                    photo_data.location_info.coordinates.longitude
                )
                
                if enhanced_location:
                    photo_data.location_info.country = photo_data.location_info.country or enhanced_location.get("country")
                    photo_data.location_info.city = photo_data.location_info.city or enhanced_location.get("city")
                    photo_data.location_info.region = photo_data.location_info.region or enhanced_location.get("region")
                    photo_data.location_info.address = photo_data.location_info.address or enhanced_location.get("address")
            
            processed_photos.append(photo_data)
        
        return processed_photos
    except Exception as e:
        logger.error(f"배치 사진 처리 실패: {str(e)}")
        raise HTTPException(status_code=500, detail="사진 일괄 처리에 실패했습니다.") 

@router.get("/health")
async def health_check():
    """
    S3 연결 상태 확인
    """
    try:
        logger.info("S3 헬스체크 요청")
        
        # 환경 변수 확인
        env_check = {
            "AWS_ACCESS_KEY_ID": bool(os.getenv('AWS_ACCESS_KEY_ID')),
            "AWS_SECRET_ACCESS_KEY": bool(os.getenv('AWS_SECRET_ACCESS_KEY')),
            "AWS_REGION": os.getenv('AWS_REGION', 'ap-northeast-2'),
            "S3_BUCKET_NAME": os.getenv('S3_BUCKET_NAME')
        }
        
        # S3 버킷 접근 확인
        bucket_access = await s3_service.check_bucket_access()
        
        return {
            "status": "healthy" if bucket_access else "unhealthy",
            "environment": env_check,
            "bucket_access": bucket_access,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"S3 헬스체크 실패: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        } 