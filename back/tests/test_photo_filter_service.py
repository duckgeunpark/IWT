"""사진 필터링 파이프라인 유닛 테스트"""
import pytest
from app.services.photo_filter_service import PhotoFilterService


class TestPhotoFilterService:
    """PhotoFilterService 유닛 테스트"""

    def setup_method(self):
        self.service = PhotoFilterService()

    def test_empty_input(self):
        result = self.service.process_pipeline([], enable_ai_quality=False)
        assert result["summary"]["total_photos"] == 0
        assert result["summary"]["usable_photos"] == 0

    def test_duplicate_detection(self):
        photos = [
            {"id": "1", "file_name": "a.jpg", "file_size": 1000, "file_hash": "abc123", "gps": {"lat": 37.5, "lng": 127.0}, "taken_at": "2025-01-01T10:00:00"},
            {"id": "2", "file_name": "b.jpg", "file_size": 1000, "file_hash": "abc123", "gps": {"lat": 37.5, "lng": 127.0}, "taken_at": "2025-01-01T10:00:00"},
            {"id": "3", "file_name": "c.jpg", "file_size": 2000, "file_hash": "def456", "gps": {"lat": 37.6, "lng": 127.1}, "taken_at": "2025-01-01T12:00:00"},
        ]
        result = self.service.process_pipeline(photos, enable_ai_quality=False)
        assert result["summary"]["duplicates_removed"] == 1

    def test_no_gps_detection(self):
        photos = [
            {"id": "1", "file_name": "a.jpg", "file_size": 1000, "file_hash": "aaa", "gps": None, "taken_at": "2025-01-01T10:00:00"},
            {"id": "2", "file_name": "b.jpg", "file_size": 2000, "file_hash": "bbb", "gps": {"lat": 37.5, "lng": 127.0}, "taken_at": "2025-01-01T11:00:00"},
        ]
        result = self.service.process_pipeline(photos, enable_ai_quality=False)
        assert result["summary"]["no_gps_count"] == 1

    def test_place_grouping(self):
        # 같은 장소 (50m 이내) 사진 2장
        photos = [
            {"id": "1", "file_name": "a.jpg", "file_size": 1000, "file_hash": "aaa", "gps": {"lat": 37.50000, "lng": 127.00000}, "taken_at": "2025-01-01T10:00:00"},
            {"id": "2", "file_name": "b.jpg", "file_size": 2000, "file_hash": "bbb", "gps": {"lat": 37.50001, "lng": 127.00001}, "taken_at": "2025-01-01T10:05:00"},
            {"id": "3", "file_name": "c.jpg", "file_size": 3000, "file_hash": "ccc", "gps": {"lat": 38.00000, "lng": 128.00000}, "taken_at": "2025-01-01T14:00:00"},
        ]
        result = self.service.process_pipeline(photos, enable_ai_quality=False)
        assert result["summary"]["place_groups"] >= 2

    def test_single_photo(self):
        photos = [
            {"id": "1", "file_name": "a.jpg", "file_size": 1000, "file_hash": "aaa", "gps": {"lat": 37.5, "lng": 127.0}, "taken_at": "2025-01-01T10:00:00"},
        ]
        result = self.service.process_pipeline(photos, enable_ai_quality=False)
        assert result["summary"]["total_photos"] == 1
        assert result["summary"]["usable_photos"] == 1
