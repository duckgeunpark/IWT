"""
사용자 LLM 파이프라인 커스터마이즈 설정 API

GET  /llm-preferences        → 내 설정 조회 (없으면 기본값 반환)
PUT  /llm-preferences        → 내 설정 저장/수정
GET  /llm-preferences/options → 선택 가능한 옵션 목록
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.db_models import UserLLMPreference
from app.services.llm_pipeline_prompts import (
    DEFAULT_PREFERENCES,
    TONE_GUIDE,
    STYLE_GUIDE,
    LANG_TITLE_GUIDE,
)

router = APIRouter(prefix="/llm-preferences", tags=["LLM 설정"])


# ── 스키마 ───────────────────────────────────────────────────────────

class LLMPreferenceResponse(BaseModel):
    tone:         str
    style:        str
    lang:         str
    stage1_extra: Optional[str]
    stage2_extra: Optional[str]
    stage3_extra: Optional[str]
    updated_at:   Optional[datetime]

    class Config:
        from_attributes = True


class LLMPreferenceUpdate(BaseModel):
    tone:         Optional[str] = Field(None, description="casual|formal|poetic|humorous")
    style:        Optional[str] = Field(None, description="blog|diary|travel_guide")
    lang:         Optional[str] = Field(None, description="ko|en|ja|zh|fr")
    stage1_extra: Optional[str] = Field(None, description="Stage1 추가 지침 (일정 표 생성)")
    stage2_extra: Optional[str] = Field(None, description="Stage2 추가 지침 (장소 단락 생성)")
    stage3_extra: Optional[str] = Field(None, description="Stage3 추가 지침 (전체 합성)")


# ── 엔드포인트 ───────────────────────────────────────────────────────

@router.get("/options")
async def get_options():
    """선택 가능한 tone / style / lang 옵션 목록"""
    return {
        "tone":  list(TONE_GUIDE.keys()),
        "style": list(STYLE_GUIDE.keys()),
        "lang":  list(LANG_TITLE_GUIDE.keys()),
    }


@router.get("/", response_model=LLMPreferenceResponse)
async def get_my_preferences(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """내 LLM 설정 조회 (설정 없으면 기본값 반환)"""
    user_id = current_user["sub"]
    pref = db.query(UserLLMPreference).filter(
        UserLLMPreference.user_id == user_id
    ).first()

    if pref:
        return pref

    # 기본값 반환 (DB 저장 안 함)
    return LLMPreferenceResponse(
        **DEFAULT_PREFERENCES,
        updated_at=None,
    )


@router.put("/", response_model=LLMPreferenceResponse)
async def update_my_preferences(
    body: LLMPreferenceUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """내 LLM 설정 저장/수정 (upsert)"""
    user_id = current_user["sub"]
    valid_tones  = list(TONE_GUIDE.keys())
    valid_styles = list(STYLE_GUIDE.keys())
    valid_langs  = list(LANG_TITLE_GUIDE.keys())

    pref = db.query(UserLLMPreference).filter(
        UserLLMPreference.user_id == user_id
    ).first()

    if not pref:
        pref = UserLLMPreference(
            user_id=user_id,
            **DEFAULT_PREFERENCES,
        )
        db.add(pref)

    if body.tone is not None:
        if body.tone not in valid_tones:
            from fastapi import HTTPException
            raise HTTPException(400, f"tone은 {valid_tones} 중 하나여야 합니다.")
        pref.tone = body.tone

    if body.style is not None:
        if body.style not in valid_styles:
            from fastapi import HTTPException
            raise HTTPException(400, f"style은 {valid_styles} 중 하나여야 합니다.")
        pref.style = body.style

    if body.lang is not None:
        if body.lang not in valid_langs:
            from fastapi import HTTPException
            raise HTTPException(400, f"lang은 {valid_langs} 중 하나여야 합니다.")
        pref.lang = body.lang

    if body.stage1_extra is not None:
        pref.stage1_extra = body.stage1_extra or None
    if body.stage2_extra is not None:
        pref.stage2_extra = body.stage2_extra or None
    if body.stage3_extra is not None:
        pref.stage3_extra = body.stage3_extra or None

    pref.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(pref)
    return pref
