"""
User Repository - 사용자 데이터 접근 계층
"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.db_models import User
from app.schemas.user import UserCreate, UserUpdate
import logging

logger = logging.getLogger(__name__)


class UserRepository:
    """사용자 데이터베이스 접근 클래스"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_or_update_user(self, user_data: UserCreate) -> Optional[User]:
        """
        사용자 생성 또는 업데이트 (UPSERT)
        
        Args:
            user_data: 사용자 생성/업데이트 데이터
            
        Returns:
            User: 생성/업데이트된 사용자 객체
            
        Raises:
            Exception: 데이터베이스 작업 실패시
        """
        try:
            # MySQL UPSERT 쿼리 실행
            result = self.db.execute(text("""
                INSERT INTO users (id, email, name, profile_image)
                VALUES (:id, :email, :name, :picture)
                ON DUPLICATE KEY UPDATE
                    name = VALUES(name),
                    profile_image = VALUES(profile_image),
                    updated_at = NOW()
            """), {
                "id": user_data.id,
                "email": user_data.email,
                "name": user_data.name,
                "picture": user_data.picture
            })
            
            self.db.commit()
            
            # 업데이트된 사용자 정보 반환
            return self.get_user_by_id(user_data.id)
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"사용자 생성/업데이트 실패: {str(e)}")
            raise
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        ID로 사용자 조회
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            User: 사용자 객체 또는 None
        """
        try:
            return self.db.query(User).filter(User.id == user_id).first()
        except Exception as e:
            logger.error(f"사용자 조회 실패: {str(e)}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        이메일로 사용자 조회
        
        Args:
            email: 사용자 이메일
            
        Returns:
            User: 사용자 객체 또는 None
        """
        try:
            return self.db.query(User).filter(User.email == email).first()
        except Exception as e:
            logger.error(f"이메일로 사용자 조회 실패: {str(e)}")
            return None
    
    def update_user(self, user_id: str, user_data: UserUpdate) -> Optional[User]:
        """
        사용자 정보 업데이트
        
        Args:
            user_id: 사용자 ID
            user_data: 업데이트할 사용자 데이터
            
        Returns:
            User: 업데이트된 사용자 객체 또는 None
        """
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                return None
            
            # 업데이트할 필드만 수정
            update_data = user_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(user, field, value)
            
            self.db.commit()
            self.db.refresh(user)
            return user
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"사용자 업데이트 실패: {str(e)}")
            raise
    
    def delete_user(self, user_id: str) -> bool:
        """
        사용자 삭제
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            bool: 삭제 성공 여부
        """
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                return False
            
            self.db.delete(user)
            self.db.commit()
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"사용자 삭제 실패: {str(e)}")
            return False