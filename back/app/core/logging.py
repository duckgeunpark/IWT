"""
Logging Configuration - 로깅 설정
"""

import logging
import logging.config
import sys
from pathlib import Path
from typing import Dict, Any
from app.core.config import settings


def get_logging_config() -> Dict[str, Any]:
    """로깅 설정 딕셔너리 반환"""
    
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": settings.log_format,
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed": {
                "format": "[{asctime}] {levelname:<8} | {name:<20} | {funcName:<15} | {lineno:<4} | {message}",
                "style": "{",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json": {
                "format": "%(asctime)s %(name)s %(levelname)s %(funcName)s %(lineno)d %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": settings.log_level,
                "formatter": "detailed",
                "stream": sys.stdout,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": settings.log_level,
                "formatter": "detailed",
                "filename": "logs/app.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "detailed",
                "filename": "logs/error.log",
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
            },
        },
        "loggers": {
            "app": {
                "level": settings.log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "app.services": {
                "level": settings.log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "app.repositories": {
                "level": settings.log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "app.api": {
                "level": settings.log_level,
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": "INFO",
                "handlers": ["console", "error_file"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": "INFO",
                "handlers": ["console"],
                "propagate": False,
            },
            "sqlalchemy.engine": {
                "level": "WARNING",
                "handlers": ["console"],
                "propagate": False,
            },
        },
        "root": {
            "level": settings.log_level,
            "handlers": ["console", "error_file"],
        },
    }


def setup_logging():
    """로깅 설정 초기화"""
    
    # 로그 디렉토리 생성
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # 로깅 설정 적용
    config = get_logging_config()
    logging.config.dictConfig(config)
    
    # 애플리케이션 로거 생성
    logger = logging.getLogger("app")
    logger.info("로깅 시스템이 초기화되었습니다.")
    
    return logger


class LoggerMixin:
    """로거 믹스인 클래스"""
    
    @property
    def logger(self) -> logging.Logger:
        """클래스별 로거 반환"""
        name = f"app.{self.__class__.__module__}.{self.__class__.__name__}"
        return logging.getLogger(name)


def get_logger(name: str) -> logging.Logger:
    """지정된 이름의 로거 반환"""
    return logging.getLogger(f"app.{name}")


# 공통 로그 메시지 함수들
def log_api_request(logger: logging.Logger, method: str, path: str, user_id: str = None):
    """API 요청 로그"""
    user_info = f"user:{user_id}" if user_id else "anonymous"
    logger.info(f"API 요청 - {method} {path} ({user_info})")


def log_api_response(logger: logging.Logger, method: str, path: str, status_code: int, duration: float):
    """API 응답 로그"""
    logger.info(f"API 응답 - {method} {path} - {status_code} ({duration:.3f}s)")


def log_database_operation(logger: logging.Logger, operation: str, table: str, record_id: Any = None):
    """데이터베이스 작업 로그"""
    record_info = f"id:{record_id}" if record_id else ""
    logger.info(f"DB 작업 - {operation} {table} {record_info}")


def log_external_service_call(logger: logging.Logger, service: str, operation: str, success: bool):
    """외부 서비스 호출 로그"""
    status = "성공" if success else "실패"
    logger.info(f"외부 서비스 - {service} {operation} {status}")


def log_file_operation(logger: logging.Logger, operation: str, file_path: str, file_size: int = None):
    """파일 작업 로그"""
    size_info = f"({file_size} bytes)" if file_size else ""
    logger.info(f"파일 작업 - {operation} {file_path} {size_info}")


def log_user_action(logger: logging.Logger, user_id: str, action: str, resource: str = None):
    """사용자 액션 로그"""
    resource_info = f"on {resource}" if resource else ""
    logger.info(f"사용자 액션 - {user_id} {action} {resource_info}")


def log_error_with_context(logger: logging.Logger, error: Exception, context: Dict[str, Any] = None):
    """컨텍스트와 함께 오류 로그"""
    context_str = f" | Context: {context}" if context else ""
    logger.error(f"오류 발생: {type(error).__name__}: {str(error)}{context_str}", exc_info=True)


def log_performance_metric(logger: logging.Logger, operation: str, duration: float, additional_metrics: Dict[str, Any] = None):
    """성능 메트릭 로그"""
    metrics_str = ""
    if additional_metrics:
        metrics_str = " | " + " | ".join([f"{k}: {v}" for k, v in additional_metrics.items()])
    
    logger.info(f"성능 메트릭 - {operation}: {duration:.3f}s{metrics_str}")