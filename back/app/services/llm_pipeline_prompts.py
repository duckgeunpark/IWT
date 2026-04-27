"""
LLM 파이프라인 프롬프트 템플릿 (LangChain ChatPromptTemplate 기반)

BASE 구조는 고정, 아래 항목만 사용자 커스터마이즈 가능:
  - tone:  casual | formal | poetic | humorous
  - style: blog | diary | travel_guide
  - stage1_extra / stage2_extra / stage3_extra: 자유 텍스트 지침
  - lang:  ko | en | ja | zh | fr (제목 언어)
"""

from langchain_core.prompts import ChatPromptTemplate

# ── 커스터마이즈 가이드 ──────────────────────────────────────────────

TONE_GUIDE = {
    "casual":   "친근하고 편안한 말투로, 마치 친구에게 여행 이야기를 들려주듯",
    "formal":   "격식 있고 정중한 문어체로, 여행 잡지 기고문처럼",
    "poetic":   "감성적이고 시적인 표현을 풍부하게 사용하여",
    "humorous": "유머와 위트를 곁들여 재미있고 생동감 있게",
}

STYLE_GUIDE = {
    "blog":         "여행 블로그 포스트 형식으로",
    "diary":        "여행 일기 형식으로, 개인적인 감정과 순간들을 중심으로",
    "travel_guide": "여행 가이드 형식으로, 실용적인 정보와 추천을 포함하여",
}

LANG_TITLE_GUIDE = {
    "ko": "한국어로 제목 작성",
    "en": "영어로 제목 작성. 예: Spring in Tokyo — Cherry Blossom Journey",
    "ja": "일본어(한자+히라가나 혼용)로 제목 작성. 예: 東京の春、桜舞う旅",
    "zh": "중국어 번체로 제목 작성. 예: 東京春日·賞花之旅",
    "fr": "프랑스어로 제목 작성. 예: Voyage au Japon — Sous les cerisiers",
}

DEFAULT_PREFERENCES = {
    "tone": "casual",
    "style": "blog",
    "stage1_extra": None,
    "stage2_extra": None,
    "stage3_extra": None,
    "lang": "ko",
}


# ── Stage 1: 전체 일정 표 ──────────────────────────────────────────

STAGE1_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "당신은 여행 일정을 정리하는 전문가입니다. 마크다운 표만 출력합니다.",
    ),
    (
        "human",
        """다음 여행 일정을 바탕으로 전체 일정 표를 마크다운으로 작성해주세요.

여행 일정:
{days_text}

작성 규칙:
1. 반드시 아래 형식의 마크다운 표로만 출력 (다른 설명 없이)
2. "메모" 칸: 해당 날짜 여행의 핵심 분위기·특징을 10자 이내로 요약
3. {tone_text} 느낌의 메모
4. {style_text} 어울리는 표현{extra_line}

출력 (표만):
| 날짜 | 장소 | 메모 |
|------|------|------|
| 1일차 | 장소명 | 메모 |""",
    ),
])


def build_stage1_inputs(
    clusters_by_day: list,
    tone: str = "casual",
    style: str = "blog",
    extra: str = None,
) -> dict:
    """Stage 1 프롬프트 입력값 딕셔너리 반환"""
    day_lines = []
    for day_info in clusters_by_day:
        places = ", ".join(
            c.get("location_name", "알 수 없는 장소")
            for c in day_info["clusters"]
        )
        day_lines.append(f"- {day_info['day']}일차: {places}")

    return {
        "days_text": "\n".join(day_lines),
        "tone_text": TONE_GUIDE.get(tone, TONE_GUIDE["casual"]),
        "style_text": STYLE_GUIDE.get(style, STYLE_GUIDE["blog"]),
        "extra_line": f"\n추가 지침: {extra}" if extra else "",
    }


# ── Stage 2: 개별 장소 단락 ───────────────────────────────────────

STAGE2_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "당신은 여행 블로거입니다. 지정된 글자 수 범위의 단락만 출력합니다.",
    ),
    (
        "human",
        """다음 여행 장소에 대한 짧은 단락을 작성해주세요.

장소: {location_name} ({country})
방문 시간대: {visit_time}
촬영 사진 수: {photo_count}장

작성 규칙:
1. 150~250자 (헤딩 없이 본문만)
2. {tone_text} 문체
3. {style_text} 스타일
4. 장소의 분위기·특징·인상 위주로 묘사
5. 첫 문장 시작 방식 다양하게 (질문형·감탄형·묘사형·회상형 중 택1){extra_line}

본문만 출력, 다른 설명 없이.""",
    ),
])


def build_stage2_inputs(
    location_name: str,
    country: str,
    photo_count: int,
    visit_time: str,
    tone: str = "casual",
    style: str = "blog",
    extra: str = None,
) -> dict:
    """Stage 2 프롬프트 입력값 딕셔너리 반환"""
    return {
        "location_name": location_name,
        "country": country,
        "photo_count": photo_count,
        "visit_time": visit_time,
        "tone_text": TONE_GUIDE.get(tone, TONE_GUIDE["casual"]),
        "style_text": STYLE_GUIDE.get(style, STYLE_GUIDE["blog"]),
        "extra_line": f"\n추가 지침: {extra}" if extra else "",
    }


# ── Stage 3: 전체 합성 및 다듬기 ─────────────────────────────────

STAGE3_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        (
            "당신은 여행 블로그 에디터입니다. "
            "초안을 자연스럽게 다듬어 완성된 마크다운 포스트를 출력합니다. "
            "제목(# 으로 시작)은 반드시 한국어로만 작성합니다. "
            "방문 장소가 일본·중국·유럽 어디든 제목은 항상 한국어입니다. "
            "[PHOTO_숫자] 형태의 태그는 절대 수정·삭제하지 않습니다."
        ),
    ),
    (
        "human",
        """다음 여행 블로그 초안을 완성된 포스트로 다듬어주세요.

[장소별 초안]
{draft_body}

[방문 장소 목록]
{place_names_text}

작성 규칙:
1. 첫 줄: # 제목 — {lang_title}. 방문지가 일본·중국·유럽 등 외국이어도 제목은 반드시 한국어로만 작성. (25자 이내)
2. 제목 다음 줄부터 각 장소 섹션(## 시작) 순서대로 이어 붙이기
3. 문장 흐름·어색한 표현만 자연스럽게 다듬기 (구조 변경 금지)
4. [PHOTO_숫자] 태그는 절대 수정·삭제·이동 금지 (그대로 유지)
5. 섹션 간 자연스러운 연결 문구 1~2줄 추가 가능
6. {tone_text} 문체
7. {style_text} 스타일
8. 마지막 줄: <!-- tags: 태그1, 태그2, 태그3, 태그4, 태그5 -->
9. 표(| 로 시작하는 행)는 절대 작성하지 마세요. 일정표는 코드가 자동으로 삽입합니다.{extra_line}

완성된 마크다운 전체 출력, 다른 설명 없이.""",
    ),
])


def build_stage3_inputs(
    itinerary_table: str,
    draft_body: str,
    place_names: list,
    lang: str = "ko",
    tone: str = "casual",
    style: str = "blog",
    extra: str = None,
) -> dict:
    """Stage 3 프롬프트 입력값 딕셔너리 반환"""
    return {
        "draft_body": draft_body,
        "place_names_text": ", ".join(place_names),
        "lang_title": LANG_TITLE_GUIDE.get(lang, LANG_TITLE_GUIDE["ko"]),
        "tone_text": TONE_GUIDE.get(tone, TONE_GUIDE["casual"]),
        "style_text": STYLE_GUIDE.get(style, STYLE_GUIDE["blog"]),
        "extra_line": f"\n추가 지침: {extra}" if extra else "",
    }
