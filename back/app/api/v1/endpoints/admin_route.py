from fastapi import APIRouter, Depends, HTTPException
from typing import List
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.auth import require_admin
from app.db.session import get_db
from app.services.system_config import system_config_service
from app.models.db_models import User, Post, Place

router = APIRouter(prefix="/admin", tags=["관리자"])


class ConfigItem(BaseModel):
    key: str
    value: str
    description: str = ""
    type: str = "string"
    options: List[str] = []


class ConfigUpdateRequest(BaseModel):
    value: str


def _validate_value(key: str, value: str) -> None:
    """type별 값 검증. 실패 시 HTTPException 발생."""
    meta = system_config_service.get_meta(key)
    vtype = meta.get("type", "string")

    if vtype == "number":
        try:
            float(value)
        except ValueError:
            raise HTTPException(status_code=400, detail="설정 값은 숫자여야 합니다.")
    elif vtype == "enum":
        options = meta.get("options", [])
        # 빈 문자열은 "환경변수 사용"을 의미하므로 허용
        if value and options and value not in options:
            raise HTTPException(
                status_code=400,
                detail=f"허용된 값: {', '.join(options)} (또는 빈 문자열)",
            )
    # string 타입은 자유 입력 허용 (빈 문자열 포함)


def _on_config_change(key: str) -> None:
    """설정 변경 후 후처리 (싱글톤 무효화 등)"""
    if key in ("llm_provider", "llm_model_name"):
        from app.services.llm_factory import reset_llm
        reset_llm()


@router.get("/settings", response_model=List[ConfigItem])
async def get_settings(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """전체 시스템 설정 목록 조회"""
    return system_config_service.get_all(db)


class AdminStats(BaseModel):
    users_total: int
    users_active: int
    users_inactive: int
    posts_total: int
    posts_published: int
    posts_draft: int
    posts_deleted: int
    places_total: int
    places_missing_city: int


@router.get("/stats", response_model=AdminStats)
async def get_stats(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """관리자 대시보드 요약 통계."""
    users_total = db.query(func.count(User.id)).scalar() or 0
    users_active = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0

    posts_total = db.query(func.count(Post.id)).filter(Post.deleted_at.is_(None)).scalar() or 0
    posts_published = db.query(func.count(Post.id)).filter(
        Post.deleted_at.is_(None), Post.status == "published"
    ).scalar() or 0
    posts_draft = db.query(func.count(Post.id)).filter(
        Post.deleted_at.is_(None), Post.status == "draft"
    ).scalar() or 0
    posts_deleted = db.query(func.count(Post.id)).filter(Post.deleted_at.is_not(None)).scalar() or 0

    places_total = db.query(func.count(Place.id)).scalar() or 0
    places_missing_city = db.query(func.count(Place.id)).filter(
        or_(Place.city.is_(None), Place.city == "")
    ).scalar() or 0

    return AdminStats(
        users_total=users_total,
        users_active=users_active,
        users_inactive=users_total - users_active,
        posts_total=posts_total,
        posts_published=posts_published,
        posts_draft=posts_draft,
        posts_deleted=posts_deleted,
        places_total=places_total,
        places_missing_city=places_missing_city,
    )


@router.put("/settings/{key}", response_model=ConfigItem)
async def update_setting(
    key: str,
    body: ConfigUpdateRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """시스템 설정 값 변경"""
    _validate_value(key, body.value)
    system_config_service.set(key, body.value, db)
    _on_config_change(key)

    all_configs = system_config_service.get_all(db)
    for item in all_configs:
        if item["key"] == key:
            return item

    return {"key": key, "value": body.value, "description": "", "type": "string", "options": []}
