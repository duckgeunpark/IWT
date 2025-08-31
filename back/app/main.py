"""
Trip Photo API - 메인 애플리케이션
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import time
import logging

from app.api.v1.endpoints import user_auth0, photo_route, llm_route, post_route, image_metadata
from app.core.config import settings, APIConstants
from app.core.exceptions import BaseAPIException, EXCEPTION_HANDLERS
from app.core.logging import setup_logging, get_logger, log_api_request, log_api_response

# 로깅 설정 초기화
setup_logging()
logger = get_logger("main")

def create_application() -> FastAPI:
    """FastAPI 애플리케이션 생성 및 설정"""
    
    # FastAPI 앱 생성
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="여행 사진 관리 및 분석 API",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json" if settings.debug else None,
    )
    
    # 미들웨어 설정
    setup_middleware(app)
    
    # 예외 핸들러 설정
    setup_exception_handlers(app)
    
    # 라우터 등록
    setup_routers(app)
    
    # 이벤트 핸들러 설정
    setup_event_handlers(app)
    
    logger.info(f"{settings.app_name} v{settings.app_version} 애플리케이션이 생성되었습니다.")
    return app


def setup_middleware(app: FastAPI) -> None:
    """미들웨어 설정"""
    
    # CORS 미들웨어
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=settings.allow_credentials,
        allow_methods=settings.allowed_methods,
        allow_headers=settings.allowed_headers,
    )
    
    # Trusted Host 미들웨어 (보안)
    if not settings.debug:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["localhost", "127.0.0.1", "*.vercel.app"]
        )
    
    # 요청 로깅 미들웨어
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        user_id = None
        
        # 인증 정보 추출 (가능한 경우)
        auth_header = request.headers.get("authorization")
        if auth_header:
            try:
                # 간단한 로깅용 사용자 ID 추출 (보안상 민감하지 않은 정보만)
                # 실제 구현시에는 토큰 검증 로직 필요
                pass  # 추후 구현
            except:
                pass
        
        # 요청 로그
        log_api_request(logger, request.method, str(request.url.path), user_id)
        
        # 요청 처리
        response = await call_next(request)
        
        # 응답 로그
        process_time = time.time() - start_time
        log_api_response(logger, request.method, str(request.url.path), response.status_code, process_time)
        
        # 성능 메트릭 헤더 추가
        response.headers["X-Process-Time"] = str(process_time)
        
        return response


def setup_exception_handlers(app: FastAPI) -> None:
    """예외 핸들러 설정"""
    
    # 커스텀 API 예외 핸들러
    @app.exception_handler(BaseAPIException)
    async def custom_exception_handler(request: Request, exc: BaseAPIException):
        logger.error(f"API 예외 발생: {exc.error_code} - {exc.detail}")
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "error_code": exc.error_code,
                "path": str(request.url.path),
                "method": request.method
            },
            headers=exc.headers
        )
    
    # 유효성 검사 예외 핸들러
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(f"요청 유효성 검사 실패: {exc.errors()}")
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "요청 데이터의 유효성 검사에 실패했습니다.",
                "error_code": "VALIDATION_ERROR",
                "errors": exc.errors(),
                "path": str(request.url.path),
                "method": request.method
            }
        )
    
    # 일반 예외 핸들러
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"예상치 못한 오류 발생: {type(exc).__name__}: {str(exc)}", exc_info=True)
        
        # 프로덕션 환경에서는 상세한 오류 정보 숨김
        detail = str(exc) if settings.debug else APIConstants.Messages.INTERNAL_ERROR
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": detail,
                "error_code": "INTERNAL_SERVER_ERROR",
                "path": str(request.url.path),
                "method": request.method
            }
        )


def setup_routers(app: FastAPI) -> None:
    """라우터 설정"""
    
    # API 버전 접두사
    api_prefix = APIConstants.API_V1_PREFIX
    
    # 라우터 등록
    app.include_router(
        user_auth0.router, 
        prefix=f"{api_prefix}/users",
        tags=["사용자 관리"]
    )
    app.include_router(
        photo_route.router, 
        prefix=api_prefix,
        tags=["사진 관리"]
    )
    app.include_router(
        llm_route.router, 
        prefix=api_prefix,
        tags=["LLM 분석"]
    )
    app.include_router(
        post_route.router, 
        prefix=api_prefix,
        tags=["포스트 관리"]
    )
    app.include_router(
        image_metadata.router, 
        prefix=f"{api_prefix}/images",
        tags=["이미지 메타데이터"]
    )
    
    # 헬스체크 엔드포인트
    @app.get("/health", tags=["헬스체크"])
    async def health_check():
        """애플리케이션 헬스체크"""
        return {
            "status": "healthy",
            "app_name": settings.app_name,
            "version": settings.app_version,
            "timestamp": time.time()
        }
    
    # 루트 엔드포인트
    @app.get("/", tags=["기본"])
    async def read_root():
        """API 루트 엔드포인트"""
        return {
            "message": f"Welcome to {settings.app_name}",
            "version": settings.app_version,
            "docs_url": "/docs" if settings.debug else "문서는 프로덕션 환경에서 비활성화됩니다.",
            "health_url": "/health"
        }


def setup_event_handlers(app: FastAPI) -> None:
    """이벤트 핸들러 설정"""
    
    @app.on_event("startup")
    async def startup_event():
        """애플리케이션 시작시 실행"""
        logger.info(f"{settings.app_name} 서버가 시작되었습니다.")
        logger.info(f"디버그 모드: {settings.debug}")
        logger.info(f"허용된 CORS origins: {settings.allowed_origins}")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """애플리케이션 종료시 실행"""
        logger.info(f"{settings.app_name} 서버가 종료됩니다.")


# 애플리케이션 인스턴스 생성
app = create_application() 