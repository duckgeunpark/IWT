"""
이미지 메타데이터 API 테스트
"""

import pytest
import json
from datetime import datetime
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# 테스트용 샘플 데이터
SAMPLE_METADATA_WITH_GPS = {
    "id": 1703123456.789,
    "fileHash": "a1b2c3d4e5f6789012345678901234567890abcdef123456789012345678901234",
    "originalFilename": "IMG_20231221_143045.jpg",
    "fileSizeBytes": 2458624,
    "mimeType": "image/jpeg",
    "imageWidth": 4032,
    "imageHeight": 3024,
    "orientation": 1,
    "colorSpace": "sRGB",
    "takenAtLocal": "2023-12-21T14:30:45.000Z",
    "offsetMinutes": 540,
    "takenAtUTC": "2023-12-21T05:30:45.000Z",
    "gps": {
        "lat": 37.566535,
        "lng": 126.977969,
        "alt": 12.5,
        "accuracyM": 3.0
    },
    "flags": {
        "isEstimatedGeo": False
    }
}

SAMPLE_METADATA_WITHOUT_GPS = {
    "id": 1703123456.123,
    "fileHash": "b2c3d4e5f6789012345678901234567890abcdef123456789012345678901234a",
    "originalFilename": "Screenshot_20231221_143045.png",
    "fileSizeBytes": 1024000,
    "mimeType": "image/png",
    "imageWidth": 1920,
    "imageHeight": 1080,
    "orientation": 1,
    "colorSpace": "sRGB",
    "takenAtLocal": None,
    "offsetMinutes": None,
    "takenAtUTC": None,
    "gps": None,
    "flags": {
        "isEstimatedGeo": False
    }
}

class TestImageMetadataAPI:
    """이미지 메타데이터 API 테스트 클래스"""
    
    def test_health_check(self):
        """헬스체크 엔드포인트 테스트"""
        response = client.get("/api/v1/images/metadata/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["endpoint"] == "image_metadata"
        assert "timestamp" in data
        
    def test_receive_metadata_with_gps_success(self):
        """GPS 정보가 있는 메타데이터 수신 테스트 (성공 케이스)"""
        response = client.post(
            "/api/v1/images/metadata", 
            json=SAMPLE_METADATA_WITH_GPS
        )
        
        # 응답 상태 확인
        assert response.status_code == 200
        
        # 응답 데이터 확인
        data = response.json()
        assert data["status"] == "success"
        assert "이미지 메타데이터가 성공적으로 처리되었습니다" in data["message"]
        assert "receivedAt" in data
        
        # 처리된 데이터 구조 확인
        processed_data = data["data"]
        assert processed_data["id"] == SAMPLE_METADATA_WITH_GPS["id"]
        assert processed_data["fileHash"] == SAMPLE_METADATA_WITH_GPS["fileHash"]
        assert processed_data["filename"] == SAMPLE_METADATA_WITH_GPS["originalFilename"]
        assert processed_data["size"] == SAMPLE_METADATA_WITH_GPS["fileSizeBytes"]
        
        # 이미지 정보 확인
        dimensions = processed_data["dimensions"]
        assert dimensions["width"] == SAMPLE_METADATA_WITH_GPS["imageWidth"]
        assert dimensions["height"] == SAMPLE_METADATA_WITH_GPS["imageHeight"]
        assert dimensions["orientation"] == SAMPLE_METADATA_WITH_GPS["orientation"]
        
        # 시간 정보 확인
        captured_at = processed_data["capturedAt"]
        assert captured_at["local"] == SAMPLE_METADATA_WITH_GPS["takenAtLocal"]
        assert captured_at["utc"] == SAMPLE_METADATA_WITH_GPS["takenAtUTC"]
        assert captured_at["timezone_offset"] == SAMPLE_METADATA_WITH_GPS["offsetMinutes"]
        
        # GPS 정보 확인
        location = processed_data["location"]
        assert location is not None
        assert location["coordinates"] == [
            SAMPLE_METADATA_WITH_GPS["gps"]["lng"],
            SAMPLE_METADATA_WITH_GPS["gps"]["lat"]
        ]
        assert location["altitude"] == SAMPLE_METADATA_WITH_GPS["gps"]["alt"]
        assert location["accuracy"] == SAMPLE_METADATA_WITH_GPS["gps"]["accuracyM"]
        assert location["estimated"] == SAMPLE_METADATA_WITH_GPS["flags"]["isEstimatedGeo"]
        
    def test_receive_metadata_without_gps_success(self):
        """GPS 정보가 없는 메타데이터 수신 테스트 (성공 케이스)"""
        response = client.post(
            "/api/v1/images/metadata",
            json=SAMPLE_METADATA_WITHOUT_GPS
        )
        
        # 응답 상태 확인
        assert response.status_code == 200
        
        # 응답 데이터 확인
        data = response.json()
        assert data["status"] == "success"
        
        # 처리된 데이터 확인
        processed_data = data["data"]
        assert processed_data["id"] == SAMPLE_METADATA_WITHOUT_GPS["id"]
        assert processed_data["filename"] == SAMPLE_METADATA_WITHOUT_GPS["originalFilename"]
        
        # GPS 정보가 없어야 함
        assert processed_data["location"] is None
        
        # 시간 정보가 없어야 함
        captured_at = processed_data["capturedAt"]
        assert captured_at["local"] is None
        assert captured_at["utc"] is None
        assert captured_at["timezone_offset"] is None
        
    def test_receive_metadata_validation_error(self):
        """필수 필드 누락 시 유효성 검사 오류 테스트"""
        invalid_metadata = {
            "id": 1703123456.789,
            # fileHash 누락
            "originalFilename": "test.jpg",
            "fileSizeBytes": 1024,
            "mimeType": "image/jpeg",
            "flags": {
                "isEstimatedGeo": False
            }
        }
        
        response = client.post(
            "/api/v1/images/metadata",
            json=invalid_metadata
        )
        
        # 유효성 검사 오류 확인
        assert response.status_code == 422
        data = response.json()
        assert data["error_code"] == "VALIDATION_ERROR"
        assert "요청 데이터의 유효성 검사에 실패했습니다" in data["detail"]
        
    def test_receive_metadata_invalid_data_types(self):
        """잘못된 데이터 타입 테스트"""
        invalid_metadata = {
            "id": "not_a_number",  # 숫자여야 함
            "fileHash": "valid_hash",
            "originalFilename": "test.jpg",
            "fileSizeBytes": "not_a_number",  # 숫자여야 함
            "mimeType": "image/jpeg",
            "flags": {
                "isEstimatedGeo": False
            }
        }
        
        response = client.post(
            "/api/v1/images/metadata",
            json=invalid_metadata
        )
        
        assert response.status_code == 422
        
    def test_receive_metadata_with_estimated_gps(self):
        """추정 GPS 정보가 있는 메타데이터 테스트"""
        estimated_metadata = SAMPLE_METADATA_WITH_GPS.copy()
        estimated_metadata["flags"]["isEstimatedGeo"] = True
        estimated_metadata["gps"]["accuracyM"] = None  # 추정이므로 정확도 없음
        
        response = client.post(
            "/api/v1/images/metadata",
            json=estimated_metadata
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # 추정 GPS 플래그 확인
        location = data["data"]["location"]
        assert location["estimated"] is True
        assert location["accuracy"] is None
        
    def test_receive_metadata_large_file(self):
        """대용량 파일 메타데이터 테스트"""
        large_file_metadata = SAMPLE_METADATA_WITH_GPS.copy()
        large_file_metadata["fileSizeBytes"] = 50 * 1024 * 1024  # 50MB
        large_file_metadata["imageWidth"] = 8192
        large_file_metadata["imageHeight"] = 6144
        
        response = client.post(
            "/api/v1/images/metadata",
            json=large_file_metadata
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # 대용량 파일 정보 처리 확인
        processed_data = data["data"]
        assert processed_data["size"] == 50 * 1024 * 1024
        assert processed_data["dimensions"]["width"] == 8192
        assert processed_data["dimensions"]["height"] == 6144

# 통합 테스트
class TestImageMetadataIntegration:
    """이미지 메타데이터 API 통합 테스트"""
    
    def test_multiple_metadata_processing(self):
        """여러 개의 메타데이터 순차 처리 테스트"""
        metadata_list = [
            SAMPLE_METADATA_WITH_GPS,
            SAMPLE_METADATA_WITHOUT_GPS,
        ]
        
        responses = []
        for metadata in metadata_list:
            response = client.post("/api/v1/images/metadata", json=metadata)
            responses.append(response)
        
        # 모든 요청이 성공적으로 처리되었는지 확인
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
    
    def test_edge_cases(self):
        """엣지 케이스 테스트"""
        edge_cases = [
            # 최소값
            {
                "id": 0.1,
                "fileHash": "a" * 64,
                "originalFilename": "a.jpg",
                "fileSizeBytes": 1,
                "mimeType": "image/jpeg",
                "imageWidth": 1,
                "imageHeight": 1,
                "flags": {"isEstimatedGeo": False}
            },
            # 매우 긴 파일명
            {
                "id": 999999999.999,
                "fileHash": "f" * 64,
                "originalFilename": "매우긴파일명" * 50 + ".jpg",
                "fileSizeBytes": 999999999,
                "mimeType": "image/jpeg",
                "flags": {"isEstimatedGeo": False}
            }
        ]
        
        for edge_case in edge_cases:
            response = client.post("/api/v1/images/metadata", json=edge_case)
            assert response.status_code == 200

if __name__ == "__main__":
    # 직접 실행 시 간단한 테스트 실행
    print("🧪 이미지 메타데이터 API 간단 테스트 시작...")
    
    # 헬스체크 테스트
    test = TestImageMetadataAPI()
    test.test_health_check()
    print("✅ 헬스체크 테스트 통과")
    
    # 메타데이터 수신 테스트
    test.test_receive_metadata_with_gps_success()
    print("✅ GPS 메타데이터 수신 테스트 통과")
    
    test.test_receive_metadata_without_gps_success()
    print("✅ 일반 메타데이터 수신 테스트 통과")
    
    print("🎉 모든 기본 테스트 통과!")