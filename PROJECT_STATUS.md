# IWT — Project Status

> **I Want. I Went. Trip.**  
> 여행 사진을 업로드하면 경로·게시글을 자동 생성하고 공유하는 여행 플랫폼  
> 최종 검토일: 2026-04-08

---

## 1. 기술 스택

| 영역 | 기술 |
|------|------|
| 프론트엔드 | React 19, Redux Toolkit, React Router 7, Auth0 |
| 백엔드 | FastAPI, SQLAlchemy 2, Pydantic v2 |
| DB | MySQL 8.0 (AWS RDS) |
| 캐시 | Redis 7 |
| 스토리지 | AWS S3 (presigned URL) |
| 인증 | Auth0 (RS256 JWT) |
| LLM | Google Gemini (`gemini-3.1-flash-lite-preview`) |
| 지도 | Google Maps API (프론트), Nominatim/OpenStreetMap (백엔드 역지오코딩) |
| 경로 | Google Directions API |
| 배포 | Docker Compose (개발) / Docker Compose prod (운영) |

---

## 2. 전체 아키텍처

```
[브라우저]
    │ Auth0 JWT
    ▼
[React SPA : 3000]
    │ REST API
    ▼
[FastAPI : 8000]  ←─ Redis (캐시 / Rate Limit)
    │
    ├─ MySQL RDS (영구 데이터)
    ├─ AWS S3 (사진 파일)
    ├─ Nominatim API (역지오코딩)
    ├─ Google Directions API (경로)
    └─ Gemini API (자연어 게시글 생성)
```

---

## 3. 핵심 데이터 파이프라인

### 여행 게시글 자동 생성 흐름

```
[프론트엔드]
사진 선택
  → exifr.js로 EXIF 추출 (GPS, 촬영시간, 카메라)
  → S3 presigned URL 발급 받아 직접 업로드
  → EXIF 데이터를 백엔드로 전송

[백엔드 - POST /posts/auto-create]
  ↓
① photo_filter_service  ── 7단계 사진 필터링
  │  1. 파일 해시 기반 완전 중복 제거
  │  2. 연사/버스트 그룹화 (3초·50m → 대표 1장)
  │  3. GPS 없는 사진 분리
  │  4. 같은 장소 그룹화 (100m 반경)
  │  5. AI 품질 분석 (미구현 — TODO)
  │  6. 쓰레기 데이터 탐지 (시간 편차 30일 / 거리 1000km)
  │  7. 활용 내역 코드 표기
  ↓
② photo_cleaner_service  ── 2단계 묶음 정제 (서버사이드)
  │  - GPS 이상치 제거 (속도 >900km/h + MAD 클러스터)
  │  - 시간 간격 6시간 기준 여행 구간 분리
  │  - Null Island (0,0) 및 미래/2000년 이전 날짜 필터
  │  - 사진별 활용 코드 (0001~0005) 리포트 생성
  ↓
③ reverse_geocoder  ── Nominatim API
  │  GPS 좌표 → 국가 / 도시 / 주소 (LLM 사용 안 함)
  ↓
④ llm_route_recommend  ── Gemini API (자연어 생성만)
  │  정제된 구조화 데이터 → 여행 제목 / 설명 / 태그
  │  각 사진 한 줄 코멘트
  ↓
⑤ DB 저장
  │  Post, Photo, Location, Category 테이블
  │  S3 임시 파일 → 영구 저장소 이동
  ↓
피드 / 공유
```

> **LLM 투입 원칙**: GPS 분석·경로 계산에는 LLM을 사용하지 않는다.  
> 정제·구조화가 완료된 데이터를 자연어로 변환하는 마지막 단계에서만 호출한다.

---

## 4. DB 스키마 (19개 테이블)

```
users ──────────────────────────────────────────────────────┐
  └── user_auth_providers                                    │
                                                             │
posts (user_id → users) ────────────────────────────────────┤
  ├── photos                                                 │
  │     ├── locations        (GPS, 국가/도시/랜드마크)        │
  │     ├── photo_labels     (출처별 라벨: exif/llm/manual)  │
  │     ├── llm_analyses     (분석 결과 JSON)                 │
  │     └── image_metadata   (EXIF/LLM 메타데이터)           │
  ├── categories             (country/city/region/theme)     │
  ├── recommended_routes     (경로 JSON)                     │
  ├── post_likes                                             │
  ├── post_bookmarks                                         │
  └── comments (스레드형, parent_id 자기참조)                 │
                                                             │
follows (follower_id / following_id → users)                 │
notifications (user_id → users)                              │
                                                             │
── AI 학습용 정규화 테이블 ─────────────────────────────────┘
places          (장소 마스터, avg_stay_duration, visit_count)
routes          (post_id, total_distance, total_duration)
route_stops     (route_id, place_id, arrival/departure_time)
route_segments  (route_id, transport_mode, distance, duration)
user_corrections (AI 수정 이력)
```

---

## 5. 구현 현황

### 5-1. 백엔드

#### API 엔드포인트

| 그룹 | 엔드포인트 | 상태 |
|------|-----------|------|
| **사용자** | GET /me, GET/PUT/DELETE /profile/{id}, POST /auth0 | ✅ 완료 |
| **사진** | POST /presigned-url, /batch-presigned-urls | ✅ 완료 |
| | POST /extract-exif, /enhance-location, /batch-process | ✅ 완료 |
| | POST /move-to-permanent, DELETE /temp-files | ✅ 완료 |
| | GET /preview/{key}, GET /health | ✅ 완료 |
| | POST /filter (7단계 파이프라인) | ✅ 완료 |
| | POST /process-exif-with-llm | ⚠️ 부분 (LLM 역할 검토 필요) |
| **게시글** | POST, GET, PUT, DELETE /posts | ✅ 완료 |
| | POST /posts/auto-create | ✅ 완료 |
| | GET /posts/user/{id} | ✅ 완료 |
| **소셜** | POST like/bookmark, GET feed | ✅ 완료 |
| | GET/POST/PUT/DELETE comments | ✅ 완료 |
| | POST/GET follow/followers/following | ✅ 완료 |
| **검색** | GET /search/posts, /search/suggestions | ✅ 완료 |
| **알림** | GET/PUT/DELETE notifications | ✅ 완료 |
| **경로** | POST /routes/directions | ✅ 완료 |
| **LLM** | POST /llm/location-estimate | ✅ 완료 |
| | POST /llm/route-recommend, /attractions | ✅ 완료 |
| | POST /llm/generate-itinerary, /generate-blog | ✅ 완료 |
| | POST /llm/category-recommendations | ✅ 완료 |
| | POST /llm/ocr-enhance | ⚠️ 껍데기 (실제 OCR 미연동) |
| | POST /llm/enhance-location | ⚠️ 부분 구현 |
| **이미지 메타** | (라우터 등록됨) | ❌ 메서드 미구현 |

#### 서비스 레이어

| 서비스 | 역할 | 상태 |
|--------|------|------|
| `photo_filter_service.py` | 7단계 필터링 + `clean_batch()` 2단계 묶음 정제 통합 | ✅ 완료 |
| `exif_extract_service.py` | EXIF 추출·검증 | ✅ 완료 |
| `reverse_geocoder.py` | Nominatim 역지오코딩 | ✅ 완료 |
| `directions_service.py` | Google Directions API | ✅ 완료 |
| `llm_factory.py` | LLM 제공자 팩토리 | ✅ 완료 |
| `llm_base.py` | LLM 추상화 + 게시글 생성 | ✅ 완료 |
| `llm_route_recommend.py` | 여행 요약·태그·일정 생성 | ✅ 완료 |
| `llm_location_search.py` | 위치 컨텍스트 보완 | ⚠️ 부분 |
| `ocr_augmenter.py` | OCR 위치 보완 | ❌ 구조만 (OCR 미연동) |
| `s3_presigned_url.py` | S3 업로드 URL 관리 | ✅ 완료 |
| `s3_cleanup_service.py` | 임시파일 자동 정리 (6h) | ✅ 완료 |
| `notification_service.py` | 알림 CRUD | ✅ 완료 |
| `user_service.py` | 사용자 관리 | ✅ 완료 |
| `labeling_service.py` | 라벨 저장 | ✅ 완료 |
| `album_category_service.py` | 카테고리 분류 | ✅ 완료 |

#### LLM 제공자

| 제공자 | 파일 | 상태 |
|--------|------|------|
| Gemini | `gemini_provider.py` | ✅ 현재 기본값 |
| Groq | `groq_provider.py` | ✅ 대기 |
| OpenAI | `openai_provider.py` | ✅ 대기 |
| Anthropic | `anthropic_provider.py` | ⚠️ 확인 필요 |

---

### 5-2. 프론트엔드

| 페이지 | 경로 | 상태 |
|--------|------|------|
| MainPage | `/` | ✅ API 연동 완료 (내 여행 + 추천 여행) |
| NewTripPage | `/trip/new` | ✅ 완료 |
| CreateTripPage | `/trip/new/edit` | ✅ 완료 (3패널 에디터) |
| TripDetailPage | `/trip/:id` | ✅ 완료 (사진 갤러리 + 지도 + 댓글) |
| ExplorePage | `/explore` | ✅ 완료 |
| FeedPage | `/feed` | ✅ 완료 |
| ProfilePage | `/profile` | ✅ 완료 (API 연동) |

| 컴포넌트 | 상태 |
|---------|------|
| ImagePanel (사진 업로드·EXIF·필터) | ✅ 완료 |
| DocumentPanel (게시글 편집·마크다운) | ✅ 완료 |
| MapPanel (지도·마커·경로) | ✅ 완료 |
| Header (네비·테마·로그인) | ✅ 완료 |
| NotificationDropdown | ✅ 완료 |
| ExifEditModal | ✅ 완료 |
| TravelCard | ✅ 완료 |

---

## 6. 알려진 이슈 및 기술 부채

| 우선순위 | 이슈 | 파일 |
|---------|------|------|
| ✅ | `photo_filter_service` + `photo_cleaner_service` 통합 완료 (`clean_batch()` 추가, `photo_cleaner_service.py` 삭제) | photo_filter_service.py |
| ✅ | `post_route.py` `model_used="groq"` → `"gemini"` 수정 완료 | post_route.py |
| ✅ | `MainPage` API 연동 완료 | MainPage.js |
| ✅ | `TripDetailPage` 사진 갤러리 + 지도 구현 완료 | TripDetailPage.js |
| ✅ | 백엔드 `GET /posts/{id}/photos` 엔드포인트 추가 | post_route.py |
| 🟠 | OCR 기능 미연동 — `ocr_augmenter.py` 구조만 존재 | ocr_augmenter.py |
| 🟡 | `photo_filter_service` 5단계 AI 품질 분석 미구현 (`pass` 처리) | photo_filter_service.py |
| 🟡 | Image Metadata API 라우터만 등록, 메서드 없음 | image_metadata.py |
| 🟡 | `process-exif-with-llm` — LLM 역할 재검토 (GPS→위치는 Nominatim 사용해야 함) | photo_route.py |

---

## 7. 남은 작업 목록 (우선순위별)

### 🔴 즉시

- [x] `photo_filter_service` ↔ `photo_cleaner_service` 역할 명확화 및 통합 ✅
- [x] `post_route.py` `model_used` 하드코딩 수정 ✅
- [x] `MainPage` API 연동 (게시글 목록 실제 데이터) ✅

### 🟠 핵심 기능

- [x] `TripDetailPage` 구현 — 사진 갤러리 + 지도(Google Maps) + 댓글 ✅
- [x] 백엔드 `GET /posts/{id}/photos` (S3 presigned URL 포함) 엔드포인트 추가 ✅
- [ ] `ProfilePage` API 엔드포인트 호환성 최종 확인 (구현은 완료, 엔드포인트 검증 필요)
- [x] 경로 표시 토글 — MapPanel 이미 구현됨 (showRoutes / useDirections 버튼) ✅
- [x] Google Directions API 경로 → 지도 실제 도로 표시 — MapPanel 이미 구현됨 ✅

### 🟡 품질 향상

- [ ] `photo_filter_service` 5단계 AI 품질 분석 구현
- [ ] 이동 수단 자동 추정 (시간·거리 → 속도 기반 분류)
- [ ] 장소별 머문 시간 계산 (첫 사진~마지막 사진 시간 차)
- [ ] `process-exif-with-llm` 엔드포인트 LLM 역할 재정리

### 🟢 확장

- [ ] 여행 코스 복사 기능 ("나도 이 코스로 갈래")
- [ ] 게시글 공유 (링크, SNS)
- [ ] 여행 기록 PDF 내보내기
- [ ] 실시간 GPS 트래킹

---

## 8. 환경 변수 체크리스트

```env
# 필수
AUTH0_DOMAIN=
AUTH0_AUDIENCE=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=
S3_BUCKET_NAME=
GEMINI_API_KEY=          ← 현재 기본 LLM
LLM_PROVIDER=gemini
LLM_MODEL_NAME=gemini-3.1-flash-lite-preview
MYSQL_USER=
MYSQL_PASSWORD=
MYSQL_HOST=
MYSQL_DB=
SECRET_KEY=

# 선택
GROQ_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEONAMES_USERNAME=       ← Nominatim 보조
GOOGLE_MAPS_API_KEY=     ← Directions API
REDIS_URL=
```

---

## 9. 파일 구조 요약

```
IWT/
├── back/
│   ├── app/
│   │   ├── api/v1/endpoints/
│   │   │   ├── user_auth0.py
│   │   │   ├── photo_route.py
│   │   │   ├── post_route.py
│   │   │   ├── social_route.py
│   │   │   ├── search_route.py
│   │   │   ├── notification_route.py
│   │   │   ├── directions_route.py
│   │   │   ├── llm_route.py
│   │   │   ├── photo_filter_route.py
│   │   │   └── image_metadata.py     ← 메서드 미구현
│   │   ├── services/
│   │   │   ├── photo_filter_service.py   ← 7단계 필터링 + clean_batch() 통합
│   │   │   ├── exif_extract_service.py
│   │   │   ├── reverse_geocoder.py
│   │   │   ├── directions_service.py
│   │   │   ├── llm_factory.py
│   │   │   ├── llm_base.py
│   │   │   ├── llm_route_recommend.py
│   │   │   ├── llm_location_search.py
│   │   │   ├── ocr_augmenter.py          ← OCR 미연동
│   │   │   ├── providers/
│   │   │   │   ├── gemini_provider.py    ← 현재 기본값
│   │   │   │   ├── groq_provider.py
│   │   │   │   ├── openai_provider.py
│   │   │   │   └── anthropic_provider.py
│   │   │   ├── s3_presigned_url.py
│   │   │   ├── s3_cleanup_service.py
│   │   │   ├── notification_service.py
│   │   │   ├── user_service.py
│   │   │   ├── labeling_service.py
│   │   │   └── album_category_service.py
│   │   ├── models/db_models.py           ← 19개 테이블
│   │   ├── schemas/
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── auth.py
│   │   │   ├── cache.py
│   │   │   └── rate_limit.py
│   │   └── db/session.py
│   ├── .env
│   └── requirements.txt
│
├── Front/src/
│   ├── pages/
│   │   ├── MainPage.js        ✅ API 연동
│   │   ├── NewTripPage.js     ✅
│   │   ├── CreateTripPage.js  ✅ (3패널)
│   │   ├── TripDetailPage.js  ✅ 갤러리+지도+댓글
│   │   ├── ExplorePage.js     ✅
│   │   ├── FeedPage.js        ✅
│   │   └── ProfilePage.js     ✅ API 연동
│   ├── components/
│   │   ├── ImagePanel.js      ✅
│   │   ├── DocumentPanel.js   ✅
│   │   ├── MapPanel.js        ✅
│   │   ├── Header.js          ✅
│   │   └── ...
│   ├── store/
│   │   ├── photoSlice.js
│   │   ├── socialSlice.js
│   │   └── notificationSlice.js
│   └── services/apiClient.js
│
├── docker-compose.yml
├── docker-compose.prod.yml
└── PROJECT_STATUS.md          ← 이 파일
```
