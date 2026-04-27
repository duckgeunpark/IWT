"""
LangChain 기반 LLM 팩토리
환경 변수에 따라 적절한 LangChain ChatModel을 반환
"""

import os
import logging
from typing import Optional
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

_default_llm: Optional[BaseChatModel] = None


def get_llm(
    provider: str = None,
    temperature: float = 0.5,
    max_tokens: Optional[int] = None,
) -> BaseChatModel:
    """
    LangChain ChatModel 인스턴스 반환

    Args:
        provider: 제공자 이름 (None이면 LLM_PROVIDER 환경변수 사용)
        temperature: 창의성 (0.0~1.0)
        max_tokens: 최대 출력 토큰 수 (None이면 모델 기본값)

    Returns:
        BaseChatModel 인스턴스
    """
    p = (provider or os.getenv("LLM_PROVIDER", "gemini")).lower()

    if p == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        kwargs: dict = {
            "model": os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
            "temperature": temperature,
            "google_api_key": os.getenv("GEMINI_API_KEY"),
        }
        if max_tokens:
            kwargs["max_output_tokens"] = max_tokens
        return ChatGoogleGenerativeAI(**kwargs)

    if p == "groq":
        from langchain_groq import ChatGroq
        kwargs = {
            "model": os.getenv("GROQ_MODEL", "llama3-8b-8192"),
            "temperature": temperature,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        return ChatGroq(**kwargs)

    if p == "openai":
        from langchain_openai import ChatOpenAI
        kwargs = {
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            "temperature": temperature,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        return ChatOpenAI(**kwargs)

    if p == "anthropic":
        from langchain_anthropic import ChatAnthropic
        kwargs = {
            "model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
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
    """싱글톤 LLM 인스턴스 초기화 (테스트용)"""
    global _default_llm
    _default_llm = None


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
