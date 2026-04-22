from fastapi import APIRouter, Depends, HTTPException
from typing import List
from pydantic import BaseModel

from app.core.auth import require_admin
from app.db.session import get_db
from app.services.system_config import system_config_service
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin", tags=["관리자"])


class ConfigItem(BaseModel):
    key: str
    value: str
    description: str = ""


class ConfigUpdateRequest(BaseModel):
    value: str


@router.get("/settings", response_model=List[ConfigItem])
async def get_settings(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """전체 시스템 설정 목록 조회"""
    return system_config_service.get_all(db)


@router.put("/settings/{key}", response_model=ConfigItem)
async def update_setting(
    key: str,
    body: ConfigUpdateRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    """시스템 설정 값 변경"""
    try:
        float(body.value)
    except ValueError:
        raise HTTPException(status_code=400, detail="설정 값은 숫자여야 합니다.")

    system_config_service.set(key, body.value, db)

    all_configs = system_config_service.get_all(db)
    for item in all_configs:
        if item["key"] == key:
            return item

    return {"key": key, "value": body.value, "description": ""}
