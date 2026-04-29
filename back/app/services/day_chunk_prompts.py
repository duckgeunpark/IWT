"""
일차 통합 LLM 호출용 프롬프트.

기존 PlaceNote → block_generator 2단계 호출을 1단계로 통합.
한 번의 LLM 호출로 일차 내 모든 장소의 메타(category·mood·depth) + 본문(paragraph)을 동시 생성.
"""

from langchain_core.prompts import ChatPromptTemplate


# ── 일차 통합 프롬프트 ──────────────────────────────────────────────
#
# 입력:
#   day_index, day_total, places_json (장소 목록 JSON 문자열),
#   tone, style
# 출력 (JSON):
#   {
#     "places": [
#       {
#         "order": int,                  # 입력 order 그대로
#         "category": str,               # landmark|cafe|nature|restaurant|street|beach|market|transport|etc
#         "depth": "main" | "brief",
#         "mood_keywords": [str, ...],
#         "highlight_scene": str,
#         "paragraph": str               # depth=main: 150~250자, depth=brief: 40~80자
#       }
#     ],
#     "tag_candidates": [str, ...]       # 이 날 추천 태그 2~3개
#   }

DAY_CHUNK_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "당신은 여행 블로그 에디터입니다. 한국어로 현장감 있는 여행 글을 씁니다. "
        "한 일차의 장소들을 동시에 보고 시간 흐름이 자연스럽게 이어지는 본문을 만듭니다. "
        "출력은 반드시 유효한 JSON만, 다른 설명 없이.",
    ),
    (
        "human",
        """다음은 여행 {day_index}일차({day_total}일 중)의 장소 목록입니다.
시간순으로 방문한 순서이며, 모든 장소의 본문을 한 번에 작성해주세요.

[장소 목록]
{places_json}

[작성 규칙]
1. 각 장소마다 아래 항목을 결정·작성:
   - category: landmark|cafe|nature|restaurant|street|beach|market|transport|etc 중 하나
   - depth: 사진 5장 이상이고 체류 30분 이상이며 의미 있는 장소면 "main", 그 외 "brief"
   - mood_keywords: 분위기 키워드 2~3개 (예: ["한적한", "골목길"])
   - highlight_scene: 이 장소에서 가장 인상적인 장면 한 줄
   - paragraph:
       depth=main이면 150~250자, depth=brief이면 40~80자
       헤딩·번호·따옴표 없이 본문만
       현재 장소의 분위기·특징을 생생하게 묘사 (실제 여행자 시점)
       다음 장소가 있다면 마지막에 "{transport_hint}" 같은 자연스러운 이동 연결 문장 1줄 포함 (강제 아님)

2. 톤·스타일:
   - tone: {tone}
   - style: {style}
   - 일차 전체의 흐름이 한 사람의 시점으로 자연스럽게 이어지도록

3. tag_candidates: 이 날 여정 전체를 대표할 태그 2~3개 (예: ["부산여행", "해변산책"])

[출력 JSON 스키마 — 정확히 이 형식만]
{{
  "places": [
    {{
      "order": 1,
      "category": "landmark",
      "depth": "main",
      "mood_keywords": ["한적한", "바다"],
      "highlight_scene": "...",
      "paragraph": "..."
    }}
  ],
  "tag_candidates": ["...", "..."]
}}

JSON만 출력. 다른 설명·주석 없이.""",
    ),
])


# ── Title + Intro 통합 프롬프트 ──────────────────────────────────────
#
# 입력: total_days, main_places_str, trip_summary, tone, style
# 출력 (JSON): {"title": str, "intro": str}

TITLE_INTRO_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "당신은 여행 블로그 에디터입니다. 한국어로 매력적인 제목과 도입부를 씁니다. "
        "출력은 반드시 유효한 JSON만, 다른 설명 없이.",
    ),
    (
        "human",
        """다음 여행 정보로 게시글의 제목과 도입부를 한 번에 작성해주세요.

[여행 개요]
총 {total_days}일 여행
주요 방문 장소: {main_places_str}
{trip_summary}

[작성 규칙]
- title: 25자 이내, 방문 지역 + 여행 특징, 감성적·매력적
- intro: 2~3문장, 여행 전체 분위기를 압축적, 독자가 읽고 싶어지도록
- tone: {tone}, style: {style}

[출력 JSON]
{{
  "title": "...",
  "intro": "..."
}}

JSON만 출력. 다른 설명 없이.""",
    ),
])


# ── 청크 분할 임계치 ────────────────────────────────────────────────

CHUNK_MAX_PLACES = 8        # 한 청크에 들어갈 최대 장소 수
CHUNK_TARGET_PLACES = 6     # 분할 시 목표 청크 크기
