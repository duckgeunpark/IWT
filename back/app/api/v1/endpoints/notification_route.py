from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging

from app.core.auth import get_current_user
from app.services.notification_service import notification_service
from app.db.session import get_db
from sqlalchemy.orm import Session

router = APIRouter(tags=["알림"])
logger = logging.getLogger(__name__)


class NotificationResponse(BaseModel):
    id: int
    type: str
    message: str
    actor_id: Optional[str] = None
    post_id: Optional[int] = None
    comment_id: Optional[int] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    notifications: List[NotificationResponse]
    unread_count: int


class UnreadCountResponse(BaseModel):
    unread_count: int


@router.get("/notifications", response_model=NotificationListResponse)
async def get_notifications(
    limit: int = 50,
    offset: int = 0,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """사용자 알림 목록 조회"""
    user_id = current_user["sub"]
    notifications = notification_service.get_notifications(db, user_id, limit, offset)
    unread_count = notification_service.get_unread_count(db, user_id)
    return NotificationListResponse(
        notifications=[NotificationResponse.model_validate(n) for n in notifications],
        unread_count=unread_count,
    )


@router.get("/notifications/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """읽지 않은 알림 수 조회"""
    user_id = current_user["sub"]
    count = notification_service.get_unread_count(db, user_id)
    return UnreadCountResponse(unread_count=count)


@router.put("/notifications/{notification_id}/read")
async def mark_as_read(
    notification_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """알림 읽음 처리"""
    user_id = current_user["sub"]
    success = notification_service.mark_as_read(db, user_id, notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
    return {"message": "읽음 처리 완료"}


@router.put("/notifications/read-all")
async def mark_all_as_read(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """모든 알림 읽음 처리"""
    user_id = current_user["sub"]
    count = notification_service.mark_all_as_read(db, user_id)
    return {"message": f"{count}개 알림 읽음 처리 완료", "count": count}


@router.delete("/notifications/{notification_id}")
async def delete_notification(
    notification_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """알림 삭제"""
    user_id = current_user["sub"]
    success = notification_service.delete_notification(db, user_id, notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
    return {"message": "알림 삭제 완료"}
