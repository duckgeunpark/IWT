"""
라벨링 데이터베이스 저장 서비스
EXIF 데이터와 LLM 분석 결과를 라벨링 데이터베이스에 저장
"""

import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.db_models import PhotoLabel, LLMAnalysis, ImageMetadata

logger = logging.getLogger(__name__)


class LabelingService:
    """라벨링 데이터베이스 저장 서비스"""
    
    def __init__(self):
        logger.info("라벨링 서비스 초기화")
    
    async def save_exif_labels(self, db: Session, photo_id: int, exif_data: Dict) -> bool:
        """
        EXIF 데이터에서 추출한 라벨들을 데이터베이스에 저장
        
        Args:
            db: 데이터베이스 세션
            photo_id: 사진 ID
            exif_data: EXIF 데이터
            
        Returns:
            저장 성공 여부
        """
        try:
            logger.info(f"EXIF 라벨 저장 시작 - photo_id: {photo_id}")
            
            # 기존 EXIF 라벨 삭제
            db.query(PhotoLabel).filter(
                PhotoLabel.photo_id == photo_id,
                PhotoLabel.source == "exif"
            ).delete()
            
            # 위치 라벨 저장
            if exif_data.get("gps"):
                gps = exif_data["gps"]
                if gps.get("latitude") and gps.get("longitude"):
                    self._save_label(db, photo_id, "location", "has_gps_coordinates", 1.0, "exif")
                if gps.get("altitude"):
                    self._save_label(db, photo_id, "location", "has_altitude", 1.0, "exif")
            
            # 시간 라벨 저장
            if exif_data.get("datetime"):
                self._save_label(db, photo_id, "time", "has_datetime", 1.0, "exif")
                
                # 시간대별 라벨 추가
                try:
                    dt = datetime.fromisoformat(exif_data["datetime"].replace("Z", "+00:00"))
                    hour = dt.hour
                    if 6 <= hour < 12:
                        self._save_label(db, photo_id, "time", "morning", 1.0, "exif")
                    elif 12 <= hour < 18:
                        self._save_label(db, photo_id, "time", "afternoon", 1.0, "exif")
                    elif 18 <= hour < 22:
                        self._save_label(db, photo_id, "time", "evening", 1.0, "exif")
                    else:
                        self._save_label(db, photo_id, "time", "night", 1.0, "exif")
                except Exception as e:
                    logger.warning(f"시간대 라벨 생성 실패: {str(e)}")
            
            # 카메라 라벨 저장
            if exif_data.get("camera_info"):
                camera = exif_data["camera_info"]
                if camera.get("make"):
                    self._save_label(db, photo_id, "camera", f"camera_make_{camera['make'].lower()}", 1.0, "exif")
                if camera.get("model"):
                    self._save_label(db, photo_id, "camera", f"camera_model_{camera['model'].lower()}", 1.0, "exif")
                if camera.get("lens"):
                    self._save_label(db, photo_id, "camera", "has_lens_info", 1.0, "exif")
            
            # 이미지 라벨 저장
            if exif_data.get("image_info"):
                image = exif_data["image_info"]
                if image.get("width") and image.get("height"):
                    aspect_ratio = image["width"] / image["height"]
                    if aspect_ratio > 1.5:
                        self._save_label(db, photo_id, "image", "landscape", 1.0, "exif")
                    elif aspect_ratio < 0.7:
                        self._save_label(db, photo_id, "image", "portrait", 1.0, "exif")
                    else:
                        self._save_label(db, photo_id, "image", "square", 1.0, "exif")
                
                if image.get("orientation"):
                    self._save_label(db, photo_id, "image", f"orientation_{image['orientation']}", 1.0, "exif")
            
            db.commit()
            logger.info(f"EXIF 라벨 저장 완료 - photo_id: {photo_id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"EXIF 라벨 저장 실패 - photo_id: {photo_id}, error: {str(e)}")
            return False
    
    async def save_llm_analysis(self, db: Session, photo_id: int, analysis_type: str, 
                               analysis_data: Dict, confidence: float = None, 
                               model_used: str = None) -> bool:
        """
        LLM 분석 결과를 데이터베이스에 저장
        
        Args:
            db: 데이터베이스 세션
            photo_id: 사진 ID
            analysis_type: 분석 타입 (location, scene, object, sentiment)
            analysis_data: 분석 데이터
            confidence: 신뢰도
            model_used: 사용된 모델명
            
        Returns:
            저장 성공 여부
        """
        try:
            logger.info(f"LLM 분석 저장 시작 - photo_id: {photo_id}, type: {analysis_type}")
            
            # 기존 분석 결과 삭제
            db.query(LLMAnalysis).filter(
                LLMAnalysis.photo_id == photo_id,
                LLMAnalysis.analysis_type == analysis_type
            ).delete()
            
            # 새로운 분석 결과 저장
            llm_analysis = LLMAnalysis(
                photo_id=photo_id,
                analysis_type=analysis_type,
                analysis_data=json.dumps(analysis_data, ensure_ascii=False),
                confidence=confidence,
                model_used=model_used,
                created_at=datetime.utcnow()
            )
            
            db.add(llm_analysis)
            db.commit()
            
            logger.info(f"LLM 분석 저장 완료 - photo_id: {photo_id}, type: {analysis_type}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"LLM 분석 저장 실패 - photo_id: {photo_id}, error: {str(e)}")
            return False
    
    async def save_llm_labels(self, db: Session, photo_id: int, llm_labels: Dict) -> bool:
        """
        LLM에서 생성된 라벨들을 데이터베이스에 저장
        
        Args:
            db: 데이터베이스 세션
            photo_id: 사진 ID
            llm_labels: LLM 라벨 데이터
            
        Returns:
            저장 성공 여부
        """
        try:
            logger.info(f"LLM 라벨 저장 시작 - photo_id: {photo_id}")
            
            # 기존 LLM 라벨 삭제
            db.query(PhotoLabel).filter(
                PhotoLabel.photo_id == photo_id,
                PhotoLabel.source == "llm"
            ).delete()
            
            # LLM 라벨 저장
            for label_type, labels in llm_labels.items():
                if isinstance(labels, list):
                    for label in labels:
                        if isinstance(label, dict):
                            label_name = label.get("name", str(label))
                            confidence = label.get("confidence", 0.8)
                        else:
                            label_name = str(label)
                            confidence = 0.8
                        
                        self._save_label(db, photo_id, label_type, label_name, confidence, "llm")
                elif isinstance(labels, str):
                    self._save_label(db, photo_id, label_type, labels, 0.8, "llm")
            
            db.commit()
            logger.info(f"LLM 라벨 저장 완료 - photo_id: {photo_id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"LLM 라벨 저장 실패 - photo_id: {photo_id}, error: {str(e)}")
            return False
    
    async def save_image_metadata(self, db: Session, photo_id: int, metadata_type: str, 
                                metadata_data: Dict) -> bool:
        """
        이미지 메타데이터를 데이터베이스에 저장
        
        Args:
            db: 데이터베이스 세션
            photo_id: 사진 ID
            metadata_type: 메타데이터 타입 (exif, llm_enhanced, manual)
            metadata_data: 메타데이터
            
        Returns:
            저장 성공 여부
        """
        try:
            logger.info(f"이미지 메타데이터 저장 시작 - photo_id: {photo_id}, type: {metadata_type}")
            
            # 기존 메타데이터 삭제
            db.query(ImageMetadata).filter(
                ImageMetadata.photo_id == photo_id,
                ImageMetadata.metadata_type == metadata_type
            ).delete()
            
            # 새로운 메타데이터 저장
            image_metadata = ImageMetadata(
                photo_id=photo_id,
                metadata_type=metadata_type,
                metadata_data=json.dumps(metadata_data, ensure_ascii=False),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(image_metadata)
            db.commit()
            
            logger.info(f"이미지 메타데이터 저장 완료 - photo_id: {photo_id}, type: {metadata_type}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"이미지 메타데이터 저장 실패 - photo_id: {photo_id}, error: {str(e)}")
            return False
    
    def _save_label(self, db: Session, photo_id: int, label_type: str, label_name: str, 
                   confidence: float, source: str) -> None:
        """
        개별 라벨을 데이터베이스에 저장
        
        Args:
            db: 데이터베이스 세션
            photo_id: 사진 ID
            label_type: 라벨 타입
            label_name: 라벨 이름
            confidence: 신뢰도
            source: 라벨 출처
        """
        try:
            photo_label = PhotoLabel(
                photo_id=photo_id,
                label_type=label_type,
                label_name=label_name,
                confidence=confidence,
                source=source,
                created_at=datetime.utcnow()
            )
            
            db.add(photo_label)
            
        except Exception as e:
            logger.error(f"라벨 저장 실패 - photo_id: {photo_id}, label: {label_name}, error: {str(e)}")
    
    async def get_photo_labels(self, db: Session, photo_id: int) -> Dict:
        """
        사진의 모든 라벨을 조회
        
        Args:
            db: 데이터베이스 세션
            photo_id: 사진 ID
            
        Returns:
            라벨 데이터
        """
        try:
            labels = db.query(PhotoLabel).filter(PhotoLabel.photo_id == photo_id).all()
            
            result = {
                "location": [],
                "time": [],
                "camera": [],
                "image": [],
                "llm_generated": []
            }
            
            for label in labels:
                if label.label_type in result:
                    result[label.label_type].append({
                        "name": label.label_name,
                        "confidence": label.confidence,
                        "source": label.source,
                        "created_at": label.created_at.isoformat()
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"라벨 조회 실패 - photo_id: {photo_id}, error: {str(e)}")
            return {}
    
    async def get_llm_analyses(self, db: Session, photo_id: int) -> Dict:
        """
        사진의 LLM 분석 결과를 조회
        
        Args:
            db: 데이터베이스 세션
            photo_id: 사진 ID
            
        Returns:
            LLM 분석 데이터
        """
        try:
            analyses = db.query(LLMAnalysis).filter(LLMAnalysis.photo_id == photo_id).all()
            
            result = {}
            for analysis in analyses:
                result[analysis.analysis_type] = {
                    "data": json.loads(analysis.analysis_data),
                    "confidence": analysis.confidence,
                    "model_used": analysis.model_used,
                    "created_at": analysis.created_at.isoformat()
                }
            
            return result
            
        except Exception as e:
            logger.error(f"LLM 분석 조회 실패 - photo_id: {photo_id}, error: {str(e)}")
            return {}


# 싱글톤 인스턴스
labeling_service = LabelingService() 