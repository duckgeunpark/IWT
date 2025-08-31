from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.core.auth import get_current_user
from app.core.exceptions import (
    AuthenticationError, 
    DatabaseError, 
    ValidationError,
    NotFoundError
)
from app.core.logging import get_logger, log_api_request, log_api_response, log_error_with_context
from app.db.session import get_db
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.user_service import UserService
from app.core.config import APIConstants

router = APIRouter()
logger = get_logger("api.user_auth0")


@router.post(
    "/auth0", 
    status_code=APIConstants.StatusCodes.CREATED,
    response_model=Dict[str, Any],
    summary="Auth0 사용자 생성/업데이트",
    description="Auth0에서 인증된 사용자 정보를 시스템에 생성하거나 업데이트합니다."
)
async def create_or_update_auth0_user(
    user_data: UserCreate,
    token_payload: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Auth0 사용자 생성 또는 업데이트
    
    Args:
        user_data: Auth0에서 받은 사용자 데이터
        token_payload: JWT 토큰에서 추출한 사용자 정보
        db: 데이터베이스 세션
    
    Returns:
        사용자 생성/업데이트 결과
    
    Raises:
        AuthenticationError: 토큰 검증 실패
        ValidationError: 입력 데이터 검증 실패
        DatabaseError: 데이터베이스 작업 실패
    """
    log_api_request(logger, "POST", "/auth0", user_data.id)
    
    try:
        # 사용자 서비스 초기화
        user_service = UserService(db)
        
        # Auth0 사용자 처리
        result = await user_service.create_or_update_auth0_user(
            user_data, token_payload
        )
        
        logger.info(f"Auth0 사용자 처리 완료: {user_data.id}")
        return result
        
    except ValueError as e:
        log_error_with_context(logger, e, {"user_id": user_data.id})
        raise AuthenticationError(str(e))
    except Exception as e:
        log_error_with_context(logger, e, {"user_id": user_data.id})
        raise DatabaseError(f"사용자 처리 중 오류가 발생했습니다: {str(e)}")


@router.get(
    "/profile/{user_id}",
    response_model=UserResponse,
    summary="사용자 프로필 조회",
    description="특정 사용자의 프로필 정보를 조회합니다."
)
def get_user_profile(
    user_id: str,
    token_payload: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    사용자 프로필 조회
    
    Args:
        user_id: 조회할 사용자 ID
        token_payload: JWT 토큰에서 추출한 사용자 정보
        db: 데이터베이스 세션
    
    Returns:
        사용자 프로필 정보
    
    Raises:
        AuthenticationError: 접근 권한 없음
        NotFoundError: 사용자를 찾을 수 없음
    """
    log_api_request(logger, "GET", f"/profile/{user_id}", token_payload.get('sub'))
    
    try:
        user_service = UserService(db)
        
        # 접근 권한 확인
        if not user_service.validate_user_access(user_id, token_payload):
            raise AuthenticationError("해당 사용자 정보에 접근할 권한이 없습니다.")
        
        # 사용자 프로필 조회
        user_profile = user_service.get_user_profile(user_id)
        if not user_profile:
            raise NotFoundError("사용자를 찾을 수 없습니다.", "user")
        
        logger.info(f"사용자 프로필 조회 완료: {user_id}")
        return user_profile
        
    except (AuthenticationError, NotFoundError):
        raise
    except Exception as e:
        log_error_with_context(logger, e, {"user_id": user_id})
        raise DatabaseError(f"사용자 프로필 조회 중 오류가 발생했습니다: {str(e)}")


@router.put(
    "/profile/{user_id}",
    response_model=UserResponse,
    summary="사용자 프로필 업데이트",
    description="사용자의 프로필 정보를 업데이트합니다."
)
def update_user_profile(
    user_id: str,
    update_data: UserUpdate,
    token_payload: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    사용자 프로필 업데이트
    
    Args:
        user_id: 업데이트할 사용자 ID
        update_data: 업데이트할 데이터
        token_payload: JWT 토큰에서 추출한 사용자 정보
        db: 데이터베이스 세션
    
    Returns:
        업데이트된 사용자 프로필 정보
    
    Raises:
        AuthenticationError: 접근 권한 없음
        ValidationError: 입력 데이터 검증 실패
        NotFoundError: 사용자를 찾을 수 없음
    """
    log_api_request(logger, "PUT", f"/profile/{user_id}", token_payload.get('sub'))
    
    try:
        user_service = UserService(db)
        
        # 접근 권한 확인
        if not user_service.validate_user_access(user_id, token_payload):
            raise AuthenticationError("해당 사용자 정보를 수정할 권한이 없습니다.")
        
        # 사용자 프로필 업데이트
        updated_user = user_service.update_user_profile(user_id, update_data)
        if not updated_user:
            raise NotFoundError("사용자를 찾을 수 없습니다.", "user")
        
        logger.info(f"사용자 프로필 업데이트 완료: {user_id}")
        return updated_user
        
    except (AuthenticationError, ValidationError, NotFoundError):
        raise
    except ValueError as e:
        log_error_with_context(logger, e, {"user_id": user_id})
        raise ValidationError(str(e))
    except Exception as e:
        log_error_with_context(logger, e, {"user_id": user_id})
        raise DatabaseError(f"사용자 프로필 업데이트 중 오류가 발생했습니다: {str(e)}")


@router.delete(
    "/profile/{user_id}",
    status_code=APIConstants.StatusCodes.NO_CONTENT,
    summary="사용자 계정 삭제",
    description="사용자 계정을 완전히 삭제합니다."
)
def delete_user_account(
    user_id: str,
    token_payload: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> None:
    """
    사용자 계정 삭제
    
    Args:
        user_id: 삭제할 사용자 ID
        token_payload: JWT 토큰에서 추출한 사용자 정보
        db: 데이터베이스 세션
    
    Raises:
        AuthenticationError: 접근 권한 없음
        NotFoundError: 사용자를 찾을 수 없음
    """
    log_api_request(logger, "DELETE", f"/profile/{user_id}", token_payload.get('sub'))
    
    try:
        user_service = UserService(db)
        
        # 접근 권한 확인
        if not user_service.validate_user_access(user_id, token_payload):
            raise AuthenticationError("해당 사용자 계정을 삭제할 권한이 없습니다.")
        
        # 사용자 계정 삭제
        success = user_service.delete_user_account(user_id)
        if not success:
            raise NotFoundError("사용자를 찾을 수 없습니다.", "user")
        
        logger.info(f"사용자 계정 삭제 완료: {user_id}")
        
    except (AuthenticationError, NotFoundError):
        raise
    except Exception as e:
        log_error_with_context(logger, e, {"user_id": user_id})
        raise DatabaseError(f"사용자 계정 삭제 중 오류가 발생했습니다: {str(e)}")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="현재 사용자 정보 조회",
    description="JWT 토큰을 기반으로 현재 로그인한 사용자의 정보를 조회합니다."
)
def get_current_user_info(
    token_payload: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    현재 사용자 정보 조회
    
    Args:
        token_payload: JWT 토큰에서 추출한 사용자 정보
        db: 데이터베이스 세션
    
    Returns:
        현재 사용자 프로필 정보
    
    Raises:
        NotFoundError: 사용자를 찾을 수 없음
    """
    user_id = token_payload.get('sub')
    log_api_request(logger, "GET", "/me", user_id)
    
    try:
        user_service = UserService(db)
        
        # 현재 사용자 프로필 조회
        user_profile = user_service.get_user_profile(user_id)
        if not user_profile:
            raise NotFoundError("사용자를 찾을 수 없습니다.", "user")
        
        logger.info(f"현재 사용자 정보 조회 완료: {user_id}")
        return user_profile
        
    except NotFoundError:
        raise
    except Exception as e:
        log_error_with_context(logger, e, {"user_id": user_id})
        raise DatabaseError(f"사용자 정보 조회 중 오류가 발생했습니다: {str(e)}") 