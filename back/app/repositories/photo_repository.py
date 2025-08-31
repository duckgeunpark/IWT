"""
Photo Repository - 사진 데이터 접근 계층
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from app.models.db_models import Photo, Location, PhotoLabel, LLMAnalysis, ImageMetadata
import logging

logger = logging.getLogger(__name__)


class PhotoRepository:
    """사진 데이터베이스 접근 클래스"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_photo(self, photo_data: Dict[str, Any]) -> Optional[Photo]:
        """
        사진 정보 생성
        
        Args:
            photo_data: 사진 정보 딕셔너리
            
        Returns:
            Photo: 생성된 사진 객체
        """
        try:
            photo = Photo(**photo_data)
            self.db.add(photo)
            self.db.commit()
            self.db.refresh(photo)
            return photo
        except Exception as e:
            self.db.rollback()
            logger.error(f"사진 생성 실패: {str(e)}")
            raise
    
    def get_photo_by_id(self, photo_id: int) -> Optional[Photo]:
        """
        ID로 사진 조회
        
        Args:
            photo_id: 사진 ID
            
        Returns:
            Photo: 사진 객체 또는 None
        """
        try:
            return self.db.query(Photo).filter(Photo.id == photo_id).first()
        except Exception as e:
            logger.error(f"사진 조회 실패: {str(e)}")
            return None
    
    def get_photo_by_file_key(self, file_key: str) -> Optional[Photo]:
        """
        파일 키로 사진 조회
        
        Args:
            file_key: S3 파일 키
            
        Returns:
            Photo: 사진 객체 또는 None
        """
        try:
            return self.db.query(Photo).filter(Photo.file_key == file_key).first()
        except Exception as e:
            logger.error(f"파일 키로 사진 조회 실패: {str(e)}")
            return None
    
    def get_photos_by_post_id(self, post_id: int) -> List[Photo]:
        """
        포스트 ID로 사진 목록 조회
        
        Args:
            post_id: 포스트 ID
            
        Returns:
            List[Photo]: 사진 목록
        """
        try:
            return (self.db.query(Photo)
                   .filter(Photo.post_id == post_id)
                   .order_by(desc(Photo.upload_time))
                   .all())
        except Exception as e:
            logger.error(f"포스트별 사진 조회 실패: {str(e)}")
            return []
    
    def create_location(self, location_data: Dict[str, Any]) -> Optional[Location]:
        """
        위치 정보 생성
        
        Args:
            location_data: 위치 정보 딕셔너리
            
        Returns:
            Location: 생성된 위치 객체
        """
        try:
            location = Location(**location_data)
            self.db.add(location)
            self.db.commit()
            self.db.refresh(location)
            return location
        except Exception as e:
            self.db.rollback()
            logger.error(f"위치 정보 생성 실패: {str(e)}")
            raise
    
    def create_photo_label(self, label_data: Dict[str, Any]) -> Optional[PhotoLabel]:
        """
        사진 라벨 생성
        
        Args:
            label_data: 라벨 정보 딕셔너리
            
        Returns:
            PhotoLabel: 생성된 라벨 객체
        """
        try:
            label = PhotoLabel(**label_data)
            self.db.add(label)
            self.db.commit()
            self.db.refresh(label)
            return label
        except Exception as e:
            self.db.rollback()
            logger.error(f"사진 라벨 생성 실패: {str(e)}")
            raise
    
    def create_llm_analysis(self, analysis_data: Dict[str, Any]) -> Optional[LLMAnalysis]:
        """
        LLM 분석 결과 생성
        
        Args:
            analysis_data: 분석 결과 딕셔너리
            
        Returns:
            LLMAnalysis: 생성된 분석 객체
        """
        try:
            analysis = LLMAnalysis(**analysis_data)
            self.db.add(analysis)
            self.db.commit()
            self.db.refresh(analysis)
            return analysis
        except Exception as e:
            self.db.rollback()
            logger.error(f"LLM 분석 결과 생성 실패: {str(e)}")
            raise
    
    def create_image_metadata(self, metadata_data: Dict[str, Any]) -> Optional[ImageMetadata]:
        """
        이미지 메타데이터 생성
        
        Args:
            metadata_data: 메타데이터 딕셔너리
            
        Returns:
            ImageMetadata: 생성된 메타데이터 객체
        """
        try:
            metadata = ImageMetadata(**metadata_data)
            self.db.add(metadata)
            self.db.commit()
            self.db.refresh(metadata)
            return metadata
        except Exception as e:
            self.db.rollback()
            logger.error(f"이미지 메타데이터 생성 실패: {str(e)}")
            raise
    
    def get_photos_with_location(self, limit: int = 100) -> List[Photo]:
        """
        위치 정보가 있는 사진 목록 조회
        
        Args:
            limit: 최대 조회 수
            
        Returns:
            List[Photo]: 위치 정보가 있는 사진 목록
        """
        try:
            return (self.db.query(Photo)
                   .join(Location)
                   .filter(and_(
                       Location.latitude.isnot(None),
                       Location.longitude.isnot(None)
                   ))
                   .order_by(desc(Photo.upload_time))
                   .limit(limit)
                   .all())
        except Exception as e:
            logger.error(f"위치 정보가 있는 사진 조회 실패: {str(e)}")
            return []
    
    def update_photo(self, photo_id: int, update_data: Dict[str, Any]) -> Optional[Photo]:
        """
        사진 정보 업데이트
        
        Args:
            photo_id: 사진 ID
            update_data: 업데이트할 데이터
            
        Returns:
            Photo: 업데이트된 사진 객체 또는 None
        """
        try:
            photo = self.get_photo_by_id(photo_id)
            if not photo:
                return None
            
            for field, value in update_data.items():
                if hasattr(photo, field):
                    setattr(photo, field, value)
            
            self.db.commit()
            self.db.refresh(photo)
            return photo
        except Exception as e:
            self.db.rollback()
            logger.error(f"사진 정보 업데이트 실패: {str(e)}")
            raise
    
    def delete_photo(self, photo_id: int) -> bool:
        """
        사진 삭제
        
        Args:
            photo_id: 사진 ID
            
        Returns:
            bool: 삭제 성공 여부
        """
        try:
            photo = self.get_photo_by_id(photo_id)
            if not photo:
                return False
            
            self.db.delete(photo)
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"사진 삭제 실패: {str(e)}")
            return False