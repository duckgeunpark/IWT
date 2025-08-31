from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

router = APIRouter()

class GPSData(BaseModel):
    """GPS 위치 정보"""
    lat: float = Field(..., description="위도")
    lng: float = Field(..., description="경도") 
    alt: Optional[float] = Field(None, description="고도 (미터)")
    accuracyM: Optional[float] = Field(None, description="GPS 정확도 (미터)")

class FlagsData(BaseModel):
    """메타데이터 플래그 정보"""
    isEstimatedGeo: bool = Field(False, description="GPS 위치가 추정값인지 여부")

class ImageMetadata(BaseModel):
    """이미지 메타데이터 스키마"""
    id: float = Field(..., description="고유 ID")
    fileHash: str = Field(..., description="파일 해시 (SHA-256)")
    originalFilename: str = Field(..., description="원본 파일명")
    fileSizeBytes: int = Field(..., description="파일 크기 (바이트)")
    mimeType: str = Field(..., description="MIME 타입")
    
    # 이미지 정보
    imageWidth: Optional[int] = Field(None, description="이미지 너비")
    imageHeight: Optional[int] = Field(None, description="이미지 높이") 
    orientation: Optional[int] = Field(None, description="이미지 방향")
    colorSpace: Optional[str] = Field(None, description="색상 공간")
    
    # 시간 정보
    takenAtLocal: Optional[str] = Field(None, description="촬영 시간 (로컬)")
    offsetMinutes: Optional[int] = Field(None, description="시간대 오프셋 (분)")
    takenAtUTC: Optional[str] = Field(None, description="촬영 시간 (UTC)")
    
    # GPS 정보
    gps: Optional[GPSData] = Field(None, description="GPS 위치 정보")
    
    # 플래그 정보
    flags: FlagsData = Field(..., description="메타데이터 플래그")

class ImageMetadataResponse(BaseModel):
    """이미지 메타데이터 응답"""
    status: str = Field(..., description="처리 상태")
    message: str = Field(..., description="응답 메시지")
    data: Dict[str, Any] = Field(..., description="처리된 데이터")
    receivedAt: str = Field(..., description="수신 시간")

@router.post(
    "/metadata",
    response_model=ImageMetadataResponse,
    status_code=status.HTTP_200_OK,
    summary="이미지 메타데이터 수신",
    description="프론트엔드에서 전송된 이미지 메타데이터를 처리합니다."
)
async def receive_image_metadata(metadata: ImageMetadata) -> ImageMetadataResponse:
    """
    이미지 메타데이터 수신 및 처리
    
    Args:
        metadata: 이미지 메타데이터 정보
        
    Returns:
        ImageMetadataResponse: 처리 결과
    """
    try:
        # 디버깅: 수신된 원본 데이터 출력
        print("🔍 수신된 메타데이터 디버깅:")
        print(f"  orientation type: {type(metadata.orientation)}, value: {metadata.orientation}")
        print(f"  colorSpace type: {type(metadata.colorSpace)}, value: {metadata.colorSpace}")
        print(f"  imageWidth type: {type(metadata.imageWidth)}, value: {metadata.imageWidth}")
        print(f"  imageHeight type: {type(metadata.imageHeight)}, value: {metadata.imageHeight}")
        
        # 현재는 단순히 데이터를 로깅하고 응답
        # 실제 구현에서는 데이터베이스 저장, 이미지 처리 등을 수행
        
        # 메타데이터 처리 로직
        processed_data = {
            "id": metadata.id,
            "fileHash": metadata.fileHash,
            "filename": metadata.originalFilename,
            "size": metadata.fileSizeBytes,
            "mimeType": metadata.mimeType,
            "dimensions": {
                "width": metadata.imageWidth,
                "height": metadata.imageHeight,
                "orientation": metadata.orientation
            },
            "capturedAt": {
                "local": metadata.takenAtLocal,
                "utc": metadata.takenAtUTC,
                "timezone_offset": metadata.offsetMinutes
            },
            "location": {
                "coordinates": [metadata.gps.lng, metadata.gps.lat] if metadata.gps else None,
                "altitude": metadata.gps.alt if metadata.gps else None,
                "accuracy": metadata.gps.accuracyM if metadata.gps else None,
                "estimated": metadata.flags.isEstimatedGeo
            } if metadata.gps else None
        }
        
        # 콘솔에 상세 정보 출력
        print("📷 이미지 메타데이터 수신:")
        print(f"  파일명: {metadata.originalFilename}")
        print(f"  크기: {metadata.fileSizeBytes / 1024 / 1024:.2f} MB")
        print(f"  해시: {metadata.fileHash[:16]}...")
        print(f"  해상도: {metadata.imageWidth}x{metadata.imageHeight}")
        
        if metadata.takenAtLocal:
            print(f"  촬영시간: {metadata.takenAtLocal}")
            
        if metadata.gps:
            print(f"  위치: {metadata.gps.lat:.6f}, {metadata.gps.lng:.6f}")
            if metadata.gps.alt:
                print(f"  고도: {metadata.gps.alt}m")
        
        return ImageMetadataResponse(
            status="success",
            message="이미지 메타데이터가 성공적으로 처리되었습니다.",
            data=processed_data,
            receivedAt=datetime.now().isoformat()
        )
        
    except Exception as e:
        print(f"❌ 메타데이터 처리 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"메타데이터 처리 중 오류가 발생했습니다: {str(e)}"
        )

@router.put(
    "/metadata/{image_id}",
    response_model=ImageMetadataResponse,
    status_code=status.HTTP_200_OK,
    summary="이미지 메타데이터 업데이트",
    description="기존 이미지의 메타데이터를 업데이트합니다."
)
async def update_image_metadata(image_id: str, metadata: ImageMetadata) -> ImageMetadataResponse:
    """
    이미지 메타데이터 업데이트
    
    Args:
        image_id: 이미지 고유 ID
        metadata: 업데이트할 이미지 메타데이터 정보
        
    Returns:
        ImageMetadataResponse: 업데이트 결과
    """
    try:
        # 디버깅: 업데이트 요청 정보 출력
        print(f"🔄 메타데이터 업데이트 요청 - ID: {image_id}")
        print("🔍 업데이트할 메타데이터:")
        print(f"  파일명: {metadata.originalFilename}")
        print(f"  해상도: {metadata.imageWidth}x{metadata.imageHeight}")
        print(f"  방향: {metadata.orientation}")
        print(f"  색상공간: {metadata.colorSpace}")
        
        if metadata.takenAtLocal:
            print(f"  촬영시간: {metadata.takenAtLocal}")
            print(f"  시간대 오프셋: {metadata.offsetMinutes}분")
            
        if metadata.gps:
            print(f"  GPS 위치: {metadata.gps.lat:.6f}, {metadata.gps.lng:.6f}")
            if metadata.gps.alt:
                print(f"  고도: {metadata.gps.alt}m")
            if metadata.gps.accuracyM:
                print(f"  GPS 정확도: {metadata.gps.accuracyM}m")
        else:
            print("  GPS 정보: 없음")
        
        # 실제 구현에서는 데이터베이스에서 해당 ID의 레코드를 찾아 업데이트
        # 현재는 업데이트 시뮬레이션만 수행
        
        # 업데이트된 데이터 처리
        updated_data = {
            "id": image_id,
            "updated_id": metadata.id,
            "fileHash": metadata.fileHash,
            "filename": metadata.originalFilename,
            "size": metadata.fileSizeBytes,
            "mimeType": metadata.mimeType,
            "dimensions": {
                "width": metadata.imageWidth,
                "height": metadata.imageHeight,
                "orientation": metadata.orientation
            },
            "colorSpace": metadata.colorSpace,
            "capturedAt": {
                "local": metadata.takenAtLocal,
                "utc": metadata.takenAtUTC,
                "timezone_offset": metadata.offsetMinutes
            },
            "location": {
                "coordinates": [metadata.gps.lng, metadata.gps.lat] if metadata.gps else None,
                "altitude": metadata.gps.alt if metadata.gps else None,
                "accuracy": metadata.gps.accuracyM if metadata.gps else None,
                "estimated": metadata.flags.isEstimatedGeo
            } if metadata.gps else None,
            "updatedAt": datetime.now().isoformat()
        }
        
        print("✅ 메타데이터 업데이트 완료")
        
        return ImageMetadataResponse(
            status="success",
            message=f"이미지 메타데이터(ID: {image_id})가 성공적으로 업데이트되었습니다.",
            data=updated_data,
            receivedAt=datetime.now().isoformat()
        )
        
    except Exception as e:
        print(f"❌ 메타데이터 업데이트 오류: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"메타데이터 업데이트 중 오류가 발생했습니다: {str(e)}"
        )

@router.get(
    "/metadata/health",
    summary="메타데이터 엔드포인트 헬스 체크",
    description="메타데이터 API 엔드포인트의 상태를 확인합니다."
)
async def health_check():
    """메타데이터 API 헬스 체크"""
    return {
        "status": "healthy",
        "endpoint": "image_metadata",
        "timestamp": datetime.now().isoformat(),
        "message": "이미지 메타데이터 API가 정상 작동 중입니다."
    }