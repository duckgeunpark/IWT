"""
LangChain 기반 LLM 팩토리

설정 우선순위 (높음 → 낮음):
  1. 함수 인자 (caller가 명시적으로 전달)
  2. SystemConfig DB (관리자 페이지에서 설정)
  3. 환경 변수 (.env)
  4. 하드코딩 기본값
"""

import os
import logging
from typing import Optional
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

_default_llm: Optional[BaseChatModel] = None

# LLM 설정 변경 시 호출될 콜백 목록 (각 서비스의 chain 싱글톤 무효화용)
_reset_callbacks: list = []


def register_reset_callback(callback) -> None:
    """LLM 설정 변경 시 호출될 콜백 등록 (chain 싱글톤 무효화 등)"""
    if callback not in _reset_callbacks:
        _reset_callbacks.append(callback)


def _get_db_config(key: str) -> str:
    """SystemConfig DB에서 값을 조회. 빈 문자열이면 '미설정'으로 간주."""
    try:
        from app.db.session import SessionLocal
        from app.services.system_config import system_config_service
        with SessionLocal() as db:
            value = system_config_service.get(key, default=None, db=db)
        if isinstance(value, str) and value.strip():
            return value.strip()
    except Exception as e:
        logger.debug(f"SystemConfig DB 조회 실패 (key={key}): {e}")
    return ""


def _resolve_provider(provider: Optional[str]) -> str:
    if provider:
        return provider.lower()
    db_value = _get_db_config("llm_provider")
    if db_value:
        return db_value.lower()
    return os.getenv("LLM_PROVIDER", "gemini").lower()


def _resolve_model(provider: str, env_keys: list, default_model: str) -> str:
    """모델명 해석: DB(llm_model_name) > env_keys[*] > default"""
    db_model = _get_db_config("llm_model_name")
    if db_model:
        return db_model
    for env_key in env_keys:
        v = os.getenv(env_key)
        if v:
            return v
    return default_model


def get_llm(
    provider: str = None,
    temperature: float = 0.5,
    max_tokens: Optional[int] = None,
) -> BaseChatModel:
    """
    LangChain ChatModel 인스턴스 반환

    Args:
        provider: 제공자 이름. None이면 DB > env(LLM_PROVIDER) 순으로 조회
        temperature: 창의성 (0.0~1.0)
        max_tokens: 최대 출력 토큰 수 (None이면 모델 기본값)

    Returns:
        BaseChatModel 인스턴스
    """
    p = _resolve_provider(provider)

    if p == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        model = _resolve_model(p, ["GEMINI_MODEL", "LLM_MODEL_NAME"], "gemini-2.0-flash-lite")
        kwargs: dict = {
            "model": model,
            "temperature": temperature,
            "google_api_key": os.getenv("GEMINI_API_KEY"),
        }
        if max_tokens:
            kwargs["max_output_tokens"] = max_tokens
        return ChatGoogleGenerativeAI(**kwargs)

    if p == "groq":
        from langchain_groq import ChatGroq
        model = _resolve_model(p, ["GROQ_MODEL", "LLM_MODEL_NAME"], "llama3-8b-8192")
        kwargs = {
            "model": model,
            "temperature": temperature,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        return ChatGroq(**kwargs)

    if p == "openai":
        from langchain_openai import ChatOpenAI
        model = _resolve_model(p, ["OPENAI_MODEL", "LLM_MODEL_NAME"], "gpt-4o-mini")
        kwargs = {
            "model": model,
            "temperature": temperature,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        return ChatOpenAI(**kwargs)

    if p == "anthropic":
        from langchain_anthropic import ChatAnthropic
        model = _resolve_model(p, ["ANTHROPIC_MODEL", "LLM_MODEL_NAME"], "claude-sonnet-4-6")
        kwargs = {
            "model": model,
            "temperature": temperature,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        return ChatAnthropic(**kwargs)

    raise ValueError(f"지원하지 않는 LLM 제공자: {p}")


def get_default_llm() -> BaseChatModel:
    """싱글톤 기본 LLM 인스턴스 반환"""
    global _default_llm
    if _default_llm is None:
        try:
            _default_llm = get_llm()
        except Exception as e:
            logger.error(f"LLM 초기화 실패: {e}")
            raise
    return _default_llm


def reset_llm():
    """싱글톤 LLM 및 등록된 chain 싱글톤 모두 초기화"""
    global _default_llm
    _default_llm = None
    for cb in _reset_callbacks:
        try:
            cb()
        except Exception as e:
            logger.warning(f"chain reset 콜백 실패: {e}")


def get_available_providers() -> list:
    """사용 가능한 제공자 목록 반환"""
    available = []
    if os.getenv("GEMINI_API_KEY"):
        available.append("gemini")
    if os.getenv("GROQ_API_KEY"):
        available.append("groq")
    if os.getenv("OPENAI_API_KEY"):
        available.append("openai")
    if os.getenv("ANTHROPIC_API_KEY"):
        available.append("anthropic")
    return available
