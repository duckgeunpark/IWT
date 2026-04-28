"""관리자 — Place(장소) 관리

- GET    /admin/places              목록 (country/city/검색, 페이지네이션)
- GET    /admin/places/{id}         상세
- PATCH  /admin/places/{id}         보정 (name/city/country/region/place_type)
- DELETE /admin/places/{id}         삭제 (route_stops 참조 없을 때만)
- POST   /admin/places/{id}/regeocode  Google API 재호출로 필드 재계산
"""

from typing import List, Optional
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.db.session import get_db
from app.models.db_models import Place, RouteStop
from app.services.reverse_geocoder import (
    GOOGLE_MAPS_API_KEY,
    _GEOCODE_URL,
    _parse_google_response,
)

router = APIRouter(prefix="/admin/places", tags=["관리자-Place"])


# ── 응답 스키마 ───────────────────────────────────────────────────────

class PlaceListItem(BaseModel):
    id: int
    google_place_id: Optional[str] = None
    name: str
    place_type: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    latitude: float
    longitude: float
    visit_count: int = 0
    created_at: Optional[datetime] = None


class PlaceDetail(PlaceListItem):
    address: Optional[str] = None
    avg_stay_duration: Optional[int] = None
    updated_at: Optional[datetime] = None
    referenced_by_route_stops: int = 0


class PlaceListResponse(BaseModel):
    items: List[PlaceListItem]
    total: int
    page: int
    size: int


class PlaceUpdateRequest(BaseModel):
    name: Optional[str] = None
    place_type: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    address: Optional[str] = None


# ── 헬퍼 ──────────────────────────────────────────────────────────────

def _to_list_item(p: Place) -> PlaceListItem:
    return PlaceListItem(
        id=p.id,
        google_place_id=p.google_place_id,
        name=p.name,
        place_type=p.place_type,
        country=p.country,
        city=p.city,
        region=p.region,
        latitude=p.latitude,
        longitude=p.longitude,
        visit_count=p.visit_count or 0,
        created_at=p.created_at,
    )


def _to_detail(p: Place, ref_count: int) -> PlaceDetail:
    return PlaceDetail(
        **_to_list_item(p).model_dump(),
        address=p.address,
        avg_stay_duration=p.avg_stay_duration,
        updated_at=p.updated_at,
        referenced_by_route_stops=ref_count,
    )


# ── 엔드포인트 ────────────────────────────────────────────────────────

@router.get("", response_model=PlaceListResponse)
async def list_places(
    q: Optional[str] = Query(None, description="이름/주소 검색"),
    country: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    missing_city: bool = Query(False, description="city 없는 Place만"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    sort: str = Query("recent", description="recent | visits"),
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Place 목록 (필터링/페이지네이션)"""
    query = db.query(Place)

    if q:
        like = f"%{q}%"
        query = query.filter(or_(Place.name.ilike(like), Place.address.ilike(like)))
    if country:
        query = query.filter(Place.country == country)
    if city:
        query = query.filter(Place.city == city)
    if missing_city:
        query = query.filter(or_(Place.city.is_(None), Place.city == ""))

    total = query.with_entities(Place.id).count()

    if sort == "visits":
        query = query.order_by(Place.visit_count.desc(), Place.id.desc())
    else:
        query = query.order_by(Place.created_at.desc(), Place.id.desc())

    rows = query.offset((page - 1) * size).limit(size).all()
    return PlaceListResponse(
        items=[_to_list_item(p) for p in rows],
        total=total,
        page=page,
        size=size,
    )


@router.get("/{place_id}", response_model=PlaceDetail)
async def get_place(
    place_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Place 상세 + 참조 카운트"""
    p = db.query(Place).filter(Place.id == place_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Place를 찾을 수 없습니다.")

    ref_count = db.query(func.count(RouteStop.id)).filter(RouteStop.place_id == place_id).scalar() or 0
    return _to_detail(p, ref_count)


@router.patch("/{place_id}", response_model=PlaceDetail)
async def update_place(
    place_id: int,
    body: PlaceUpdateRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Place 필드 보정 (name/city/country/region/place_type/address)"""
    p = db.query(Place).filter(Place.id == place_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Place를 찾을 수 없습니다.")

    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="변경할 필드가 없습니다.")

    for field, value in data.items():
        setattr(p, field, value)

    db.commit()
    db.refresh(p)
    return await get_place(place_id, db, admin)


@router.delete("/{place_id}")
async def delete_place(
    place_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """Place 삭제. RouteStop 참조가 있으면 차단(데이터 무결성)."""
    p = db.query(Place).filter(Place.id == place_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Place를 찾을 수 없습니다.")

    ref_count = db.query(func.count(RouteStop.id)).filter(RouteStop.place_id == place_id).scalar() or 0
    if ref_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"이 Place를 참조하는 RouteStop이 {ref_count}개 있어 삭제할 수 없습니다. 보정(PATCH)을 권장합니다.",
        )

    db.delete(p)
    db.commit()
    return {"deleted": True, "id": place_id}


@router.post("/{place_id}/regeocode", response_model=PlaceDetail)
async def regeocode_place(
    place_id: int,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    """Google Geocoding API를 재호출해 Place 필드를 재계산."""
    p = db.query(Place).filter(Place.id == place_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Place를 찾을 수 없습니다.")

    if not GOOGLE_MAPS_API_KEY:
        raise HTTPException(status_code=503, detail="GOOGLE_MAPS_API_KEY 미설정.")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                _GEOCODE_URL,
                params={"latlng": f"{p.latitude},{p.longitude}", "key": GOOGLE_MAPS_API_KEY, "language": "ko"},
            )
        data = resp.json()
        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            raise HTTPException(
                status_code=502,
                detail=f"Google Maps 오류: {data.get('status')} {data.get('error_message') or ''}",
            )
        parsed = _parse_google_response(data, p.latitude, p.longitude)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Google Maps 호출 실패: {e}")

    if parsed:
        if parsed.get("landmark"):
            p.name = parsed["landmark"]
        if parsed.get("place_type"):
            p.place_type = parsed["place_type"]
        if parsed.get("address"):
            p.address = parsed["address"]
        if parsed.get("country"):
            p.country = parsed["country"]
        if parsed.get("city"):
            p.city = parsed["city"]
        if parsed.get("region"):
            p.region = parsed["region"]
        if parsed.get("place_id") and parsed["place_id"] != p.google_place_id:
            existing = db.query(Place).filter(
                Place.google_place_id == parsed["place_id"],
                Place.id != p.id,
            ).first()
            if not existing:
                p.google_place_id = parsed["place_id"]

        db.commit()
        db.refresh(p)

    return await get_place(place_id, db, admin)
