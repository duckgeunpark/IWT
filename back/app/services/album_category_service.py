"""
앨범 카테고리 분류 서비스
사진/여행별 국가, 도시, 테마 카테고리 자동 분류/저장
"""

from typing import Dict, List, Optional, Set
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class AlbumCategoryService:
    """앨범 카테고리 분류 서비스"""
    
    def __init__(self):
        # 테마 카테고리 정의
        self.theme_categories = {
            "nature": ["산", "바다", "숲", "공원", "정원", "폭포", "강", "호수", "해변", "mountain", "sea", "forest", "park", "garden", "waterfall", "river", "lake", "beach"],
            "culture": ["박물관", "미술관", "궁전", "사원", "교회", "성당", "유적지", "museum", "gallery", "palace", "temple", "church", "cathedral", "heritage"],
            "food": ["레스토랑", "카페", "음식점", "시장", "restaurant", "cafe", "food", "market", "dining"],
            "shopping": ["쇼핑몰", "상점", "시장", "mall", "shop", "store", "marketplace"],
            "entertainment": ["테마파크", "놀이공원", "영화관", "극장", "themepark", "amusement", "cinema", "theater"],
            "transportation": ["공항", "역", "버스터미널", "airport", "station", "terminal", "transport"],
            "urban": ["도시", "거리", "빌딩", "city", "street", "building", "urban", "downtown"],
            "rural": ["마을", "농촌", "전원", "village", "rural", "countryside", "farm"]
        }
        
        # 국가별 주요 도시 매핑
        self.country_cities = {
            "korea": ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "제주", "seoul", "busan", "daegu", "incheon", "gwangju", "daejeon", "ulsan", "jeju"],
            "japan": ["도쿄", "오사카", "교토", "요코하마", "나고야", "삿포로", "후쿠오카", "고베", "tokyo", "osaka", "kyoto", "yokohama", "nagoya", "sapporo", "fukuoka", "kobe"],
            "china": ["베이징", "상하이", "광저우", "선전", "청두", "항저우", "beijing", "shanghai", "guangzhou", "shenzhen", "chengdu", "hangzhou"],
            "usa": ["뉴욕", "로스앤젤레스", "시카고", "휴스턴", "피닉스", "필라델피아", "new york", "los angeles", "chicago", "houston", "phoenix", "philadelphia"],
            "uk": ["런던", "버밍엄", "리즈", "글래스고", "셰필드", "브래드포드", "london", "birmingham", "leeds", "glasgow", "sheffield", "bradford"],
            "france": ["파리", "마르세유", "리옹", "툴루즈", "니스", "낭트", "paris", "marseille", "lyon", "toulouse", "nice", "nantes"],
            "germany": ["베를린", "함부르크", "뮌헨", "쾰른", "프랑크푸르트", "슈투트가르트", "berlin", "hamburg", "munich", "cologne", "frankfurt", "stuttgart"],
            "italy": ["로마", "밀란", "나폴리", "토리노", "팔레르모", "제노바", "rome", "milan", "naples", "turin", "palermo", "genoa"]
        }
    
    async def classify_photo_categories(
        self, 
        photo_data: Dict,
        location_info: Optional[Dict] = None
    ) -> Dict:
        """
        개별 사진의 카테고리 분류
        
        Args:
            photo_data: 사진 데이터 (EXIF, 메타데이터 포함)
            location_info: 위치 정보
            
        Returns:
            분류된 카테고리 정보
        """
        try:
            categories = {
                "country": None,
                "city": None,
                "region": None,
                "themes": [],
                "confidence": 0.0
            }
            
            # 위치 기반 카테고리 분류
            if location_info:
                categories.update(await self._classify_location_categories(location_info))
            
            # EXIF 데이터 기반 분류
            if photo_data.get("exif"):
                exif_categories = await self._classify_exif_categories(photo_data["exif"])
                categories["themes"].extend(exif_categories.get("themes", []))
            
            # 중복 제거 및 정렬
            categories["themes"] = list(set(categories["themes"]))
            categories["themes"].sort()
            
            # 신뢰도 계산
            categories["confidence"] = await self._calculate_confidence(categories)
            
            return categories
            
        except Exception as e:
            logger.error(f"Failed to classify photo categories: {e}")
            return self._get_default_categories()
    
    async def classify_album_categories(
        self, 
        photos: List[Dict]
    ) -> Dict:
        """
        앨범 전체의 카테고리 분류
        
        Args:
            photos: 사진 리스트
            
        Returns:
            앨범 카테고리 정보
        """
        try:
            album_categories = {
                "countries": set(),
                "cities": set(),
                "regions": set(),
                "themes": set(),
                "total_photos": len(photos),
                "date_range": None
            }
            
            # 각 사진의 카테고리 수집
            for photo in photos:
                if photo.get("categories"):
                    categories = photo["categories"]
                    
                    if categories.get("country"):
                        album_categories["countries"].add(categories["country"])
                    
                    if categories.get("city"):
                        album_categories["cities"].add(categories["city"])
                    
                    if categories.get("region"):
                        album_categories["regions"].add(categories["region"])
                    
                    album_categories["themes"].update(categories.get("themes", []))
            
            # 날짜 범위 계산
            album_categories["date_range"] = await self._calculate_date_range(photos)
            
            # Set을 List로 변환
            result = {
                "countries": list(album_categories["countries"]),
                "cities": list(album_categories["cities"]),
                "regions": list(album_categories["regions"]),
                "themes": list(album_categories["themes"]),
                "total_photos": album_categories["total_photos"],
                "date_range": album_categories["date_range"]
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to classify album categories: {e}")
            return self._get_default_album_categories()
    
    async def _classify_location_categories(self, location_info: Dict) -> Dict:
        """위치 정보 기반 카테고리 분류"""
        categories = {}
        
        # 국가 분류
        country = location_info.get("country", "").lower()
        for country_name, cities in self.country_cities.items():
            if country_name in country or any(city.lower() in country for city in cities):
                categories["country"] = country_name
                break
        
        # 도시 분류
        city = location_info.get("city", "").lower()
        for country_name, cities in self.country_cities.items():
            for city_name in cities:
                if city_name.lower() in city:
                    categories["city"] = city_name
                    categories["country"] = country_name
                    break
            if categories.get("city"):
                break
        
        # 지역 분류
        if location_info.get("state"):
            categories["region"] = location_info["state"]
        
        return categories
    
    async def _classify_exif_categories(self, exif_data: Dict) -> Dict:
        """EXIF 데이터 기반 테마 분류"""
        themes = []
        
        # 카메라 정보 기반 분류
        camera_info = exif_data.get("camera_info", {})
        if camera_info.get("make") or camera_info.get("model"):
            themes.append("photography")
        
        # 이미지 정보 기반 분류
        image_info = exif_data.get("image_info", {})
        if image_info.get("width") and image_info.get("height"):
            # 고해상도 이미지는 풍경 사진일 가능성
            if image_info["width"] * image_info["height"] > 20000000:  # 20MP 이상
                themes.append("landscape")
        
        return {"themes": themes}
    
    async def _calculate_confidence(self, categories: Dict) -> float:
        """카테고리 분류 신뢰도 계산"""
        confidence = 0.0
        
        # 국가 정보가 있으면 +0.4
        if categories.get("country"):
            confidence += 0.4
        
        # 도시 정보가 있으면 +0.3
        if categories.get("city"):
            confidence += 0.3
        
        # 테마 정보가 있으면 +0.2
        if categories.get("themes"):
            confidence += min(0.2, len(categories["themes"]) * 0.1)
        
        # 지역 정보가 있으면 +0.1
        if categories.get("region"):
            confidence += 0.1
        
        return min(1.0, confidence)
    
    async def _calculate_date_range(self, photos: List[Dict]) -> Optional[Dict]:
        """사진들의 날짜 범위 계산"""
        try:
            dates = []
            
            for photo in photos:
                if photo.get("exif", {}).get("datetime"):
                    try:
                        date_str = photo["exif"]["datetime"]
                        # EXIF 날짜 형식: "YYYY:MM:DD HH:MM:SS"
                        date_obj = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                        dates.append(date_obj)
                    except ValueError:
                        continue
            
            if dates:
                dates.sort()
                return {
                    "start_date": dates[0].isoformat(),
                    "end_date": dates[-1].isoformat(),
                    "duration_days": (dates[-1] - dates[0]).days
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to calculate date range: {e}")
            return None
    
    async def suggest_themes(self, location_info: Dict) -> List[str]:
        """
        위치 정보 기반 테마 추천
        
        Args:
            location_info: 위치 정보
            
        Returns:
            추천 테마 리스트
        """
        try:
            suggested_themes = []
            
            # 위치 기반 테마 추천
            location_text = f"{location_info.get('country', '')} {location_info.get('city', '')} {location_info.get('landmark', '')}".lower()
            
            for theme, keywords in self.theme_categories.items():
                for keyword in keywords:
                    if keyword.lower() in location_text:
                        suggested_themes.append(theme)
                        break
            
            return list(set(suggested_themes))
            
        except Exception as e:
            logger.error(f"Failed to suggest themes: {e}")
            return []
    
    def _get_default_categories(self) -> Dict:
        """기본 카테고리 정보"""
        return {
            "country": None,
            "city": None,
            "region": None,
            "themes": [],
            "confidence": 0.0
        }
    
    def _get_default_album_categories(self) -> Dict:
        """기본 앨범 카테고리 정보"""
        return {
            "countries": [],
            "cities": [],
            "regions": [],
            "themes": [],
            "total_photos": 0,
            "date_range": None
        }


# 싱글톤 인스턴스
album_category_service = AlbumCategoryService() 