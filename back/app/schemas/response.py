"""
표준 API 응답 스키마
모든 엔드포인트에서 일관된 응답 포맷을 사용한다.
"""

from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel
from datetime import datetime

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """표준 API 응답"""
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None
    timestamp: datetime = None

    def __init__(self, **kwargs):
        if "timestamp" not in kwargs or kwargs["timestamp"] is None:
            kwargs["timestamp"] = datetime.utcnow()
        super().__init__(**kwargs)


class PaginatedResponse(BaseModel, Generic[T]):
    """페이지네이션이 포함된 표준 응답"""
    success: bool = True
    data: List[T] = []
    total: int = 0
    skip: int = 0
    limit: int = 10
    has_next: bool = False
    message: Optional[str] = None
    timestamp: datetime = None

    def __init__(self, **kwargs):
        if "timestamp" not in kwargs or kwargs["timestamp"] is None:
            kwargs["timestamp"] = datetime.utcnow()
        # has_next 자동 계산
        if "has_next" not in kwargs:
            total = kwargs.get("total", 0)
            skip = kwargs.get("skip", 0)
            limit = kwargs.get("limit", 10)
            kwargs["has_next"] = (skip + limit) < total
        super().__init__(**kwargs)


class ErrorResponse(BaseModel):
    """표준 에러 응답"""
    success: bool = False
    error_code: str
    detail: str
    path: Optional[str] = None
    method: Optional[str] = None
    timestamp: datetime = None

    def __init__(self, **kwargs):
        if "timestamp" not in kwargs or kwargs["timestamp"] is None:
            kwargs["timestamp"] = datetime.utcnow()
        super().__init__(**kwargs)


def ok(data: Any = None, message: str = None) -> dict:
    """성공 응답을 생성한다."""
    return APIResponse(success=True, data=data, message=message).model_dump()


def paginated(items: list, total: int, skip: int = 0, limit: int = 10, message: str = None) -> dict:
    """페이지네이션 응답을 생성한다."""
    return PaginatedResponse(
        data=items,
        total=total,
        skip=skip,
        limit=limit,
        message=message,
    ).model_dump()
