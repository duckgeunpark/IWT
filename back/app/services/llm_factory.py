"""
LLM 서비스 팩토리
환경 변수에 따라 적절한 LLM 제공자를 선택하여 서비스 인스턴스를 생성
"""

import os
from typing import Optional
from .llm_base import LLMService, LLMProvider
from .providers.groq_provider import GroqProvider

# 추가 제공자들을 여기에 import
# from .providers.openai_provider import OpenAIProvider
# from .providers.anthropic_provider import AnthropicProvider


class LLMFactory:
    """LLM 서비스 팩토리"""
    
    @staticmethod
    def create_llm_service(provider_name: Optional[str] = None) -> LLMService:
        """
        LLM 서비스 인스턴스 생성
        
        Args:
            provider_name: 제공자 이름 (None이면 환경 변수에서 자동 선택)
            
        Returns:
            LLMService 인스턴스
        """
        if provider_name is None:
            provider_name = os.getenv('LLM_PROVIDER', 'groq').lower()
        
        try:
            provider = LLMFactory._create_provider(provider_name)
            return LLMService(provider)
        except Exception as e:
            print(f"LLM 서비스 생성 실패: {str(e)}")
            # 기본 제공자로 재시도
            try:
                provider = GroqProvider()
                return LLMService(provider)
            except Exception as fallback_error:
                print(f"기본 LLM 제공자도 실패: {str(fallback_error)}")
                raise
    
    @staticmethod
    def _create_provider(provider_name: str) -> LLMProvider:
        """
        LLM 제공자 인스턴스 생성
        
        Args:
            provider_name: 제공자 이름
            
        Returns:
            LLMProvider 인스턴스
        """
        if provider_name == 'groq':
            return GroqProvider()
        # elif provider_name == 'openai':
        #     return OpenAIProvider()
        # elif provider_name == 'anthropic':
        #     return AnthropicProvider()
        else:
            raise ValueError(f"지원하지 않는 LLM 제공자: {provider_name}")
    
    @staticmethod
    def get_available_providers() -> list:
        """사용 가능한 제공자 목록 반환"""
        return ['groq']  # 'openai', 'anthropic' 추가 가능


# 전역 LLM 서비스 인스턴스
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """
    전역 LLM 서비스 인스턴스 반환 (싱글톤 패턴)
    
    Returns:
        LLMService 인스턴스
    """
    global _llm_service
    if _llm_service is None:
        try:
            _llm_service = LLMFactory.create_llm_service()
        except Exception as e:
            print(f"LLM 서비스 초기화 실패: {str(e)}")
            # 더미 서비스 반환 (기능은 제한적이지만 앱이 크래시되지 않음)
            from .llm_base import LLMProvider
            
            class DummyProvider(LLMProvider):
                async def chat_completion(self, messages, temperature=0.1, max_tokens=500, **kwargs):
                    return '{"error": "LLM 서비스가 초기화되지 않았습니다."}'
                
                async def vision_completion(self, messages, temperature=0.1, max_tokens=500, **kwargs):
                    return '{"error": "LLM 서비스가 초기화되지 않았습니다."}'
            
            _llm_service = LLMService(DummyProvider())
    
    return _llm_service


def reset_llm_service():
    """전역 LLM 서비스 인스턴스 재설정"""
    global _llm_service
    _llm_service = None 