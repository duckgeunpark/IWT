"""
User Service - 사용자 비즈니스 로직 계층
"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.models.db_models import User
import logging

logger = logging.getLogger(__name__)


class UserService:
    """사용자 비즈니스 로직 서비스"""
    
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
    
    async def create_or_update_auth0_user(
        self, 
        user_data: UserCreate,
        token_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Auth0 사용자 생성 또는 업데이트
        
        Args:
            user_data: Auth0에서 받은 사용자 데이터
            token_payload: JWT 토큰 페이로드
            
        Returns:
            Dict: 처리 결과
        """
        try:
            logger.info(f"Auth0 사용자 처리 시작: {user_data.id}")
            
            # 토큰 검증 (필요시 추가 검증 로직)
            if token_payload.get('sub') != user_data.id:
                raise ValueError("토큰과 사용자 ID가 일치하지 않습니다.")
            
            # 사용자 생성 또는 업데이트
            user = await self.user_repo.create_or_update_user(user_data)
            
            if user:
                logger.info(f"Auth0 사용자 처리 완료: {user.id}")
                return {
                    "status": "success",
                    "message": "사용자 정보가 성공적으로 처리되었습니다.",
                    "user_id": user.id
                }
            else:
                raise Exception("사용자 생성/업데이트에 실패했습니다.")
                
        except ValueError as e:
            logger.warning(f"Auth0 사용자 검증 실패: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Auth0 사용자 처리 실패: {str(e)}")
            raise
    
    def get_user_profile(self, user_id: str) -> Optional[UserResponse]:
        """
        사용자 프로필 조회
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            UserResponse: 사용자 프로필 정보
        """
        try:
            user = self.user_repo.get_user_by_id(user_id)
            if user:
                return UserResponse.from_orm(user)
            return None
        except Exception as e:
            logger.error(f"사용자 프로필 조회 실패: {str(e)}")
            return None
    
    def update_user_profile(
        self, 
        user_id: str, 
        update_data: UserUpdate
    ) -> Optional[UserResponse]:
        """
        사용자 프로필 업데이트
        
        Args:
            user_id: 사용자 ID
            update_data: 업데이트할 데이터
            
        Returns:
            UserResponse: 업데이트된 사용자 정보
        """
        try:
            # 입력 데이터 검증
            if update_data.email:
                existing_user = self.user_repo.get_user_by_email(update_data.email)
                if existing_user and existing_user.id != user_id:
                    raise ValueError("이미 사용 중인 이메일입니다.")
            
            user = self.user_repo.update_user(user_id, update_data)
            if user:
                logger.info(f"사용자 프로필 업데이트 완료: {user_id}")
                return UserResponse.from_orm(user)
            return None
            
        except ValueError as e:
            logger.warning(f"사용자 프로필 업데이트 검증 실패: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"사용자 프로필 업데이트 실패: {str(e)}")
            raise
    
    def delete_user_account(self, user_id: str) -> bool:
        """
        사용자 계정 삭제
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            bool: 삭제 성공 여부
        """
        try:
            success = self.user_repo.delete_user(user_id)
            if success:
                logger.info(f"사용자 계정 삭제 완료: {user_id}")
            return success
        except Exception as e:
            logger.error(f"사용자 계정 삭제 실패: {str(e)}")
            return False
    
    def validate_user_access(
        self, 
        user_id: str, 
        token_payload: Dict[str, Any]
    ) -> bool:
        """
        사용자 접근 권한 검증
        
        Args:
            user_id: 요청된 사용자 ID
            token_payload: JWT 토큰 페이로드
            
        Returns:
            bool: 접근 권한 여부
        """
        try:
            # 토큰의 사용자 ID와 요청된 사용자 ID 일치 확인
            token_user_id = token_payload.get('sub')
            return token_user_id == user_id
        except Exception as e:
            logger.error(f"사용자 접근 권한 검증 실패: {str(e)}")
            return False