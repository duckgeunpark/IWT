"""
응답 스키마 단위 테스트
"""

import pytest
from app.schemas.response import APIResponse, PaginatedResponse, ErrorResponse, ok, paginated


class TestAPIResponse:
    def test_success_response(self):
        resp = APIResponse(data={"id": 1, "name": "test"})
        assert resp.success is True
        assert resp.data == {"id": 1, "name": "test"}
        assert resp.timestamp is not None

    def test_with_message(self):
        resp = APIResponse(data=None, message="완료되었습니다.")
        assert resp.message == "완료되었습니다."


class TestPaginatedResponse:
    def test_has_next_true(self):
        resp = PaginatedResponse(data=[1, 2, 3], total=10, skip=0, limit=3)
        assert resp.has_next is True

    def test_has_next_false(self):
        resp = PaginatedResponse(data=[1, 2, 3], total=3, skip=0, limit=10)
        assert resp.has_next is False

    def test_last_page(self):
        resp = PaginatedResponse(data=[10], total=10, skip=9, limit=1)
        assert resp.has_next is False


class TestErrorResponse:
    def test_error_response(self):
        resp = ErrorResponse(error_code="NOT_FOUND", detail="리소스를 찾을 수 없습니다.")
        assert resp.success is False
        assert resp.error_code == "NOT_FOUND"
        assert resp.timestamp is not None


class TestHelperFunctions:
    def test_ok(self):
        result = ok(data={"id": 1}, message="성공")
        assert result["success"] is True
        assert result["data"] == {"id": 1}

    def test_paginated(self):
        result = paginated(items=[1, 2, 3], total=10, skip=0, limit=3)
        assert result["success"] is True
        assert result["total"] == 10
        assert result["has_next"] is True
        assert len(result["data"]) == 3
