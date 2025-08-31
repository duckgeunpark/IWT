"""
Custom Exceptions - 커스텀 예외 정의
"""

from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class BaseAPIException(HTTPException):
    """API 기본 예외 클래스"""
    
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code


class ValidationError(BaseAPIException):
    """유효성 검사 실패"""
    
    def __init__(self, detail: str = "유효성 검사에 실패했습니다.", field: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code="VALIDATION_ERROR"
        )
        self.field = field


class AuthenticationError(BaseAPIException):
    """인증 실패"""
    
    def __init__(self, detail: str = "인증에 실패했습니다."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="AUTHENTICATION_ERROR",
            headers={"WWW-Authenticate": "Bearer"}
        )


class AuthorizationError(BaseAPIException):
    """권한 부족"""
    
    def __init__(self, detail: str = "접근 권한이 없습니다."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="AUTHORIZATION_ERROR"
        )


class NotFoundError(BaseAPIException):
    """리소스 찾을 수 없음"""
    
    def __init__(self, detail: str = "요청한 리소스를 찾을 수 없습니다.", resource: Optional[str] = None):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            error_code="NOT_FOUND_ERROR"
        )
        self.resource = resource


class ConflictError(BaseAPIException):
    """리소스 충돌"""
    
    def __init__(self, detail: str = "리소스 충돌이 발생했습니다."):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            error_code="CONFLICT_ERROR"
        )


class FileError(BaseAPIException):
    """파일 처리 오류"""
    
    def __init__(self, detail: str = "파일 처리 중 오류가 발생했습니다."):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code="FILE_ERROR"
        )


class FileTooLargeError(FileError):
    """파일 크기 초과"""
    
    def __init__(self, max_size: int):
        super().__init__(f"파일 크기가 최대 허용 크기({max_size}MB)를 초과했습니다.")
        self.error_code = "FILE_TOO_LARGE"


class InvalidFileTypeError(FileError):
    """지원하지 않는 파일 형식"""
    
    def __init__(self, file_type: str, allowed_types: list):
        super().__init__(
            f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(allowed_types)}"
        )
        self.error_code = "INVALID_FILE_TYPE"
        self.file_type = file_type
        self.allowed_types = allowed_types


class DatabaseError(BaseAPIException):
    """데이터베이스 오류"""
    
    def __init__(self, detail: str = "데이터베이스 처리 중 오류가 발생했습니다."):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            error_code="DATABASE_ERROR"
        )


class ExternalServiceError(BaseAPIException):
    """외부 서비스 오류"""
    
    def __init__(self, service_name: str, detail: str = None):
        detail = detail or f"{service_name} 서비스 연결에 실패했습니다."
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            error_code="EXTERNAL_SERVICE_ERROR"
        )
        self.service_name = service_name


class LLMServiceError(ExternalServiceError):
    """LLM 서비스 오류"""
    
    def __init__(self, detail: str = "LLM 서비스 처리 중 오류가 발생했습니다."):
        super().__init__("LLM", detail)
        self.error_code = "LLM_SERVICE_ERROR"


class S3ServiceError(ExternalServiceError):
    """S3 서비스 오류"""
    
    def __init__(self, detail: str = "S3 서비스 처리 중 오류가 발생했습니다."):
        super().__init__("S3", detail)
        self.error_code = "S3_SERVICE_ERROR"


class Auth0ServiceError(ExternalServiceError):
    """Auth0 서비스 오류"""
    
    def __init__(self, detail: str = "Auth0 서비스 처리 중 오류가 발생했습니다."):
        super().__init__("Auth0", detail)
        self.error_code = "AUTH0_SERVICE_ERROR"


class RateLimitError(BaseAPIException):
    """요청 제한 초과"""
    
    def __init__(self, detail: str = "요청 제한을 초과했습니다. 잠시 후 다시 시도해주세요."):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            error_code="RATE_LIMIT_ERROR"
        )


# 예외 매핑 딕셔너리
EXCEPTION_HANDLERS = {
    ValidationError: {
        "description": "요청 데이터 유효성 검사 실패",
        "example": {"detail": "유효성 검사에 실패했습니다.", "error_code": "VALIDATION_ERROR"}
    },
    AuthenticationError: {
        "description": "인증 실패",
        "example": {"detail": "인증에 실패했습니다.", "error_code": "AUTHENTICATION_ERROR"}
    },
    AuthorizationError: {
        "description": "권한 부족",
        "example": {"detail": "접근 권한이 없습니다.", "error_code": "AUTHORIZATION_ERROR"}
    },
    NotFoundError: {
        "description": "리소스를 찾을 수 없음",
        "example": {"detail": "요청한 리소스를 찾을 수 없습니다.", "error_code": "NOT_FOUND_ERROR"}
    },
    DatabaseError: {
        "description": "데이터베이스 처리 오류",
        "example": {"detail": "데이터베이스 처리 중 오류가 발생했습니다.", "error_code": "DATABASE_ERROR"}
    },
    ExternalServiceError: {
        "description": "외부 서비스 연결 오류",
        "example": {"detail": "외부 서비스 연결에 실패했습니다.", "error_code": "EXTERNAL_SERVICE_ERROR"}
    }
}