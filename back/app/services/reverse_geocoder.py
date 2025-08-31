"""
역지오코딩 서비스
위경도 → 국가/도시 등 카테고리 변환, LLM 보조 프롬프트 데이터 제공
"""

import os
import requests
from typing import Dict, Optional, List
import logging
from fastapi import HTTPException
import json

logger = logging.getLogger(__name__)


class ReverseGeocoderService:
    """역지오코딩 서비스"""
    
    def __init__(self):
        # OpenStreetMap Nominatim API 사용
        self.nominatim_base_url = "https://nominatim.openstreetmap.org/reverse"
        self.geonames_username = os.getenv('GEONAMES_USERNAME', 'demo')
        
        # 캐시 설정
        self.cache = {}
    
    async def reverse_geocode(
        self, 
        latitude: float, 
        longitude: float,
        zoom: int = 10
    ) -> Dict:
        """
        위경도를 주소 정보로 변환
        
        Args:
            latitude: 위도
            longitude: 경도
            zoom: 상세도 레벨 (0-18)
            
        Returns:
            주소 정보
        """
        try:
            # 캐시 확인
            cache_key = f"{latitude:.6f}_{longitude:.6f}_{zoom}"
            if cache_key in self.cache:
                return self.cache[cache_key]
            
            # Nominatim API 호출
            params = {
                'lat': latitude,
                'lon': longitude,
                'format': 'json',
                'zoom': zoom,
                'addressdetails': 1
            }
            
            response = requests.get(
                self.nominatim_base_url,
                params=params,
                headers={'User-Agent': 'TripApp/1.0'}
            )
            
            if response.status_code != 200:
                logger.error(f"Geocoding API error: {response.status_code}")
                return self._get_default_location()
            
            data = response.json()
            
            # 주소 정보 파싱
            address_info = self._parse_address_data(data)
            
            # 캐시에 저장
            self.cache[cache_key] = address_info
            
            return address_info
            
        except Exception as e:
            logger.error(f"Failed to reverse geocode: {e}")
            return self._get_default_location()
    
    def _parse_address_data(self, data: Dict) -> Dict:
        """API 응답 데이터 파싱"""
        address = data.get('address', {})
        
        return {
            "country": address.get('country'),
            "country_code": address.get('country_code'),
            "state": address.get('state'),
            "city": address.get('city') or address.get('town') or address.get('village'),
            "district": address.get('suburb') or address.get('district'),
            "postcode": address.get('postcode'),
            "road": address.get('road'),
            "house_number": address.get('house_number'),
            "full_address": data.get('display_name'),
            "place_id": data.get('place_id'),
            "osm_type": data.get('osm_type'),
            "osm_id": data.get('osm_id'),
            "latitude": data.get('lat'),
            "longitude": data.get('lon')
        }
    
    async def get_location_categories(self, latitude: float, longitude: float) -> Dict:
        """
        위치 기반 카테고리 정보 추출
        
        Args:
            latitude: 위도
            longitude: 경도
            
        Returns:
            카테고리 정보
        """
        try:
            # 기본 주소 정보 가져오기
            address_info = await self.reverse_geocode(latitude, longitude)
            
            # 카테고리 정보 구성
            categories = {
                "country": {
                    "name": address_info.get("country"),
                    "code": address_info.get("country_code"),
                    "type": "country"
                },
                "region": {
                    "name": address_info.get("state"),
                    "type": "state"
                },
                "city": {
                    "name": address_info.get("city"),
                    "type": "city"
                },
                "district": {
                    "name": address_info.get("district"),
                    "type": "district"
                }
            }
            
            # 빈 값 제거
            categories = {k: v for k, v in categories.items() if v.get("name")}
            
            return categories
            
        except Exception as e:
            logger.error(f"Failed to get location categories: {e}")
            return {}
    
    async def generate_llm_prompt_data(
        self, 
        latitude: float, 
        longitude: float
    ) -> Dict:
        """
        LLM 추천 시스템을 위한 지역 정보 생성
        
        Args:
            latitude: 위도
            longitude: 경도
            
        Returns:
            LLM 프롬프트용 지역 정보
        """
        try:
            # 주소 정보 가져오기
            address_info = await self.reverse_geocode(latitude, longitude)
            categories = await self.get_location_categories(latitude, longitude)
            
            # LLM 프롬프트용 데이터 구성
            prompt_data = {
                "location_context": {
                    "full_address": address_info.get("full_address"),
                    "country": address_info.get("country"),
                    "state": address_info.get("state"),
                    "city": address_info.get("city"),
                    "district": address_info.get("district")
                },
                "categories": categories,
                "coordinates": {
                    "latitude": latitude,
                    "longitude": longitude
                },
                "place_metadata": {
                    "osm_id": address_info.get("osm_id"),
                    "osm_type": address_info.get("osm_type"),
                    "place_id": address_info.get("place_id")
                }
            }
            
            return prompt_data
            
        except Exception as e:
            logger.error(f"Failed to generate LLM prompt data: {e}")
            return {}
    
    async def get_nearby_places(
        self, 
        latitude: float, 
        longitude: float,
        radius: int = 1000,
        place_type: str = "tourism"
    ) -> List[Dict]:
        """
        주변 관광지 정보 조회
        
        Args:
            latitude: 위도
            longitude: 경도
            radius: 반경 (미터)
            place_type: 장소 타입
            
        Returns:
            주변 장소 리스트
        """
        try:
            # Overpass API 사용 (OpenStreetMap 데이터)
            overpass_url = "https://overpass-api.de/api/interpreter"
            
            query = f"""
            [out:json][timeout:25];
            (
              node["{place_type}"](around:{radius},{latitude},{longitude});
              way["{place_type}"](around:{radius},{latitude},{longitude});
              relation["{place_type}"](around:{radius},{latitude},{longitude});
            );
            out body;
            >;
            out skel qt;
            """
            
            response = requests.post(overpass_url, data=query)
            
            if response.status_code != 200:
                logger.error(f"Overpass API error: {response.status_code}")
                return []
            
            data = response.json()
            
            # 결과 파싱
            places = []
            for element in data.get('elements', []):
                if element.get('type') == 'node' and 'tags' in element:
                    place = {
                        "name": element['tags'].get('name'),
                        "type": element['tags'].get(place_type),
                        "latitude": element.get('lat'),
                        "longitude": element.get('lon'),
                        "tags": element['tags']
                    }
                    if place["name"]:
                        places.append(place)
            
            return places[:10]  # 최대 10개 반환
            
        except Exception as e:
            logger.error(f"Failed to get nearby places: {e}")
            return []
    
    def _get_default_location(self) -> Dict:
        """기본 위치 정보 반환"""
        return {
            "country": None,
            "country_code": None,
            "state": None,
            "city": None,
            "district": None,
            "postcode": None,
            "road": None,
            "house_number": None,
            "full_address": None,
            "place_id": None,
            "osm_type": None,
            "osm_id": None,
            "latitude": None,
            "longitude": None
        }
    
    async def validate_coordinates(self, latitude: float, longitude: float) -> bool:
        """
        좌표 유효성 검증
        
        Args:
            latitude: 위도
            longitude: 경도
            
        Returns:
            유효성 여부
        """
        # 위도: -90 ~ 90
        if not (-90 <= latitude <= 90):
            return False
        
        # 경도: -180 ~ 180
        if not (-180 <= longitude <= 180):
            return False
        
        return True


# 싱글톤 인스턴스
geocoder_service = ReverseGeocoderService() 