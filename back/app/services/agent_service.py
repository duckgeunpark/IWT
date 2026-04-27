"""
LangChain Agent 서비스

route_planning_agent: 목적지 입력 → 경로·명소 추천 (계획 모드 백엔드)
"""

import json
import logging
import os
from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

from app.services.llm_factory import get_llm, register_reset_callback

logger = logging.getLogger(__name__)


# ── Tool 정의 ────────────────────────────────────────────────────────

@tool
async def search_attractions(location: str, categories: str = "전반적인 관광") -> str:
    """특정 위치의 여행 명소를 검색합니다.

    Args:
        location: 검색할 위치 (예: 제주도, 도쿄 신주쿠)
        categories: 검색 카테고리 (예: 음식, 자연, 문화)
    """
    from app.services.llm_route_recommend import llm_route_service
    attractions = await llm_route_service.recommend_attractions(
        location_info={"name": location},
        categories=categories.split(",") if categories else None,
        max_attractions=5,
    )
    return json.dumps(attractions, ensure_ascii=False)


@tool
async def search_similar_trips(query: str, location: str = "") -> str:
    """커뮤니티에 올라온 유사한 여행 게시글을 검색합니다.

    Args:
        query: 검색 쿼리 (예: 제주도 힐링 여행)
        location: 위치 필터 (선택사항)
    """
    try:
        from app.services.rag_service import rag_service
        results = await rag_service.search_similar(query=query, location=location, k=3)
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"RAG 검색 실패 (폴백): {e}")
        return json.dumps([], ensure_ascii=False)


@tool
async def get_popular_places(city: str) -> str:
    """특정 도시의 인기 장소 목록을 조회합니다.

    Args:
        city: 도시명 (예: 서울, 부산, 제주)
    """
    try:
        from app.core.database import SessionLocal
        from app.models.db_models import Place
        db = SessionLocal()
        try:
            places = (
                db.query(Place)
                .filter(Place.city == city)
                .order_by(Place.visit_count.desc())
                .limit(5)
                .all()
            )
            result = [
                {"name": p.name, "place_type": p.place_type, "visit_count": p.visit_count}
                for p in places
            ]
            return json.dumps(result, ensure_ascii=False)
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"인기 장소 조회 실패: {e}")
        return json.dumps([], ensure_ascii=False)


@tool
async def generate_route_itinerary(
    destination: str,
    duration: str = "",
    styles: str = "",
    attractions: str = "",
) -> str:
    """여행 경로와 일정을 상세하게 작성합니다.

    Args:
        destination: 목적지
        duration: 여행 기간 (예: 2박 3일)
        styles: 여행 스타일 (예: 힐링, 맛집)
        attractions: 포함할 명소 목록 (JSON 문자열)
    """
    from app.services.llm_route_recommend import llm_route_service
    prompt_text = f"""다음 여행 정보를 바탕으로 상세한 여행 경로와 일정을 마크다운으로 작성해주세요.

목적지: {destination}
기간: {duration or "미정"}
여행 스타일: {styles or "자유"}
추천 명소: {attractions or "없음"}

작성 규칙:
1. 첫 줄: # 제목 (목적지와 여행 특징 포함, 25자 이내)
2. 일차별 ## 소제목 (예: ## 1일차 — 도착 및 시내 탐방)
3. 각 일차별 방문 장소, 이동 수단, 예상 소요 시간 포함
4. 실용적인 팁과 추천 식당/카페 포함
5. 감성적이고 친근한 한국어 블로그 문체
6. 마지막 줄: <!-- tags: 태그1, 태그2, 태그3 -->"""

    result = await llm_route_service.generate_travel_itinerary({"prompt": prompt_text})
    return result


# ── Agent 구성 ────────────────────────────────────────────────────────

_ROUTE_AGENT_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """당신은 친절한 여행 플래너 AI입니다.
사용자가 원하는 여행 경로를 만들어주기 위해 도구를 활용하여 정보를 수집하고 최적의 여행 계획을 제안합니다.

작업 순서:
1. 목적지의 인기 장소 조회
2. 여행 스타일에 맞는 명소 검색
3. 유사한 커뮤니티 여행 사례 검색 (참고용)
4. 수집한 정보를 바탕으로 상세 여행 일정 생성

항상 한국어로 응답하고, 실용적이면서 감성적인 여행 계획을 제안하세요.""",
    ),
    MessagesPlaceholder(variable_name="chat_history", optional=True),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

_AGENT_TOOLS = [search_attractions, search_similar_trips, get_popular_places, generate_route_itinerary]


def _build_agent_executor() -> AgentExecutor:
    llm = get_llm(temperature=0.3)
    agent = create_tool_calling_agent(llm, _AGENT_TOOLS, _ROUTE_AGENT_PROMPT)
    return AgentExecutor(
        agent=agent,
        tools=_AGENT_TOOLS,
        verbose=True,
        max_iterations=6,
        return_intermediate_steps=True,
    )


_agent_executor: Optional[AgentExecutor] = None


def get_route_agent() -> AgentExecutor:
    """경로 계획 Agent 싱글톤 반환"""
    global _agent_executor
    if _agent_executor is None:
        _agent_executor = _build_agent_executor()
    return _agent_executor


def _reset_agent():
    global _agent_executor
    _agent_executor = None


register_reset_callback(_reset_agent)


# ── Agent 실행 (SSE 스트리밍) ────────────────────────────────────────

async def plan_route_stream(
    destination: str,
    styles: List[str] = None,
    duration: str = "",
    companions: str = "",
) -> AsyncGenerator[str, None]:
    """
    경로 계획 Agent를 SSE 스트림으로 실행.

    yield: "data: {json}\n\n" 형식의 SSE 이벤트 문자열
    """
    import asyncio

    style_text = ", ".join(styles) if styles else "자유"
    query = f"""목적지: {destination}
여행 기간: {duration or "미정"}
여행 스타일: {style_text}
동행: {companions or "미정"}

위 정보를 바탕으로 최적의 여행 계획을 세워주세요."""

    def _sse(step: str, progress: int, message: str, **extra) -> str:
        data = {"step": step, "progress": progress, "message": message, **extra}
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    try:
        yield _sse("start", 5, "여행 계획을 시작합니다...")

        executor = get_route_agent()
        result: Dict[str, Any] = {}

        # Agent는 동기/비동기 혼용이라 별도 태스크로 실행
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: executor.invoke({"input": query}),
        )

        itinerary = result.get("output", "")
        yield _sse("done", 100, "여행 계획이 완성됐습니다!", itinerary=itinerary)

    except Exception as e:
        logger.error(f"Agent 실행 실패: {e}")
        yield _sse("error", 0, str(e))
