from fastapi import APIRouter, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging

from app.core.auth import get_current_user
from app.services.photo_filter_service import PhotoFilterService

router = APIRouter(prefix="/photos", tags=["사진 필터링"])
logger = logging.getLogger(__name__)

filter_service = PhotoFilterService()


class PhotoFilterItem(BaseModel):
    id: str
    file_name: str
    file_size: int
    file_hash: Optional[str] = None
    gps: Optional[Dict[str, float]] = None
    taken_at: Optional[str] = None
    content_type: str = "image/jpeg"


class PhotoFilterRequest(BaseModel):
    photos: List[PhotoFilterItem]
    enable_ai_quality: bool = False


@router.post("/filter")
async def filter_photos(
    request: PhotoFilterRequest,
    current_user=Depends(get_current_user),
):
    """
    사진 필터링 파이프라인 실행

    7단계 파이프라인:
    1. 중복 제거 (파일 해시)
    2. 연사/버스트 그룹화
    3. GPS 없는 사진 분리
    4. 같은 장소 그룹화
    5. AI 품질 분석 (선택)
    6. 쓰레기 데이터 구분
    7. 데이터 활용 내역 표기
    """
    photos_data = [p.model_dump() for p in request.photos]
    result = filter_service.run_pipeline(photos_data, request.enable_ai_quality)

    return {
        "summary": {
            "total_input": result.total_input,
            "duplicates_removed": result.duplicates_removed,
            "burst_groups": result.burst_groups,
            "burst_selected": result.burst_selected,
            "no_gps_count": result.no_gps_count,
            "place_groups": result.place_groups,
            "trash_removed": result.trash_removed,
            "usable_photos": result.usable_photos,
        },
        "photos": result.photos,
        "place_groups": result.place_group_details,
    }
