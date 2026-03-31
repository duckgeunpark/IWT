"""
Anthropic (Claude) LLM 제공자
"""

import os
import logging
from typing import Dict, List, Any
from ..llm_base import LLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API 제공자"""

    def __init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY 환경변수가 설정되지 않았습니다.")

        self.model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

        try:
            from anthropic import AsyncAnthropic
            self.client = AsyncAnthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic 패키지가 설치되지 않았습니다. pip install anthropic")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 500,
        **kwargs
    ) -> str:
        try:
            # system 메시지 분리
            system_msg = ""
            user_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    user_messages.append(msg)

            response = await self.client.messages.create(
                model=self.model,
                system=system_msg,
                messages=user_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic chat completion 실패: {str(e)}")
            raise

    async def vision_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: int = 500,
        **kwargs
    ) -> str:
        try:
            system_msg = ""
            user_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    user_messages.append(msg)

            response = await self.client.messages.create(
                model=self.model,
                system=system_msg,
                messages=user_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic vision completion 실패: {str(e)}")
            raise
