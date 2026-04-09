# IWT 개발 백로그

> 업데이트: 2026-04-09  
> 이 문서는 향후 구현 예정 기능을 정리한 것으로, 우선순위에 따라 작업 예정.

---

## 3순위 — 나중에 구현할 것

### 📌 사진 드래그 → 본문 삽입

**개요**  
왼쪽 패널(사진 리스트)에서 사진을 드래그해 중앙 패널(마크다운 에디터) 커서 위치에 드롭하면, 해당 사진의 presigned URL이 `![이름](url)` 형식으로 본문에 삽입되는 기능.

**구현 포인트**
- 왼쪽 패널 사진에 `draggable` 속성 + `onDragStart` (photoId, fileKey 전달)
- 에디터 textarea에 `onDragOver` / `onDrop` 이벤트 처리
- 드롭 시 커서 위치(selectionStart)에 마크다운 이미지 문법 삽입
- 삽입할 URL은 업로드된 경우 presigned URL, 아직 업로드 전이면 로컬 preview URL (blob:) 사용 후 업로드 시 교체

**관련 파일**
- `Front/src/components/ImagePanel.js` — draggable 추가
- `Front/src/components/DocumentPanel.js` — drop zone 추가

---

### 📌 본문에 사진 임베드 (AI 자동)

**개요**  
AI가 여행 기록을 생성할 때 중요한 장소·순간마다 대표 사진을 본문에 자동으로 삽입.  
예) 1일차 오사카 도착 단락 아래에 해당 시간대에 찍힌 사진 1~2장이 자동 삽입됨.

**구현 포인트**
- 백엔드 LLM 프롬프트에 사진 목록 + 시간/위치 정보 전달
- LLM이 마크다운 내 `[PHOTO:photoId]` 플레이스홀더 삽입
- 프론트에서 마크다운 렌더링 시 플레이스홀더를 실제 `<img>` 또는 presigned URL로 치환
- 왼쪽 패널에서 해당 사진에 "본문 활용됨" 표시 연동

**관련 파일**
- `back/app/services/llm_route_recommend.py` — 프롬프트에 photo 목록 포함
- `back/app/schemas/llm.py` — ItineraryResponse에 used_photo_ids 필드 추가
- `Front/src/components/MarkdownPreview.js` — [PHOTO:id] 치환 로직

---

### 📌 +위치 추가 (지도 클릭 방식)

**개요**  
오른쪽 지도 패널에서 "+위치 추가" 버튼 클릭 시 맵 커서가 바뀌고, 사용자가 지도를 클릭한 좌표에 새 위치 핀을 추가하는 기능.

**구현 포인트**
- 클릭 후 시간 설정 모달 표시 (기존 사진 타임라인 사이에 삽입될 시간 선택)
- 기존 타임라인 순서(captureTimestamp)에 맞게 자동 정렬
- 추가된 핀은 드래그로 이동 가능 (`google.maps.Marker` draggable 옵션)
- 드래그 완료 시 좌표 Redux 업데이트
- 수동 추가된 핀은 별도 마커 스타일(테두리 점선 등)로 구분 표시

**관련 파일**
- `Front/src/components/MapPanel.js` — handleMapClick, draggable marker
- `Front/src/store/photoSlice.js` — manualLocation 타입 추가

---

### 📌 여행 계획하기 — 별도 페이지 분리

**개요**  
현재 `/trip/new`에서 "여행 계획하기" 탭이 기록하기와 같은 플로우를 사용하지만, 계획 모드는 사진이 없는 상태에서 출발하므로 데이터 구조와 UX가 다름.  
별도 라우트(`/trip/plan`)와 전용 페이지로 분리해야 함.

**구현 포인트**
- `/trip/plan` 라우트 + `PlanTripPage.js` 신규 생성
- 백엔드에 `POST /api/v1/trips/plan` 엔드포인트 추가
  - 입력: destination, styles, duration, companions
  - 출력: 추천 경로 (장소 목록 + 이동 순서 + 예상 시간)
- 결과 화면: 지도 + 일정표 형식 (게시글 에디터와 무관)
- 결과를 저장하거나 게시글로 전환하는 별도 액션

**관련 파일**
- `Front/src/pages/PlanTripPage.js` — 신규
- `Front/src/App.js` — `/trip/plan` 라우트 추가
- `back/app/api/v1/endpoints/trip_plan_route.py` — 신규 엔드포인트

---

## 완료된 주요 작업

- [x] 기본 게시글 CRUD (2026-04)
- [x] 소셜 기능: 좋아요, 북마크, 댓글, 팔로우 (2026-04)
- [x] MinIO 로컬 스토리지 연동 (2026-04)
- [x] 사진 필터링 파이프라인 (중복/연사/GPS이상치) (2026-04)
- [x] 게시글 목록 optional auth (비로그인 열람) (2026-04)
- [x] PostResponse 소셜 정보 포함 (likes_count, thumbnail_url 등) (2026-04)
