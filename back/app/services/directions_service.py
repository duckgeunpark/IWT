"""
Google Directions API 연동 서비스

직선(geodesic) 경로 → 실제 도로 기반 경로로 변경
구간별 이동 시간/거리/경로 폴리라인 제공
"""

import os
import httpx
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
DIRECTIONS_API_URL = "https://maps.googleapis.com/maps/api/directions/json"


class DirectionsService:
    """Google Directions API 서비스"""

    async def get_directions(
        self,
        waypoints: List[Dict[str, float]],
        mode: str = "driving",
    ) -> Dict[str, Any]:
        """
        여러 경유지 간 실제 도로 기반 경로 조회

        Args:
            waypoints: [{lat, lng}, ...] 최소 2개
            mode: driving, walking, bicycling, transit

        Returns:
            {
                total_distance_m, total_duration_s,
                segments: [{from, to, distance_m, duration_s, polyline, steps}],
                overview_polyline
            }
        """
        if not GOOGLE_MAPS_API_KEY:
            return {"error": "GOOGLE_MAPS_API_KEY가 설정되지 않았습니다.", "segments": []}

        if len(waypoints) < 2:
            return {"error": "최소 2개의 경유지가 필요합니다.", "segments": []}

        origin = f"{waypoints[0]['lat']},{waypoints[0]['lng']}"
        destination = f"{waypoints[-1]['lat']},{waypoints[-1]['lng']}"

        # 중간 경유지 (최대 23개, Directions API 제한)
        intermediate = []
        if len(waypoints) > 2:
            mid_points = waypoints[1:-1][:23]
            intermediate = [f"{w['lat']},{w['lng']}" for w in mid_points]

        params = {
            "origin": origin,
            "destination": destination,
            "mode": mode,
            "key": GOOGLE_MAPS_API_KEY,
            "language": "ko",
            "units": "metric",
        }
        if intermediate:
            params["waypoints"] = "|".join(intermediate)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(DIRECTIONS_API_URL, params=params, timeout=15.0)
                response.raise_for_status()
                data = response.json()

            if data.get("status") != "OK":
                logger.warning(f"Directions API 오류: {data.get('status')} - {data.get('error_message', '')}")
                return {
                    "error": f"Directions API: {data.get('status')}",
                    "segments": [],
                }

            return self._parse_response(data, waypoints)

        except httpx.HTTPError as e:
            logger.error(f"Directions API 요청 실패: {e}")
            return {"error": str(e), "segments": []}

    def _parse_response(
        self, data: Dict[str, Any], waypoints: List[Dict[str, float]]
    ) -> Dict[str, Any]:
        """Directions API 응답 파싱"""
        route = data["routes"][0]
        legs = route["legs"]

        total_distance_m = 0
        total_duration_s = 0
        segments = []

        for i, leg in enumerate(legs):
            distance_m = leg["distance"]["value"]
            duration_s = leg["duration"]["value"]
            total_distance_m += distance_m
            total_duration_s += duration_s

            steps = []
            for step in leg.get("steps", []):
                steps.append({
                    "instruction": step.get("html_instructions", ""),
                    "distance_m": step["distance"]["value"],
                    "duration_s": step["duration"]["value"],
                    "travel_mode": step.get("travel_mode", "DRIVING"),
                    "polyline": step.get("polyline", {}).get("points", ""),
                })

            segments.append({
                "from_index": i,
                "to_index": i + 1,
                "from_address": leg.get("start_address", ""),
                "to_address": leg.get("end_address", ""),
                "distance_m": distance_m,
                "distance_text": leg["distance"]["text"],
                "duration_s": duration_s,
                "duration_text": leg["duration"]["text"],
                "polyline": leg.get("overview_polyline", {}).get("points", ""),
                "steps": steps,
            })

        return {
            "total_distance_m": total_distance_m,
            "total_distance_text": self._format_distance(total_distance_m),
            "total_duration_s": total_duration_s,
            "total_duration_text": self._format_duration(total_duration_s),
            "segments": segments,
            "overview_polyline": route.get("overview_polyline", {}).get("points", ""),
            "bounds": route.get("bounds"),
        }

    @staticmethod
    def _format_distance(meters: int) -> str:
        if meters >= 1000:
            return f"{meters / 1000:.1f}km"
        return f"{meters}m"

    @staticmethod
    def _format_duration(seconds: int) -> str:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours > 0:
            return f"{hours}시간 {minutes}분"
        return f"{minutes}분"


# 인스턴스
directions_service = DirectionsService()
