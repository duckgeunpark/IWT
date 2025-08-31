"""
EXIF 메타데이터 처리 서비스
프론트엔드에서 전송된 EXIF 데이터를 처리하고 검증
"""

import os
from typing import Dict, Optional, List
import logging
from datetime import datetime
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class ExifExtractService:
    """EXIF 메타데이터 처리 서비스"""
    
    def __init__(self):
        logger.info("EXIF 처리 서비스 초기화")
    
    async def process_exif_data(self, exif_data: Dict) -> Dict:
        """
        프론트엔드에서 전송된 EXIF 데이터 처리
        
        Args:
            exif_data: 프론트엔드에서 전송된 EXIF 데이터
            
        Returns:
            처리된 EXIF 메타데이터
        """
        try:
            logger.info(f"EXIF 데이터 처리 시작: {exif_data}")
            
            if not exif_data:
                logger.warning("EXIF 데이터가 없습니다.")
                return self._get_default_metadata()
            
            # 데이터 검증 및 정리
            processed_data = {
                "camera_info": self._process_camera_info(exif_data.get("camera_info", {})),
                "datetime": self._process_datetime(exif_data.get("datetime")),
                "gps": self._process_gps_data(exif_data.get("gps")),
                "image_info": self._process_image_info(exif_data.get("image_info", {})),
                "extraction_success": exif_data.get("extraction_success", False)
            }
            
            logger.info(f"EXIF 데이터 처리 완료: GPS={processed_data['gps'] is not None}, DateTime={processed_data['datetime'] is not None}")
            return processed_data
            
        except Exception as e:
            logger.error(f"EXIF 데이터 처리 실패: {str(e)}")
            return self._get_default_metadata()
    
    async def prepare_exif_for_llm(self, exif_data: Dict) -> Dict:
        """
        LLM 분석을 위한 EXIF 데이터 준비
        
        Args:
            exif_data: 처리된 EXIF 데이터
            
        Returns:
            LLM 분석용 데이터
        """
        try:
            llm_data = {
                "location": None,
                "datetime": None,
                "camera_info": None,
                "image_metadata": None
            }
            
            # GPS 데이터 처리
            if exif_data.get("gps"):
                gps = exif_data["gps"]
                llm_data["location"] = {
                    "latitude": gps.get("latitude"),
                    "longitude": gps.get("longitude"),
                    "altitude": gps.get("altitude"),
                    "coordinates_available": bool(gps.get("latitude") and gps.get("longitude"))
                }
            
            # 날짜/시간 처리
            if exif_data.get("datetime"):
                llm_data["datetime"] = exif_data["datetime"]
            
            # 카메라 정보 처리
            if exif_data.get("camera_info"):
                llm_data["camera_info"] = {
                    "make": exif_data["camera_info"].get("make"),
                    "model": exif_data["camera_info"].get("model"),
                    "lens": exif_data["camera_info"].get("lens")
                }
            
            # 이미지 메타데이터 처리
            if exif_data.get("image_info"):
                llm_data["image_metadata"] = {
                    "width": exif_data["image_info"].get("width"),
                    "height": exif_data["image_info"].get("height"),
                    "format": exif_data["image_info"].get("format"),
                    "orientation": exif_data["image_info"].get("orientation")
                }
            
            return llm_data
            
        except Exception as e:
            logger.error(f"LLM용 EXIF 데이터 준비 실패: {str(e)}")
            return {}
    
    async def prepare_exif_for_labeling(self, exif_data: Dict) -> Dict:
        """
        라벨링 데이터베이스 저장을 위한 EXIF 데이터 준비
        
        Args:
            exif_data: 처리된 EXIF 데이터
            
        Returns:
            라벨링용 데이터
        """
        try:
            labeling_data = {
                "location_labels": [],
                "time_labels": [],
                "camera_labels": [],
                "image_labels": []
            }
            
            # 위치 라벨 생성
            if exif_data.get("gps"):
                gps = exif_data["gps"]
                if gps.get("latitude") and gps.get("longitude"):
                    labeling_data["location_labels"].append("has_gps_coordinates")
                if gps.get("altitude"):
                    labeling_data["location_labels"].append("has_altitude")
            
            # 시간 라벨 생성
            if exif_data.get("datetime"):
                labeling_data["time_labels"].append("has_datetime")
                # 시간대별 라벨 추가
                try:
                    dt = datetime.fromisoformat(exif_data["datetime"].replace("Z", "+00:00"))
                    hour = dt.hour
                    if 6 <= hour < 12:
                        labeling_data["time_labels"].append("morning")
                    elif 12 <= hour < 18:
                        labeling_data["time_labels"].append("afternoon")
                    elif 18 <= hour < 22:
                        labeling_data["time_labels"].append("evening")
                    else:
                        labeling_data["time_labels"].append("night")
                except:
                    pass
            
            # 카메라 라벨 생성
            if exif_data.get("camera_info"):
                camera = exif_data["camera_info"]
                if camera.get("make"):
                    labeling_data["camera_labels"].append(f"camera_make_{camera['make'].lower()}")
                if camera.get("model"):
                    labeling_data["camera_labels"].append(f"camera_model_{camera['model'].lower()}")
                if camera.get("lens"):
                    labeling_data["camera_labels"].append("has_lens_info")
            
            # 이미지 라벨 생성
            if exif_data.get("image_info"):
                image = exif_data["image_info"]
                if image.get("width") and image.get("height"):
                    aspect_ratio = image["width"] / image["height"]
                    if aspect_ratio > 1.5:
                        labeling_data["image_labels"].append("landscape")
                    elif aspect_ratio < 0.7:
                        labeling_data["image_labels"].append("portrait")
                    else:
                        labeling_data["image_labels"].append("square")
                
                if image.get("orientation"):
                    labeling_data["image_labels"].append(f"orientation_{image['orientation']}")
            
            return labeling_data
            
        except Exception as e:
            logger.error(f"라벨링용 EXIF 데이터 준비 실패: {str(e)}")
            return {"location_labels": [], "time_labels": [], "camera_labels": [], "image_labels": []}
    
    def _process_camera_info(self, camera_info: Dict) -> Dict:
        """카메라 정보 처리"""
        try:
            processed = {}
            
            if camera_info.get("make"):
                processed["make"] = str(camera_info["make"])
            
            if camera_info.get("model"):
                processed["model"] = str(camera_info["model"])
            
            if camera_info.get("lens"):
                processed["lens"] = str(camera_info["lens"])
                
            return processed
            
        except Exception as e:
            logger.error(f"카메라 정보 처리 실패: {str(e)}")
            return {}
    
    def _process_datetime(self, datetime_str: Optional[str]) -> Optional[str]:
        """날짜/시간 처리"""
        try:
            if not datetime_str:
                return None
            
            # EXIF 날짜 형식 검증 및 변환
            # 예: "2023:12:25 14:30:45" -> "2023-12-25T14:30:45"
            if ':' in datetime_str and ' ' in datetime_str:
                date_part, time_part = datetime_str.split(' ')
                year, month, day = date_part.split(':')
                return f"{year}-{month}-{day}T{time_part}"
            
            return str(datetime_str)
            
        except Exception as e:
            logger.error(f"날짜/시간 처리 실패: {str(e)}")
            return None
    
    def _process_gps_data(self, gps_data: Optional[Dict]) -> Optional[Dict]:
        """GPS 데이터 처리"""
        try:
            if not gps_data:
                return None
            
            processed = {}
            
            # 위도 검증
            if "latitude" in gps_data:
                lat = float(gps_data["latitude"])
                if -90 <= lat <= 90:
                    processed["latitude"] = lat
                else:
                    logger.warning(f"잘못된 위도 값: {lat}")
            
            # 경도 검증
            if "longitude" in gps_data:
                lon = float(gps_data["longitude"])
                if -180 <= lon <= 180:
                    processed["longitude"] = lon
                else:
                    logger.warning(f"잘못된 경도 값: {lon}")
            
            # 고도
            if "altitude" in gps_data:
                processed["altitude"] = float(gps_data["altitude"])
            
            return processed if processed else None
            
        except Exception as e:
            logger.error(f"GPS 데이터 처리 실패: {str(e)}")
            return None
    
    def _process_image_info(self, image_info: Dict) -> Dict:
        """이미지 정보 처리"""
        try:
            processed = {}
            
            if "width" in image_info:
                processed["width"] = int(image_info["width"])
            
            if "height" in image_info:
                processed["height"] = int(image_info["height"])
            
            if "format" in image_info:
                processed["format"] = str(image_info["format"])
            
            if "mode" in image_info:
                processed["mode"] = str(image_info["mode"])
            
            if "orientation" in image_info:
                processed["orientation"] = int(image_info["orientation"])
            
            return processed
            
        except Exception as e:
            logger.error(f"이미지 정보 처리 실패: {str(e)}")
            return {}
    
    def _get_default_metadata(self) -> Dict:
        """기본 메타데이터 반환"""
        return {
            "camera_info": {},
            "datetime": None,
            "gps": None,
            "image_info": {},
            "extraction_success": False
        }
    
    async def validate_gps_data(self, gps_data: Dict) -> bool:
        """
        GPS 데이터 유효성 검증
        
        Args:
            gps_data: GPS 데이터
            
        Returns:
            유효성 여부
        """
        if not gps_data:
            return False
        
        try:
            lat = gps_data.get("latitude")
            lon = gps_data.get("longitude")
            
            # 위도: -90 ~ 90
            if lat is None or lat < -90 or lat > 90:
                return False
            
            # 경도: -180 ~ 180
            if lon is None or lon < -180 or lon > 180:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"GPS 데이터 검증 실패: {str(e)}")
            return False


# 싱글톤 인스턴스
exif_service = ExifExtractService() 