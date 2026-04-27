"""
3단계 LLM 파이프라인 오케스트레이터 (LangChain LCEL 기반)

Stage 1 → 전체 일정 표 생성 (1개 LLM, temperature=0.2)
Stage 2 → 클러스터(장소)별 단락 생성 (N개 병렬, temperature=0.75, abatch)
Stage 3 → 전체 합성 및 다듬기 (1개 LLM, temperature=0.5)
"""

import hashlib
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.output_parsers import StrOutputParser

from app.services.llm_factory import get_llm
from app.services.llm_pipeline_prompts import (
    DEFAULT_PREFERENCES,
    STAGE1_PROMPT,
    STAGE2_PROMPT,
    STAGE3_PROMPT,
    build_stage1_inputs,
    build_stage2_inputs,
    build_stage3_inputs,
)

logger = logging.getLogger(__name__)

_STAGE2_CONCURRENCY = 10


# ── 유틸 함수 ────────────────────────────────────────────────────────

def cluster_fingerprint(cluster: Dict) -> str:
    """클러스터 사진 구성 → 12자리 MD5 지문 (Stage 2 캐시 키)"""
    file_keys = sorted(
        p.get("file_key", "") for p in cluster.get("photos", [cluster])
    )
    if not file_keys or file_keys == [""]:
        file_keys = [cluster.get("representative_photo_url", str(cluster.get("cluster_id", "")))]
    content = "|".join(file_keys)
    return hashlib.md5(content.encode()).hexdigest()[:12]


def _format_visit_time(start: Optional[str], end: Optional[str]) -> str:
    """ISO 시간 문자열 → 읽기 쉬운 방문 시간대 문자열"""
    fmts = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"]

    def parse(s: str) -> Optional[datetime]:
        if not s:
            return None
        for f in fmts:
            try:
                return datetime.strptime(s[:19], f[:19])
            except ValueError:
                continue
        return None

    def label(d: datetime) -> str:
        h = d.hour
        if h < 6:   return f"새벽 {d.strftime('%H:%M')}"
        if h < 12:  return f"오전 {d.strftime('%H:%M')}"
        if h < 14:  return f"점심 {d.strftime('%H:%M')}"
        if h < 18:  return f"오후 {d.strftime('%H:%M')}"
        return f"저녁 {d.strftime('%H:%M')}"

    s_dt = parse(start)
    e_dt = parse(end)
    if s_dt and e_dt:
        delta = int((e_dt - s_dt).total_seconds() / 60)
        dur = f"{delta // 60}시간 {delta % 60}분" if delta >= 60 else f"{delta}분"
        return f"{label(s_dt)} ~ {label(e_dt)} (약 {dur})"
    if s_dt:
        return label(s_dt)
    return "시간 정보 없음"


def _inject_table(markdown: str, itinerary_table: str) -> str:
    """Stage 3 출력에 일정 표 강제 삽입 (LLM 생성 표 제거 후 첫 ## 앞에 삽입)"""
    if not itinerary_table:
        return markdown

    lines = markdown.split("\n")
    cleaned: List[str] = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("|"):
            while i < len(lines) and lines[i].strip().startswith("|"):
                i += 1
        else:
            cleaned.append(lines[i])
            i += 1

    insert_at = len(cleaned)
    for idx, line in enumerate(cleaned):
        if line.startswith("##"):
            insert_at = idx
            break

    cleaned.insert(insert_at, "")
    cleaned.insert(insert_at + 1, itinerary_table)
    cleaned.insert(insert_at + 2, "")
    return "\n".join(cleaned)


def _parse_sections(markdown: str) -> List[Dict]:
    """H2(##) 기준으로 마크다운을 섹션 목록으로 파싱"""
    lines = markdown.split("\n")
    sections: List[Dict] = []
    current: Dict = {"heading": None, "lines": []}
    for line in lines:
        if line.startswith("## "):
            sections.append(current)
            current = {"heading": line[3:].strip(), "lines": []}
        else:
            current["lines"].append(line)
    sections.append(current)
    return sections


def _reassemble_sections(sections: List[Dict]) -> str:
    """섹션 목록을 마크다운 문자열로 재조합"""
    parts: List[str] = []
    for sec in sections:
        if sec["heading"] is not None:
            parts.append(f"## {sec['heading']}")
        parts.extend(sec["lines"])
    return "\n".join(parts)


def _merge_into_document(
    current_content: str,
    stage2_results: List[Dict],
    cache_hit_ids: set,
    itinerary_table: str,
) -> str:
    """사용자 편집 중인 문서에 Stage 2 결과 머지 (캐시 히트 섹션은 기존 유지)"""
    sections = _parse_sections(current_content)

    added_new: List[Dict] = []
    for r in stage2_results:
        if r["cluster_id"] in cache_hit_ids:
            continue

        heading = r["location_name"]
        new_lines: List[str] = []
        if r.get("photo_url"):
            new_lines.append(f"![{heading}]({r['photo_url']})")
        new_lines.append("")
        new_lines.append(r["paragraph"])

        matched = False
        for sec in sections:
            if sec["heading"] and sec["heading"].strip() == heading.strip():
                sec["lines"] = new_lines
                matched = True
                break
        if not matched:
            added_new.append({"heading": heading, "lines": new_lines})

    sections.extend(added_new)

    if itinerary_table and sections and sections[0]["heading"] is None:
        intro = sections[0]["lines"]
        clean_intro: List[str] = []
        i = 0
        while i < len(intro):
            if intro[i].strip().startswith("|"):
                while i < len(intro) and intro[i].strip().startswith("|"):
                    i += 1
            else:
                clean_intro.append(intro[i])
                i += 1
        insert_pos = len(clean_intro)
        for j, line in enumerate(clean_intro):
            if line.startswith("#") and not line.startswith("##"):
                insert_pos = j + 1
                break
        clean_intro.insert(insert_pos, "")
        clean_intro.insert(insert_pos + 1, itinerary_table)
        clean_intro.insert(insert_pos + 2, "")
        sections[0]["lines"] = clean_intro

    return _reassemble_sections(sections)


def _extract_tags_from_markdown(markdown: str) -> List[str]:
    """<!-- tags: tag1, tag2 --> 주석에서 태그 추출"""
    match = re.search(r"<!--\s*tags:\s*(.+?)\s*-->", markdown)
    if not match:
        return []
    return [t.strip() for t in match.group(1).split(",") if t.strip()]


def _extract_title_from_markdown(markdown: str) -> str:
    """첫 번째 # 제목 추출"""
    match = re.search(r"^#\s+(.+)", markdown, re.MULTILINE)
    return match.group(1).strip() if match else "여행 기록"


def _group_clusters_by_day(clusters: List[Dict]) -> List[Dict]:
    """클러스터 리스트를 일차별로 그룹핑"""
    day_map: Dict[int, List[Dict]] = {}
    for c in clusters:
        day = c.get("day", 1)
        day_map.setdefault(day, []).append(c)
    return [
        {"day": day, "clusters": day_map[day]}
        for day in sorted(day_map.keys())
    ]


# ── LCEL 파이프라인 ──────────────────────────────────────────────────

class LLMPipeline:
    """3단계 LLM 파이프라인 (LCEL 기반)"""

    def __init__(self):
        provider = os.getenv("LLM_PROVIDER", "gemini")
        parser = StrOutputParser()

        # Stage별 온도와 토큰 제한이 다르므로 각각 별도 모델 생성
        llm1 = get_llm(provider, temperature=0.2, max_tokens=400)
        llm2 = get_llm(provider, temperature=0.75, max_tokens=300)
        llm3 = get_llm(provider, temperature=0.5, max_tokens=4096)

        self.stage1_chain = STAGE1_PROMPT | llm1 | parser
        self.stage2_chain = STAGE2_PROMPT | llm2 | parser
        self.stage3_chain = STAGE3_PROMPT | llm3 | parser

    # ── Stage 1 ─────────────────────────────────────────────────────

    async def _run_stage1(self, clusters_by_day: List[Dict], prefs: Dict) -> str:
        """전체 일정 표 생성 → 마크다운 표 문자열 반환"""
        inputs = build_stage1_inputs(
            clusters_by_day=clusters_by_day,
            tone=prefs["tone"],
            style=prefs["style"],
            extra=prefs.get("stage1_extra"),
        )
        try:
            return (await self.stage1_chain.ainvoke(inputs)).strip()
        except Exception as e:
            logger.error(f"Stage1 실패: {e}")
            rows = "\n".join(
                f"| {d['day']}일차 | "
                + ", ".join(c.get("location_name", "-") for c in d["clusters"])
                + " | - |"
                for d in clusters_by_day
            )
            return f"| 날짜 | 장소 | 메모 |\n|------|------|------|\n{rows}"

    # ── Stage 2 ─────────────────────────────────────────────────────

    async def _run_stage2(self, clusters: List[Dict], prefs: Dict) -> List[Dict]:
        """모든 클러스터 병렬 처리 (abatch, max_concurrency=10)"""
        batch_inputs = []
        for cluster in clusters:
            loc_info = cluster.get("location_info", {})
            inputs = build_stage2_inputs(
                location_name=cluster.get("location_name", "알 수 없는 장소"),
                country=loc_info.get("country", ""),
                photo_count=cluster.get("photo_count", 0),
                visit_time=_format_visit_time(
                    cluster.get("start_time"), cluster.get("end_time")
                ),
                tone=prefs["tone"],
                style=prefs["style"],
                extra=prefs.get("stage2_extra"),
            )
            batch_inputs.append(inputs)

        try:
            paragraphs = await self.stage2_chain.abatch(
                batch_inputs,
                config={"max_concurrency": _STAGE2_CONCURRENCY},
                return_exceptions=True,
            )
        except Exception as e:
            logger.error(f"Stage2 abatch 실패: {e}")
            paragraphs = [Exception(str(e))] * len(clusters)

        output = []
        for i, (cluster, result) in enumerate(zip(clusters, paragraphs)):
            location_name = cluster.get("location_name", "알 수 없는 장소")
            if isinstance(result, Exception):
                logger.warning(f"Stage2 cluster[{i}] 실패: {result}")
                paragraph = f"{location_name}에서의 소중한 시간을 사진에 담았습니다."
            else:
                paragraph = result.strip()

            output.append({
                "cluster_id": cluster.get("cluster_id"),
                "day": cluster.get("day"),
                "location_name": location_name,
                "photo_url": cluster.get("representative_photo_url", ""),
                "paragraph": paragraph,
            })
        return output

    # ── 초안 조립 ────────────────────────────────────────────────────

    def _assemble_draft(self, stage2_results: List[Dict]) -> Tuple[str, Dict[str, str]]:
        """Stage 2 결과를 마크다운 초안으로 조립 (S3 URL → [PHOTO_n] 플레이스홀더)"""
        sections = []
        photo_map: Dict[str, str] = {}

        for i, item in enumerate(stage2_results):
            heading = f"## {item['location_name']}"
            placeholder = f"[PHOTO_{i}]"
            if item.get("photo_url"):
                photo_map[placeholder] = f"![{item['location_name']}]({item['photo_url']})"
                parts = [heading, placeholder, item["paragraph"]]
            else:
                parts = [heading, item["paragraph"]]
            sections.append("\n".join(parts))

        return "\n\n".join(sections), photo_map

    @staticmethod
    def _inject_photos(markdown: str, photo_map: Dict[str, str]) -> str:
        """[PHOTO_n] 플레이스홀더 → 실제 이미지 마크다운으로 교체"""
        for placeholder, img_md in photo_map.items():
            markdown = markdown.replace(placeholder, img_md)
        return markdown

    # ── Stage 3 ─────────────────────────────────────────────────────

    async def _run_stage3(
        self,
        itinerary_table: str,
        draft_body: str,
        place_names: List[str],
        prefs: Dict,
    ) -> str:
        """초안 → 완성 마크다운"""
        inputs = build_stage3_inputs(
            itinerary_table=itinerary_table,
            draft_body=draft_body,
            place_names=place_names,
            lang=prefs.get("lang", "ko"),
            tone=prefs["tone"],
            style=prefs["style"],
            extra=prefs.get("stage3_extra"),
        )
        try:
            return (await self.stage3_chain.ainvoke(inputs)).strip()
        except Exception as e:
            logger.error(f"Stage3 실패: {e}")
            return f"# 여행 기록\n\n{itinerary_table}\n\n{draft_body}"

    # ── 메인 엔트리 ──────────────────────────────────────────────────

    async def run(
        self,
        clusters: List[Dict],
        preferences: Optional[Dict] = None,
        on_progress=None,
    ) -> Dict[str, Any]:
        """
        파이프라인 전체 실행 (신규 게시글)

        Returns:
            {markdown, title, tags, itinerary_table, stage2_cache}
        """
        prefs = {**DEFAULT_PREFERENCES, **(preferences or {})}

        if not clusters:
            return {
                "markdown": "# 여행 기록\n\n여행 사진을 업로드했습니다.",
                "title": "여행 기록",
                "tags": ["여행"],
                "itinerary_table": "",
                "stage2_cache": {},
            }

        clusters_by_day = _group_clusters_by_day(clusters)

        logger.info("Pipeline Stage1 시작")
        if on_progress:
            await on_progress("stage1", 48, "일정 표 생성 중...")
        itinerary_table = await self._run_stage1(clusters_by_day, prefs)

        logger.info(f"Pipeline Stage2 시작 — 총 {len(clusters)}개 클러스터")
        if on_progress:
            await on_progress("stage2", 68, f"장소별 글 작성 중... ({len(clusters)}곳)")
        stage2_results = await self._run_stage2(clusters, prefs)
        stage2_results.sort(key=lambda x: (x.get("day", 0), x.get("cluster_id", 0)))

        draft_body, photo_map = self._assemble_draft(stage2_results)
        place_names = [r["location_name"] for r in stage2_results]

        logger.info("Pipeline Stage3 시작")
        if on_progress:
            await on_progress("stage3", 84, "게시글 완성 중...")
        final_markdown = await self._run_stage3(itinerary_table, draft_body, place_names, prefs)

        final_markdown = _inject_table(final_markdown, itinerary_table)
        final_markdown = self._inject_photos(final_markdown, photo_map)

        stage2_cache = {
            cluster_fingerprint(clusters[i]): {
                "location_name": r["location_name"],
                "paragraph": r["paragraph"],
                "photo_url": r["photo_url"],
            }
            for i, r in enumerate(stage2_results)
        }

        return {
            "markdown": final_markdown,
            "title": _extract_title_from_markdown(final_markdown),
            "tags": _extract_tags_from_markdown(final_markdown),
            "itinerary_table": itinerary_table,
            "stage2_cache": stage2_cache,
        }

    async def run_incremental(
        self,
        clusters: List[Dict],
        stage2_cache: Dict[str, Dict],
        preferences: Optional[Dict] = None,
        skip_stage3: bool = False,
    ) -> Dict[str, Any]:
        """
        증분 업데이트 파이프라인 (사진 추가/변경 시)

        Stage 2: 지문 캐시 히트 → 재사용, 미스 → 새로 호출
        Stage 1/3: 항상 재실행
        """
        prefs = {**DEFAULT_PREFERENCES, **(preferences or {})}

        if not clusters:
            return {
                "markdown": "# 여행 기록\n\n여행 사진을 업로드했습니다.",
                "title": "여행 기록",
                "tags": ["여행"],
                "itinerary_table": "",
                "stage2_cache": {},
                "cache_stats": {"hit": 0, "miss": 0, "removed": 0},
            }

        clusters_by_day = _group_clusters_by_day(clusters)

        logger.info("Incremental Stage1 시작")
        itinerary_table = await self._run_stage1(clusters_by_day, prefs)

        # Stage 2: 지문 기반 캐시 히트/미스 판단
        fingerprints = [cluster_fingerprint(c) for c in clusters]
        hits: List[Tuple[int, Dict]] = []
        miss_indices: List[int] = []

        for i, fp in enumerate(fingerprints):
            if fp in stage2_cache:
                cached = stage2_cache[fp]
                hits.append((i, {
                    "cluster_id":    clusters[i].get("cluster_id"),
                    "day":           clusters[i].get("day"),
                    "location_name": cached["location_name"],
                    "photo_url":     clusters[i].get("representative_photo_url", cached.get("photo_url", "")),
                    "paragraph":     cached["paragraph"],
                }))
            else:
                miss_indices.append(i)

        cache_hit  = len(hits)
        cache_miss = len(miss_indices)
        removed    = len(stage2_cache) - cache_hit
        logger.info(f"Stage2 캐시 — hit:{cache_hit} miss:{cache_miss} removed:{removed}")

        miss_results: Dict[int, Dict] = {}
        if miss_indices:
            miss_clusters = [clusters[i] for i in miss_indices]
            miss_stage2 = await self._run_stage2(miss_clusters, prefs)
            for orig_idx, result in zip(miss_indices, miss_stage2):
                miss_results[orig_idx] = result

        hit_map = {i: r for i, r in hits}
        stage2_results = [
            hit_map[i] if i in hit_map else miss_results[i]
            for i in range(len(clusters))
        ]
        stage2_results.sort(key=lambda x: (x.get("day", 0), x.get("cluster_id", 0)))

        new_cache = {fp: stage2_cache[fp] for fp in fingerprints if fp in stage2_cache}
        for i in miss_indices:
            fp = fingerprints[i]
            r  = miss_results[i]
            new_cache[fp] = {
                "location_name": r["location_name"],
                "paragraph":     r["paragraph"],
                "photo_url":     r["photo_url"],
            }

        if skip_stage3:
            cache_hit_ids = {r["cluster_id"] for _, r in hits}
            return {
                "markdown":        None,
                "title":           None,
                "tags":            [],
                "itinerary_table": itinerary_table,
                "stage2_results":  stage2_results,
                "cache_hit_ids":   cache_hit_ids,
                "stage2_cache":    new_cache,
                "cache_stats": {
                    "hit": cache_hit, "miss": cache_miss,
                    "removed": removed,
                    "new_sections": len([
                        r for r in stage2_results
                        if r["cluster_id"] not in cache_hit_ids
                    ]),
                },
            }

        logger.info("Incremental Stage3 시작")
        draft_body, photo_map = self._assemble_draft(stage2_results)
        place_names = [r["location_name"] for r in stage2_results]
        final_markdown = await self._run_stage3(itinerary_table, draft_body, place_names, prefs)

        final_markdown = _inject_table(final_markdown, itinerary_table)
        final_markdown = self._inject_photos(final_markdown, photo_map)

        return {
            "markdown":        final_markdown,
            "title":           _extract_title_from_markdown(final_markdown),
            "tags":            _extract_tags_from_markdown(final_markdown),
            "itinerary_table": itinerary_table,
            "stage2_cache":    new_cache,
            "cache_stats":     {"hit": cache_hit, "miss": cache_miss, "removed": removed},
        }


# 싱글톤
_pipeline: Optional[LLMPipeline] = None


def get_llm_pipeline() -> LLMPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = LLMPipeline()
    return _pipeline
