"""알림 API 테스트"""
import pytest


class TestNotificationAPI:
    """알림 API 테스트"""

    def _create_notification(self, db_session, user_id, msg="테스트 알림"):
        from app.models.db_models import Notification

        n = Notification(
            user_id=user_id,
            type="like",
            message=msg,
        )
        db_session.add(n)
        db_session.commit()
        db_session.refresh(n)
        return n

    def test_get_notifications_empty(self, client, sample_user):
        res = client.get("/api/v1/notifications")
        assert res.status_code == 200
        data = res.json()
        assert data["notifications"] == []

    def test_get_notifications(self, client, sample_user, db_session):
        self._create_notification(db_session, sample_user.id, "알림1")
        self._create_notification(db_session, sample_user.id, "알림2")

        res = client.get("/api/v1/notifications")
        assert res.status_code == 200
        data = res.json()
        assert len(data["notifications"]) == 2

    def test_unread_count(self, client, sample_user, db_session):
        self._create_notification(db_session, sample_user.id)

        res = client.get("/api/v1/notifications/unread-count")
        assert res.status_code == 200
        assert res.json()["unread_count"] == 1

    def test_mark_as_read(self, client, sample_user, db_session):
        n = self._create_notification(db_session, sample_user.id)

        res = client.put(f"/api/v1/notifications/{n.id}/read")
        assert res.status_code == 200

        # 읽지 않은 수 확인
        res = client.get("/api/v1/notifications/unread-count")
        assert res.json()["unread_count"] == 0

    def test_mark_all_read(self, client, sample_user, db_session):
        self._create_notification(db_session, sample_user.id, "알림1")
        self._create_notification(db_session, sample_user.id, "알림2")

        res = client.put("/api/v1/notifications/read-all")
        assert res.status_code == 200

        res = client.get("/api/v1/notifications/unread-count")
        assert res.json()["unread_count"] == 0

    def test_delete_notification(self, client, sample_user, db_session):
        n = self._create_notification(db_session, sample_user.id)

        res = client.delete(f"/api/v1/notifications/{n.id}")
        assert res.status_code == 200

        res = client.get("/api/v1/notifications")
        assert len(res.json()["notifications"]) == 0
