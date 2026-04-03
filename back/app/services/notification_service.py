"""알림 서비스"""

import logging
from sqlalchemy.orm import Session
from app.models.db_models import Notification, User

logger = logging.getLogger(__name__)


class NotificationService:

    @staticmethod
    def create_notification(
        db: Session,
        user_id: str,
        type: str,
        message: str,
        actor_id: str = None,
        post_id: int = None,
        comment_id: int = None,
    ) -> Notification:
        """알림 생성 (자기 자신에게는 알림 안 보냄)"""
        if actor_id and actor_id == user_id:
            return None

        notification = Notification(
            user_id=user_id,
            type=type,
            message=message,
            actor_id=actor_id,
            post_id=post_id,
            comment_id=comment_id,
        )
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def get_notifications(db: Session, user_id: str, limit: int = 50, offset: int = 0):
        """사용자 알림 목록 조회"""
        return (
            db.query(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_unread_count(db: Session, user_id: str) -> int:
        """읽지 않은 알림 수"""
        return (
            db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.is_read == False)
            .count()
        )

    @staticmethod
    def mark_as_read(db: Session, user_id: str, notification_id: int) -> bool:
        """알림 읽음 처리"""
        notif = (
            db.query(Notification)
            .filter(Notification.id == notification_id, Notification.user_id == user_id)
            .first()
        )
        if notif:
            notif.is_read = True
            db.commit()
            return True
        return False

    @staticmethod
    def mark_all_as_read(db: Session, user_id: str) -> int:
        """모든 알림 읽음 처리"""
        count = (
            db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.is_read == False)
            .update({"is_read": True})
        )
        db.commit()
        return count

    @staticmethod
    def delete_notification(db: Session, user_id: str, notification_id: int) -> bool:
        """알림 삭제"""
        notif = (
            db.query(Notification)
            .filter(Notification.id == notification_id, Notification.user_id == user_id)
            .first()
        )
        if notif:
            db.delete(notif)
            db.commit()
            return True
        return False


notification_service = NotificationService()
