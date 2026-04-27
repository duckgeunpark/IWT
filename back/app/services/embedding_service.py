"""
임베딩 서비스 (Google Gemini 임베딩 모델 기반)
텍스트 → 벡터 변환, ChromaDB와 연동
"""

import logging
import os
from typing import Optional

from langchain_google_genai import GoogleGenerativeAIEmbeddings

logger = logging.getLogger(__name__)

_embeddings: Optional[GoogleGenerativeAIEmbeddings] = None


def get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """임베딩 모델 싱글톤 반환"""
    global _embeddings
    if _embeddings is None:
        _embeddings = GoogleGenerativeAIEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "models/text-embedding-004"),
            google_api_key=os.getenv("GEMINI_API_KEY"),
        )
        logger.info("임베딩 모델 초기화 완료")
    return _embeddings
