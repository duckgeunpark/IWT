"""
Groq LLM 제공자 구현
"""

import os
import groq
from typing import Dict, List, Optional, Any
import logging
from ..llm_base import LLMProvider

logger = logging.getLogger(__name__)


class GroqProvider(LLMProvider):
    """Groq LLM 제공자"""
    
    def __init__(self):
        self.client = groq.Groq(
            api_key=os.getenv('GROQ_API_KEY')
        )
        self.model = "llama3-8b-8192"  # Groq의 빠른 모델
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 500,
        **kwargs
    ) -> str:
        """Groq 채팅 완성 API 호출"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq API 호출 실패: {str(e)}")
            raise
    
    async def vision_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: int = 500,
        **kwargs
    ) -> str:
        """Groq 비전 완성 API 호출 (이미지 분석)"""
        try:
            # Groq는 현재 이미지 분석을 지원하지 않으므로 텍스트만 처리
            # 이미지 URL을 텍스트로 변환하여 처리
            text_messages = self._convert_vision_to_text(messages)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=text_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq Vision API 호출 실패: {str(e)}")
            raise
    
    def _convert_vision_to_text(self, messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """비전 메시지를 텍스트 메시지로 변환"""
        text_messages = []
        
        for message in messages:
            if message["role"] == "user":
                content = message["content"]
                if isinstance(content, list):
                    # 이미지가 포함된 메시지 처리
                    text_content = ""
                    for item in content:
                        if item["type"] == "text":
                            text_content += item["text"] + "\n"
                        elif item["type"] == "image_url":
                            text_content += f"이미지 URL: {item['image_url']['url']}\n"
                    
                    text_messages.append({
                        "role": "user",
                        "content": text_content.strip()
                    })
                else:
                    text_messages.append(message)
            else:
                text_messages.append(message)
        
        return text_messages 