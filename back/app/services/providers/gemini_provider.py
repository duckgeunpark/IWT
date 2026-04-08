"""
Google Gemini LLM 제공자 구현
"""

import os
import google.generativeai as genai
from typing import Dict, List, Any
import logging
from ..llm_base import LLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini LLM 제공자"""

    def __init__(self):
        genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
        self.model_name = os.getenv('LLM_MODEL_NAME', 'gemini-3.1-flash-lite-preview')

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 500,
        **kwargs
    ) -> str:
        """Gemini 채팅 완성 API 호출"""
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
            )

            # system 메시지를 system_instruction으로 분리
            system_instruction = None
            chat_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system_instruction = msg["content"]
                elif msg["role"] == "user":
                    chat_messages.append({"role": "user", "parts": [msg["content"]]})
                elif msg["role"] == "assistant":
                    chat_messages.append({"role": "model", "parts": [msg["content"]]})

            if system_instruction:
                model = genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=system_instruction,
                    generation_config=genai.types.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    )
                )

            if len(chat_messages) > 1:
                chat = model.start_chat(history=chat_messages[:-1])
                response = chat.send_message(chat_messages[-1]["parts"][0])
            else:
                last_content = chat_messages[0]["parts"][0] if chat_messages else ""
                response = model.generate_content(last_content)

            return response.text
        except Exception as e:
            logger.error(f"Gemini API 호출 실패: {str(e)}")
            raise

    async def vision_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: int = 500,
        **kwargs
    ) -> str:
        """Gemini 비전 완성 API 호출 (이미지 분석)"""
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
            )

            parts = []
            system_instruction = None

            for msg in messages:
                if msg["role"] == "system":
                    system_instruction = msg["content"]
                elif msg["role"] == "user":
                    content = msg["content"]
                    if isinstance(content, list):
                        for item in content:
                            if item["type"] == "text":
                                parts.append(item["text"])
                            elif item["type"] == "image_url":
                                # Gemini는 URL 직접 지원 안 함 → 텍스트로 전달
                                parts.append(f"이미지 URL: {item['image_url']['url']}")
                    else:
                        parts.append(content)

            if system_instruction:
                model = genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=system_instruction,
                    generation_config=genai.types.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    )
                )

            response = model.generate_content(parts)
            return response.text
        except Exception as e:
            logger.error(f"Gemini Vision API 호출 실패: {str(e)}")
            raise
