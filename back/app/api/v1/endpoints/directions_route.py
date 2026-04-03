from fastapi import APIRouter, Depends
from typing import List, Dict
from pydantic import BaseModel
import logging

from app.core.auth import get_current_user
from app.services.directions_service import directions_service

router = APIRouter(prefix="/routes", tags=["경로"])
logger = logging.getLogger(__name__)


class Waypoint(BaseModel):
    lat: float
    lng: float


class DirectionsRequest(BaseModel):
    waypoints: List[Waypoint]
    mode: str = "driving"  # driving, walking, bicycling, transit


@router.post("/directions")
async def get_directions(
    request: DirectionsRequest,
    current_user=Depends(get_current_user),
):
    """
    실제 도로 기반 경로 조회

    Google Directions API를 사용하여 경유지 간 실제 이동 경로,
    구간별 거리/시간, 폴리라인 데이터를 반환합니다.
    """
    waypoints = [{"lat": w.lat, "lng": w.lng} for w in request.waypoints]
    result = await directions_service.get_directions(waypoints, request.mode)
    return result
