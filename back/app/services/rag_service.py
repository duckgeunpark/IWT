"""
RAG 서비스 (ChromaDB 기반 벡터 검색)

게시글 발행 시 자동 색인, 유사 여행 검색, 삭제 지원
"""

import logging
import os
from typing import Any, Dict, List, Optional

from langchain_community.vectorstores import Chroma

from app.services.embedding_service import get_embeddings

logger = logging.getLogger(__name__)

_CHROMA_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
_COLLECTION  = "travel_posts"

_vectorstore: Optional[Chroma] = None


def _get_vectorstore() -> Chroma:
    """ChromaDB 벡터스토어 싱글톤 반환"""
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = Chroma(
            collection_name=_COLLECTION,
            embedding_function=get_embeddings(),
            persist_directory=_CHROMA_PATH,
        )
        logger.info(f"ChromaDB 초기화 완료: {_CHROMA_PATH}")
    return _vectorstore


class RAGService:
    """RAG 서비스: 게시글 색인 / 유사 검색 / 삭제"""

    def index_post(self, post: Any, clusters: List[Any] = None) -> None:
        """
        게시글을 벡터 DB에 색인.
        게시글 발행(status=published) 시 호출.

        Args:
            post: Post DB 모델 인스턴스
            clusters: 관련 Cluster 인스턴스 목록 (선택)
        """
        try:
            vs = _get_vectorstore()

            # 색인 텍스트 조합 (제목 + 설명 + 클러스터 위치명)
            cluster_names = ""
            if clusters:
                cluster_names = " ".join(
                    c.location_name for c in clusters if c.location_name
                )

            doc_text = f"{post.title or ''}\n{post.description or ''}\n{cluster_names}".strip()
            if not doc_text:
                return

            import json as _json
            tags = []
            if post.tags:
                try:
                    tags = _json.loads(post.tags) if isinstance(post.tags, str) else post.tags
                except Exception:
                    pass

            metadata = {
                "post_id":   str(post.id),
                "title":     post.title or "",
                "tags":      ", ".join(tags) if tags else "",
                "status":    post.status or "",
                "user_id":   str(post.user_id) if post.user_id else "",
            }

            # 기존 문서 삭제 후 재색인 (upsert)
            self._delete_by_post_id(str(post.id))
            vs.add_texts(
                texts=[doc_text],
                metadatas=[metadata],
                ids=[f"post_{post.id}"],
            )
            logger.info(f"게시글 색인 완료: post_id={post.id}")
        except Exception as e:
            logger.error(f"게시글 색인 실패 (post_id={post.id}): {e}")

    async def search_similar(
        self,
        query: str,
        location: str = "",
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        유사한 여행 게시글 검색 (벡터 유사도 기반).

        Args:
            query: 검색 쿼리 (예: "제주도 힐링 여행")
            location: 위치 필터 (선택)
            k: 반환할 최대 결과 수

        Returns:
            [{"post_id", "title", "tags", "score"}, ...]
        """
        try:
            vs = _get_vectorstore()
            search_query = f"{query} {location}".strip()
            docs_with_scores = vs.similarity_search_with_score(search_query, k=k)

            results = []
            for doc, score in docs_with_scores:
                meta = doc.metadata
                results.append({
                    "post_id": meta.get("post_id"),
                    "title":   meta.get("title", ""),
                    "tags":    meta.get("tags", ""),
                    "score":   float(score),
                })
            return results
        except Exception as e:
            logger.error(f"유사 게시글 검색 실패: {e}")
            return []

    def delete_post(self, post_id: int) -> None:
        """게시글 삭제 시 벡터 DB에서도 제거"""
        try:
            self._delete_by_post_id(str(post_id))
            logger.info(f"벡터 DB 게시글 삭제: post_id={post_id}")
        except Exception as e:
            logger.error(f"벡터 DB 삭제 실패 (post_id={post_id}): {e}")

    def _delete_by_post_id(self, post_id: str) -> None:
        """post_id로 기존 벡터 삭제"""
        try:
            vs = _get_vectorstore()
            vs.delete(ids=[f"post_{post_id}"])
        except Exception:
            pass  # 존재하지 않으면 무시


# 서비스 싱글톤
rag_service = RAGService()
