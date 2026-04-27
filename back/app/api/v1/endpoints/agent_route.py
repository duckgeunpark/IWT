"""
Agent 엔드포인트
- POST /agent/plan-route  : 여행 경로 계획 Agent (SSE 스트리밍)
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

from app.core.auth import get_current_user

router = APIRouter(prefix="/agent", tags=["agent"])


class PlanRouteRequest(BaseModel):
    destination: str
    styles: Optional[List[str]] = None
    duration: Optional[str] = ""
    companions: Optional[str] = ""


@router.post("/plan-route")
async def plan_route(
    req: PlanRouteRequest,
    current_user=Depends(get_current_user),
):
    """
    목적지 + 여행 스타일 → 경로 계획 Agent (SSE 스트리밍)

    프론트엔드 NewTripPage 계획 모드에서 호출.
    SSE 이벤트: {step, progress, message, itinerary?}
    """
    from app.services.agent_service import plan_route_stream

    async def event_generator():
        async for chunk in plan_route_stream(
            destination=req.destination,
            styles=req.styles or [],
            duration=req.duration or "",
            companions=req.companions or "",
        ):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
