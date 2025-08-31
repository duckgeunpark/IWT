"""
Application Configuration - 앱 설정 중앙 관리
"""

import os
from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings
import secrets


class Settings(BaseSettings):
    """애플리케이션 설정 클래스"""
    
    # 기본 설정
    app_name: str = "IWT API"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # 서버 설정
    host: str = "0.0.0.0"
    port: int = 8000
    
    # CORS 설정
    allowed_origins: List[str] = ["http://localhost:3000"]
    allowed_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allowed_headers: List[str] = ["*"]
    allow_credentials: bool = True
    
    # 데이터베이스 설정
    database_url: Optional[str] = None
    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "iwt_db"
    db_user: str = "root"
    db_password: str = ""
    
    # Auth0 설정
    auth0_domain: Optional[str] = None
    auth0_audience: Optional[str] = None
    auth0_algorithms: str = "RS256"
    
    # AWS S3 설정
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "ap-northeast-2"
    s3_bucket_name: Optional[str] = None
    s3_presigned_url_expire: int = 3600  # 1시간
    
    # LLM 설정
    groq_api_key: Optional[str] = None
    llm_model_name: str = "llama3-8b-8192"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 500
    
    # 파일 업로드 설정
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_image_types: List[str] = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    
    # 로깅 설정
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 보안 설정
    secret_key: str = secrets.token_urlsafe(32)
    access_token_expire_minutes: int = 30
    
    @field_validator("database_url", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str]) -> str:
        """데이터베이스 연결 URL 생성"""
        if isinstance(v, str):
            return v
        # For Pydantic v2, we need to access other fields differently
        # This validator will be updated to work with v2 patterns
        return v or "mysql+pymysql://root:@localhost:3306/iwt_db"
    
    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        """CORS origins 파싱"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @property
    def auth0_algorithms_list(self) -> List[str]:
        """Auth0 algorithms를 리스트로 반환"""
        if isinstance(self.auth0_algorithms, str):
            return [algo.strip() for algo in self.auth0_algorithms.split(",")]
        return [self.auth0_algorithms]
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore"
    }


# 설정 인스턴스 생성
settings = Settings()


class APIConstants:
    """API 상수 정의"""
    
    # API 버전
    API_V1_PREFIX = "/api/v1"
    
    # 응답 메시지
    class Messages:
        SUCCESS = "요청이 성공적으로 처리되었습니다."
        CREATED = "리소스가 성공적으로 생성되었습니다."
        UPDATED = "리소스가 성공적으로 업데이트되었습니다."
        DELETED = "리소스가 성공적으로 삭제되었습니다."
        NOT_FOUND = "요청한 리소스를 찾을 수 없습니다."
        UNAUTHORIZED = "인증이 필요합니다."
        FORBIDDEN = "접근 권한이 없습니다."
        BAD_REQUEST = "잘못된 요청입니다."
        INTERNAL_ERROR = "서버 내부 오류가 발생했습니다."
        FILE_TOO_LARGE = "파일 크기가 너무 큽니다."
        INVALID_FILE_TYPE = "지원하지 않는 파일 형식입니다."
    
    # HTTP 상태 코드
    class StatusCodes:
        OK = 200
        CREATED = 201
        NO_CONTENT = 204
        BAD_REQUEST = 400
        UNAUTHORIZED = 401
        FORBIDDEN = 403
        NOT_FOUND = 404
        UNPROCESSABLE_ENTITY = 422
        INTERNAL_SERVER_ERROR = 500
    
    # 데이터베이스 상수
    class Database:
        MAX_STRING_LENGTH = 255
        MAX_TEXT_LENGTH = 65535
        MAX_BATCH_SIZE = 1000
    
    # 파일 처리 상수
    class Files:
        MAX_SIZE = settings.max_file_size
        ALLOWED_TYPES = settings.allowed_image_types
        CHUNK_SIZE = 8192
    
    # LLM 상수
    class LLM:
        DEFAULT_TEMPERATURE = settings.llm_temperature
        DEFAULT_MAX_TOKENS = settings.llm_max_tokens
        ANALYSIS_TYPES = ["location", "scene", "object", "sentiment"]
        LABEL_TYPES = ["location", "time", "camera", "image", "llm_generated"]
        SOURCES = ["exif", "llm", "manual"]


class DatabaseConfig:
    """데이터베이스 설정"""
    
    @staticmethod
    def get_engine_args():
        """SQLAlchemy 엔진 설정 반환"""
        return {
            "pool_size": 20,
            "max_overflow": 0,
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "echo": settings.debug,
        }
    
    @staticmethod
    def get_session_args():
        """SQLAlchemy 세션 설정 반환"""
        return {
            "autocommit": False,
            "autoflush": False,
        }