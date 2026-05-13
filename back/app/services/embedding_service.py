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
        # 2026-05: text-embedding-004 / gemini-embedding-001 모두 v1beta API 에서 deprecated/404.
        # 현재 권장 모델: gemini-embedding-2-preview (langchain-google 공식 권장).
        # 모델 변경 시 ChromaDB 차원이 달라지므로 /app/chroma_db 비우고 재인덱싱 필요.
        _embeddings = GoogleGenerativeAIEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "gemini-embedding-2-preview"),
            google_api_key=os.getenv("GEMINI_API_KEY"),
        )
        logger.info("임베딩 모델 초기화 완료")
    return _embeddings
