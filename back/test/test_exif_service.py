"""
EXIF Extract Service 단위 테스트
"""

import pytest
import asyncio
from app.services.exif_extract_service import ExifExtractService


@pytest.fixture
def service():
    return ExifExtractService()


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class TestProcessExifData:
    def test_empty_data_returns_default(self, service):
        result = run(service.process_exif_data({}))
        assert result["extraction_success"] is False
        assert result["gps"] is None
        assert result["datetime"] is None

    def test_none_data_returns_default(self, service):
        result = run(service.process_exif_data(None))
        assert result["extraction_success"] is False

    def test_valid_gps_data(self, service):
        data = {
            "gps": {"latitude": 37.5665, "longitude": 126.9780},
            "extraction_success": True,
        }
        result = run(service.process_exif_data(data))
        assert result["gps"]["latitude"] == 37.5665
        assert result["gps"]["longitude"] == 126.9780

    def test_invalid_gps_latitude_excluded(self, service):
        data = {"gps": {"latitude": 999, "longitude": 126.9780}}
        result = run(service.process_exif_data(data))
        # 무효한 위도는 제외되고 경도만 남으므로 좌표 쌍이 불완전
        assert result["gps"] is None or "latitude" not in result["gps"]

    def test_valid_datetime_exif_format(self, service):
        data = {"datetime": "2024:03:15 14:30:45"}
        result = run(service.process_exif_data(data))
        assert result["datetime"] == "2024-03-15T14:30:45"

    def test_valid_camera_info(self, service):
        data = {
            "camera_info": {
                "make": "Canon",
                "model": "EOS R5",
                "lens": "RF 24-70mm",
            }
        }
        result = run(service.process_exif_data(data))
        assert result["camera_info"]["make"] == "Canon"
        assert result["camera_info"]["model"] == "EOS R5"


class TestValidateGpsData:
    def test_valid_coordinates(self, service):
        assert run(service.validate_gps_data({"latitude": 37.5, "longitude": 127.0})) is True

    def test_boundary_values(self, service):
        assert run(service.validate_gps_data({"latitude": 90, "longitude": 180})) is True
        assert run(service.validate_gps_data({"latitude": -90, "longitude": -180})) is True

    def test_invalid_latitude(self, service):
        assert run(service.validate_gps_data({"latitude": 91, "longitude": 127})) is False

    def test_invalid_longitude(self, service):
        assert run(service.validate_gps_data({"latitude": 37, "longitude": 181})) is False

    def test_none_data(self, service):
        assert run(service.validate_gps_data(None)) is False

    def test_missing_latitude(self, service):
        assert run(service.validate_gps_data({"longitude": 127})) is False


class TestPrepareExifForLlm:
    def test_with_full_data(self, service):
        data = {
            "gps": {"latitude": 37.5665, "longitude": 126.9780, "altitude": 50},
            "datetime": "2024-03-15T14:30:45",
            "camera_info": {"make": "Canon", "model": "EOS R5"},
            "image_info": {"width": 8192, "height": 5464},
        }
        result = run(service.prepare_exif_for_llm(data))
        assert result["location"]["coordinates_available"] is True
        assert result["datetime"] == "2024-03-15T14:30:45"
        assert result["camera_info"]["make"] == "Canon"

    def test_with_empty_data(self, service):
        result = run(service.prepare_exif_for_llm({}))
        assert result["location"] is None
        assert result["datetime"] is None


class TestPrepareExifForLabeling:
    def test_landscape_image(self, service):
        data = {"image_info": {"width": 1920, "height": 1080}}
        result = run(service.prepare_exif_for_labeling(data))
        assert "landscape" in result["image_labels"]

    def test_portrait_image(self, service):
        data = {"image_info": {"width": 1080, "height": 1920}}
        result = run(service.prepare_exif_for_labeling(data))
        assert "portrait" in result["image_labels"]

    def test_morning_label(self, service):
        data = {"datetime": "2024-03-15T08:30:00"}
        result = run(service.prepare_exif_for_labeling(data))
        assert "morning" in result["time_labels"]

    def test_evening_label(self, service):
        data = {"datetime": "2024-03-15T19:30:00"}
        result = run(service.prepare_exif_for_labeling(data))
        assert "evening" in result["time_labels"]

    def test_gps_labels(self, service):
        data = {"gps": {"latitude": 37.5, "longitude": 127.0, "altitude": 30}}
        result = run(service.prepare_exif_for_labeling(data))
        assert "has_gps_coordinates" in result["location_labels"]
        assert "has_altitude" in result["location_labels"]
