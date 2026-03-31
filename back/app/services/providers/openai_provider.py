"""
OpenAI LLM 제공자
"""

import os
import logging
from typing import Dict, List, Any
from ..llm_base import LLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI API 제공자"""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")

        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        try:
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("openai 패키지가 설치되지 않았습니다. pip install openai")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 500,
        **kwargs
    ) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI chat completion 실패: {str(e)}")
            raise

    async def vision_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: int = 500,
        **kwargs
    ) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI vision completion 실패: {str(e)}")
            raise
