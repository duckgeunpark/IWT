"""
3단계 LLM 파이프라인 오케스트레이터

Stage 1 → 전체 일정 표 생성 (1개 LLM)
Stage 2 → 클러스터(장소)별 단락 생성 (N개 병렬, 최대 동시 10개)
Stage 3 → 전체 합성 및 다듬기 (1개 LLM)

입력 cluster 형식:
  {
    "cluster_id": int,
    "day": int,                        # 1일차, 2일차 ...
    "location_name": str,              # Nominatim 역지오코딩 결과
    "location_info": {                 # 상세 위치 정보
        "country": str,
        "city": str,
        "address": str,
    },
    "representative_photo_url": str,   # S3 presigned URL (대표 사진)
    "photo_count": int,
    "start_time": str | None,          # ISO datetime
    "end_time": str | None,
  }
"""

import asyncio
import hashlib
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.services.llm_factory import get_llm_service
from app.services.llm_pipeline_prompts import (
    DEFAULT_PREFERENCES,
    build_stage1_prompt,
    build_stage2_prompt,
    build_stage3_prompt,
)

logger = logging.getLogger(__name__)

# Stage 2 최대 동시 LLM 호출 수
_STAGE2_CONCURRENCY = 10


def cluster_fingerprint(cluster: Dict) -> str:
    """
    클러스터의 사진 file_keys를 정렬·해시하여 12자리 지문 반환.
    같은 사진 구성이면 항상 동일한 지문 → Stage 2 캐시 키로 사용.
    """
    file_keys = sorted(
        p.get("file_key", "") for p in cluster.get("photos", [cluster])
    )
    # photos 키가 없을 때(pipeline_cluster 형태)는 representative_photo_url로 대체
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


class LLMPipeline:
    """3단계 LLM 파이프라인"""

    def __init__(self):
        self.llm = get_llm_service()

    # ── Stage 1 ─────────────────────────────────────────────────────

    async def _run_stage1(
        self,
        clusters_by_day: List[Dict],
        prefs: Dict,
    ) -> str:
        """전체 일정 표 생성 → 마크다운 표 문자열 반환"""
        prompt = build_stage1_prompt(
            clusters_by_day=clusters_by_day,
            tone=prefs["tone"],
            style=prefs["style"],
            extra=prefs.get("stage1_extra"),
        )
        try:
            result = await self.llm.provider.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 여행 일정을 정리하는 전문가입니다. 마크다운 표만 출력합니다.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=400,
            )
            return result.strip()
        except Exception as e:
            logger.error(f"Stage1 실패: {e}")
            # 폴백: 기본 표 구성
            rows = "\n".join(
                f"| {d['day']}일차 | "
                + ", ".join(c.get("location_name", "-") for c in d["clusters"])
                + " | - |"
                for d in clusters_by_day
            )
            return f"| 날짜 | 장소 | 메모 |\n|------|------|------|\n{rows}"

    # ── Stage 2 ─────────────────────────────────────────────────────

    async def _run_stage2_one(
        self,
        cluster: Dict,
        prefs: Dict,
        semaphore: asyncio.Semaphore,
    ) -> Dict:
        """클러스터 하나 → 단락 텍스트 반환"""
        async with semaphore:
            location_name = cluster.get("location_name", "알 수 없는 장소")
            loc_info = cluster.get("location_info", {})
            country = loc_info.get("country", "")
            visit_time = _format_visit_time(
                cluster.get("start_time"), cluster.get("end_time")
            )
            prompt = build_stage2_prompt(
                location_name=location_name,
                country=country,
                photo_count=cluster.get("photo_count", 0),
                visit_time=visit_time,
                tone=prefs["tone"],
                style=prefs["style"],
                extra=prefs.get("stage2_extra"),
            )
            try:
                paragraph = await self.llm.provider.chat_completion(
                    messages=[
                        {
                            "role": "system",
                            "content": "당신은 여행 블로거입니다. 지정된 글자 수 범위의 단락만 출력합니다.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.75,
                    max_tokens=300,
                )
                paragraph = paragraph.strip()
            except Exception as e:
                logger.warning(f"Stage2 클러스터 {cluster.get('cluster_id')} 실패: {e}")
                paragraph = f"{location_name}에서의 소중한 시간을 사진에 담았습니다."

            return {
                "cluster_id": cluster.get("cluster_id"),
                "day": cluster.get("day"),
                "location_name": location_name,
                "photo_url": cluster.get("representative_photo_url", ""),
                "paragraph": paragraph,
            }

    async def _run_stage2(
        self,
        clusters: List[Dict],
        prefs: Dict,
    ) -> List[Dict]:
        """모든 클러스터 병렬 처리 (최대 동시 10개)"""
        semaphore = asyncio.Semaphore(_STAGE2_CONCURRENCY)
        tasks = [
            self._run_stage2_one(cluster, prefs, semaphore)
            for cluster in clusters
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 예외 처리: 실패한 항목은 기본 단락으로 대체
        output = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.error(f"Stage2 gather 예외 cluster[{i}]: {res}")
                c = clusters[i]
                output.append({
                    "cluster_id": c.get("cluster_id"),
                    "day": c.get("day"),
                    "location_name": c.get("location_name", "알 수 없는 장소"),
                    "photo_url": c.get("representative_photo_url", ""),
                    "paragraph": "이 장소에서의 여행을 사진으로 담았습니다.",
                })
            else:
                output.append(res)
        return output

    # ── 중간 조립 ────────────────────────────────────────────────────

    def _assemble_draft(
        self,
        itinerary_table: str,
        stage2_results: List[Dict],
    ) -> str:
        """
        Stage 2 결과를 마크다운 초안으로 조립.
        ## 장소명
        ![location_name](photo_url)
        단락
        """
        sections = []
        for item in stage2_results:
            heading = f"## {item['location_name']}"
            photo_md = (
                f"![{item['location_name']}]({item['photo_url']})"
                if item.get("photo_url")
                else ""
            )
            parts = [heading]
            if photo_md:
                parts.append(photo_md)
            parts.append(item["paragraph"])
            sections.append("\n".join(parts))

        return "\n\n".join(sections)

    # ── Stage 3 ─────────────────────────────────────────────────────

    async def _run_stage3(
        self,
        itinerary_table: str,
        draft_body: str,
        place_names: List[str],
        prefs: Dict,
    ) -> str:
        """초안 → 완성 마크다운"""
        prompt = build_stage3_prompt(
            itinerary_table=itinerary_table,
            draft_body=draft_body,
            place_names=place_names,
            lang=prefs.get("lang", "ko"),
            tone=prefs["tone"],
            style=prefs["style"],
            extra=prefs.get("stage3_extra"),
        )
        try:
            result = await self.llm.provider.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "당신은 여행 블로그 에디터입니다. "
                            "초안을 자연스럽게 다듬어 완성된 마크다운 포스트를 출력합니다. "
                            "이미지 마크다운(![...](URL))은 절대 수정하지 않습니다."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=3000,
            )
            return result.strip()
        except Exception as e:
            logger.error(f"Stage3 실패: {e}")
            # 폴백: 초안을 제목만 붙여서 반환
            return f"# 여행 기록\n\n{itinerary_table}\n\n{draft_body}"

    # ── 메인 엔트리 ──────────────────────────────────────────────────

    async def run(
        self,
        clusters: List[Dict],
        preferences: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        파이프라인 실행

        Args:
            clusters: 클러스터 리스트 (day, location_name, representative_photo_url 포함)
            preferences: 사용자 커스터마이즈 설정 (없으면 기본값)

        Returns:
            {
                "markdown": str,    # 완성된 마크다운 포스트
                "title": str,       # 추출된 제목
                "tags": List[str],  # 추출된 태그
                "itinerary_table": str,
            }
        """
        prefs = {**DEFAULT_PREFERENCES, **(preferences or {})}

        if not clusters:
            return {
                "markdown": "# 여행 기록\n\n여행 사진을 업로드했습니다.",
                "title": "여행 기록",
                "tags": ["여행"],
                "itinerary_table": "",
            }

        # 일차별 그룹핑
        clusters_by_day = _group_clusters_by_day(clusters)

        # Stage 1: 일정 표
        logger.info("Pipeline Stage1 시작")
        itinerary_table = await self._run_stage1(clusters_by_day, prefs)

        # Stage 2: 장소별 단락 (병렬)
        logger.info(f"Pipeline Stage2 시작 — 총 {len(clusters)}개 클러스터")
        stage2_results = await self._run_stage2(clusters, prefs)

        # 일차 → 클러스터 순서로 정렬 (day 오름차순, cluster_id 오름차순)
        stage2_results.sort(key=lambda x: (x.get("day", 0), x.get("cluster_id", 0)))

        # 초안 조립
        draft_body = self._assemble_draft(itinerary_table, stage2_results)
        place_names = [r["location_name"] for r in stage2_results]

        # Stage 3: 최종 합성
        logger.info("Pipeline Stage3 시작")
        final_markdown = await self._run_stage3(
            itinerary_table=itinerary_table,
            draft_body=draft_body,
            place_names=place_names,
            prefs=prefs,
        )

        # Stage 2 결과를 지문 기준으로 캐시 저장
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
            "stage2_cache": stage2_cache,   # 다음 증분 업데이트에서 재사용
        }


    async def run_incremental(
        self,
        clusters: List[Dict],
        stage2_cache: Dict[str, Dict],
        preferences: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        증분 업데이트 파이프라인.

        Stage 2는 지문이 캐시에 있으면 재사용, 없으면 새로 호출.
        Stage 1 · Stage 3은 항상 재실행 (빠르고, 변경 반영 필요).

        Args:
            clusters:      현재 사진으로 계산된 클러스터 리스트
            stage2_cache:  기존 포스트의 stage2_cache (fingerprint → paragraph dict)
            preferences:   사용자 LLM 설정

        Returns:
            run()과 동일한 구조 + "cache_stats" 키 추가
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

        # ── Stage 1: 항상 재실행 ──────────────────────────────────────
        logger.info("Incremental Stage1 시작")
        itinerary_table = await self._run_stage1(clusters_by_day, prefs)

        # ── Stage 2: 지문 기반 캐시 히트/미스 판단 ──────────────────
        hits: List[Tuple[int, Dict]] = []    # (index, cached_result)
        misses: List[int] = []               # 재실행 필요한 클러스터 인덱스

        fingerprints = [cluster_fingerprint(c) for c in clusters]
        for i, fp in enumerate(fingerprints):
            if fp in stage2_cache:
                cached = stage2_cache[fp]
                hits.append((i, {
                    "cluster_id": clusters[i].get("cluster_id"),
                    "day":        clusters[i].get("day"),
                    "location_name": cached["location_name"],
                    "photo_url":     clusters[i].get("representative_photo_url", cached.get("photo_url", "")),
                    "paragraph":     cached["paragraph"],
                }))
            else:
                misses.append(i)

        cache_hit  = len(hits)
        cache_miss = len(misses)
        removed    = len(stage2_cache) - cache_hit  # 사라진 클러스터 수
        logger.info(f"Stage2 캐시 — hit:{cache_hit} miss:{cache_miss} removed:{removed}")

        # 캐시 미스 클러스터만 병렬 실행
        miss_results: Dict[int, Dict] = {}
        if misses:
            semaphore = asyncio.Semaphore(_STAGE2_CONCURRENCY)
            tasks = {
                i: self._run_stage2_one(clusters[i], prefs, semaphore)
                for i in misses
            }
            gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for idx, result in zip(tasks.keys(), gathered):
                if isinstance(result, Exception):
                    logger.error(f"Incremental Stage2 예외 cluster[{idx}]: {result}")
                    c = clusters[idx]
                    miss_results[idx] = {
                        "cluster_id":    c.get("cluster_id"),
                        "day":           c.get("day"),
                        "location_name": c.get("location_name", "알 수 없는 장소"),
                        "photo_url":     c.get("representative_photo_url", ""),
                        "paragraph":     "이 장소에서의 여행을 사진으로 담았습니다.",
                    }
                else:
                    miss_results[idx] = result

        # 전체 결과를 원래 클러스터 순서대로 재조립
        hit_map = {i: r for i, r in hits}
        stage2_results = [
            hit_map[i] if i in hit_map else miss_results[i]
            for i in range(len(clusters))
        ]
        stage2_results.sort(key=lambda x: (x.get("day", 0), x.get("cluster_id", 0)))

        # ── Stage 3: 항상 재실행 ──────────────────────────────────────
        logger.info("Incremental Stage3 시작")
        draft_body  = self._assemble_draft(itinerary_table, stage2_results)
        place_names = [r["location_name"] for r in stage2_results]
        final_markdown = await self._run_stage3(
            itinerary_table=itinerary_table,
            draft_body=draft_body,
            place_names=place_names,
            prefs=prefs,
        )

        # 갱신된 캐시 (히트 항목 유지 + 미스 항목 신규 추가)
        new_cache = {fp: stage2_cache[fp] for fp in fingerprints if fp in stage2_cache}
        for i in misses:
            fp = fingerprints[i]
            r  = miss_results[i]
            new_cache[fp] = {
                "location_name": r["location_name"],
                "paragraph":     r["paragraph"],
                "photo_url":     r["photo_url"],
            }

        return {
            "markdown":      final_markdown,
            "title":         _extract_title_from_markdown(final_markdown),
            "tags":          _extract_tags_from_markdown(final_markdown),
            "itinerary_table": itinerary_table,
            "stage2_cache":  new_cache,
            "cache_stats":   {"hit": cache_hit, "miss": cache_miss, "removed": removed},
        }


# 싱글톤
_pipeline: Optional[LLMPipeline] = None


def get_llm_pipeline() -> LLMPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = LLMPipeline()
    return _pipeline
