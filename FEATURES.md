# IWT (Image World Travel) - 기능 및 기술 명세서

## 프로젝트 개요

사진을 업로드하면 AI가 자동으로 여행 경로, 장소 정보, 이동 수단 등을 분석하여 여행 게시글을 생성하는 플랫폼.

---

## 기술 스택 요약

| 계층 | 현재 사용 | 추가 예정 |
|------|----------|----------|
| **프론트엔드** | React 19, Redux Toolkit, React Router 7 | - |
| **백엔드** | FastAPI 0.115, Uvicorn | - |
| **데이터베이스** | MySQL 8.0, SQLAlchemy 2.0 | 테이블 확장 (경로/구간 정규화) |
| **캐시** | Redis 7 | - |
| **인증** | Auth0 (JWT RS256) | - |
| **스토리지** | AWS S3 (boto3) | - |
| **지도** | Google Maps API (@googlemaps/react-wrapper) | Google Directions API, Google Places API |
| **AI/LLM** | Groq (llama3-8b), OpenAI, Anthropic | scikit-learn, TensorFlow Lite (장기) |
| **이미지 처리** | Pillow, exifr (EXIF 추출) | 해시 비교 (중복 제거), 블러 감지 |
| **콘텐츠** | react-markdown, remark-gfm, rehype-highlight, KaTeX | - |
| **컨테이너** | Docker Compose (4 서비스) | - |

---

## 구현 완료 기능

### 1. 사진 업로드 & EXIF 추출
- **상태**: ✅ 구현 완료
- **설명**: 사진 드래그앤드롭/파일선택 업로드, EXIF 메타데이터 자동 추출 (GPS, 촬영 시간, 카메라 정보)
- **관련 파일**:
  - `Front/src/pages/NewTripPage.js` - 업로드 UI, 여행 스타일 선택 (8종)
  - `Front/src/store/photoSlice.js` - 사진 상태 관리 (Redux)
  - `back/app/services/exif_extract_service.py` - 서버 EXIF 추출
  - `back/app/api/v1/endpoints/photo_route.py` - 사진 API
- **라이브러리**:
  - 프론트: `exifr` ^7.1.3 (클라이언트 EXIF 파싱)
  - 백엔드: `Pillow` 10.1.0 (서버 이미지 처리)

### 2. S3 파일 저장
- **상태**: ✅ 구현 완료
- **설명**: Presigned URL 기반 S3 직접 업로드, 임시→영구 파일 이동, 자동 정리
- **관련 파일**:
  - `back/app/services/s3_presigned_url.py` - URL 생성
  - `back/app/services/s3_cleanup_service.py` - 정리 서비스
- **라이브러리**: `boto3` 1.34.0

### 3. Google Maps 지도 표시
- **상태**: ✅ 구현 완료
- **설명**: 사진 GPS 데이터를 지도에 마커로 표시, 번호 매기기, 직선 경로(Polyline) 연결
- **관련 파일**:
  - `Front/src/components/MapPanel.js` - 지도 컴포넌트 (마커, 경로, 컨트롤)
  - `Front/src/styles/MapPanel.css` - 지도 스타일
- **라이브러리**:
  - `@googlemaps/react-wrapper` 1.2.0
  - `@googlemaps/js-api-loader` 1.16.10
- **현재 한계**: 직선 연결만 지원, 경로 토글 버튼 미구현

### 4. AI/LLM 분석
- **상태**: ✅ 구현 완료
- **설명**: 사진 기반 위치 추정, 장소 검색, 경로 추천, 여행기 생성, 라벨링
- **관련 파일**:
  - `back/app/services/llm_factory.py` - LLM 프로바이더 팩토리
  - `back/app/services/llm_location_search.py` - 위치 추정
  - `back/app/services/llm_route_recommend.py` - 경로 추천
  - `back/app/services/labeling_service.py` - 자동 라벨링
  - `back/app/services/reverse_geocoder.py` - 역 지오코딩
  - `back/app/services/ocr_augmenter.py` - OCR 보강
  - `back/app/api/v1/endpoints/llm_route.py` - LLM API 엔드포인트
- **라이브러리**: `groq` 0.4.2 (기본), `openai`, `anthropic` (선택)
- **API 엔드포인트**:
  - `POST /api/v1/location-estimate` - 위치 추정
  - `POST /api/v1/route-recommend` - 경로 추천
  - `POST /api/v1/generate-itinerary` - 일정 생성
  - `POST /api/v1/generate-blog` - 블로그 생성
  - `POST /api/v1/attractions` - 관광지 검색

### 5. 인증 시스템
- **상태**: ✅ 구현 완료
- **설명**: Auth0 기반 소셜 로그인, JWT 토큰 검증, 멀티 프로바이더 지원
- **관련 파일**:
  - `Front/src/services/apiClient.js` - 토큰 자동 주입
  - `back/app/core/auth.py` - JWT 검증 (RS256, JWKS)
  - `back/app/api/v1/endpoints/user_auth0.py` - 유저 API
  - `back/app/models/db_models.py` - User, UserAuthProvider 모델
- **라이브러리**:
  - 프론트: `@auth0/auth0-react` 2.4.0
  - 백엔드: `python-jose[cryptography]` 3.3.0, `authlib` 1.2.1

### 6. 게시글 관리 (CRUD)
- **상태**: ✅ 구현 완료
- **설명**: 여행 게시글 생성/조회/수정/삭제, 자동 생성, 미리보기
- **관련 파일**:
  - `Front/src/pages/CreateTripPage.js` - 게시글 편집
  - `Front/src/pages/TripDetailPage.js` - 게시글 상세
  - `back/app/api/v1/endpoints/post_route.py` - 게시글 API
- **API 엔드포인트**:
  - `POST /api/v1/posts/` - 생성
  - `POST /api/v1/posts/auto-create` - 자동 생성
  - `GET/PUT/DELETE /api/v1/posts/{id}` - CRUD

### 7. 탐색 & 프로필
- **상태**: ✅ 구현 완료 (기본)
- **설명**: 여행 탐색, 필터/검색, 프로필 관리
- **관련 파일**:
  - `Front/src/pages/ExplorePage.js` - 탐색 페이지
  - `Front/src/pages/ProfilePage.js` - 프로필 페이지
  - `Front/src/components/TravelCard.js` - 여행 카드
- **현재 한계**: 샘플 데이터 기반, 실제 API 연동 필요

### 8. Markdown 콘텐츠 렌더링
- **상태**: ✅ 구현 완료
- **설명**: 마크다운 기반 여행 문서 렌더링 (수식, 코드 하이라이팅 지원)
- **관련 파일**:
  - `Front/src/components/DocumentPanel.js` - 문서 패널
  - `Front/src/components/MarkdownPreview.js` - 마크다운 프리뷰
- **라이브러리**: `react-markdown` 10.1.0, `remark-gfm` 4.0.1, `rehype-highlight` 7.0.2, `katex` 0.16.44

### 9. UI/UX 기반
- **상태**: ✅ 구현 완료
- **설명**: 다크/라이트 테마, 토스트 알림, 에러 바운더리, 패널 리사이즈, 반응형
- **관련 파일**:
  - `Front/src/components/Header.js` - 헤더/네비게이션
  - `Front/src/components/Toast.js` - 토스트 알림
  - `Front/src/components/ErrorBoundary.js` - 에러 처리
  - `Front/src/components/Resizer.js` - 패널 리사이즈
  - `Front/src/hooks/useTheme.js` - 테마 훅

### 10. 인프라
- **상태**: ✅ 구현 완료
- **설명**: Docker Compose 기반 4 서비스 (프론트, 백엔드, MySQL, Redis)
- **관련 파일**: `docker-compose.yml`
- **서비스**: iwt-frontend(:3000), iwt-backend(:8000), iwt-mysql(:3306), iwt-redis(:6379)
- **기타**: Rate Limiting (`slowapi`), Redis 캐싱, CORS 설정, 로깅

---

## 구현 예정 기능

### 11. Google Directions API 연동
- **우선순위**: 높음
- **설명**: 직선 경로 → 실제 도로 기반 경로, 구간별 이동 시간/거리
- **추가 라이브러리**: Google Directions API (Google Maps 플랫폼에 포함)
- **비용**: 월 $200 무료 크레딧 (약 40,000건/월)
- **변경 대상**: `MapPanel.js` (Polyline → DirectionsRenderer)

### 12. 이동 수단 자동 추정
- **우선순위**: 중간
- **설명**: 사진 촬영 시간 + 거리 → 평균 속도 → 이동 수단 매칭
- **추가 라이브러리**: 없음 (자체 로직, 추후 scikit-learn으로 분류 모델 전환 가능)
- **변경 대상**: `back/app/services/` (새 서비스), `photoSlice.js` (구간 상태 추가)

### 13. 머문 시간 추정
- **우선순위**: 낮음
- **설명**: 같은 장소 사진 → 최소 체류 시간, 장소 유형 기반 평균 체류 시간 추정
- **추가 라이브러리**: Google Places API (장소 유형 조회)
- **비용**: 월 $200 무료 크레딧에 포함

### 14. 경로 표시 토글 버튼
- **우선순위**: 높음
- **설명**: `showRoutes` 상태 토글 UI 추가
- **추가 라이브러리**: 없음
- **변경 대상**: `MapPanel.js` (버튼 추가)

### 15. 사진 필터링 파이프라인
- **우선순위**: 높음
- **설명**: 중복 제거, 연사 그룹화, GPS 분리, 장소 그룹화, AI 품질 분석
- **추가 라이브러리**:
  - 프론트: `crypto-js` 또는 Web Crypto API (파일 해시)
  - 백엔드: `imagehash` (지각적 해시, 유사 이미지 감지), `opencv-python` (블러 감지, 선택)
- **변경 대상**: `photoSlice.js` (필터링 로직), 새 서비스 추가

### 16. 자동 게시글 생성 고도화
- **우선순위**: 중간
- **설명**: 사진 업로드 → 자동 필터링 → 경로 생성 → 게시글 초안 (기존 LLM 서비스 확장)
- **추가 라이브러리**: 없음 (기존 Groq/OpenAI/Anthropic 활용)
- **변경 대상**: `back/app/api/v1/endpoints/post_route.py`, `llm_route.py` 확장

### 17. 데이터 정규화 (AI 학습용 설계)
- **우선순위**: 높음
- **설명**: 경로/구간/체류 데이터를 분리된 테이블로 저장, 표준 단위, 사용자 수정 이력 포함
- **추가 라이브러리**: `alembic` (이미 설치됨, 마이그레이션)
- **변경 대상**: `back/app/models/db_models.py` (테이블 추가)
- **새 테이블**:
  ```
  Route         - trip_id, total_distance, total_duration
  RouteStop     - route_id, place_id, arrival_time, departure_time, stay_duration, order
  RouteSegment  - route_id, from_stop_id, to_stop_id, transport_mode, distance, duration
  Place         - google_place_id, name, type, lat, lng, avg_stay_duration
  UserCorrection - original_value, corrected_value, field_name (학습 라벨용)
  ```

### 18. 경로 추천 시스템
- **우선순위**: 중간 (데이터 축적 후)
- **설명**: 사용자 데이터 기반 경로/장소 추천, 인기 경로, 시즌별 추천
- **추가 라이브러리**:
  - `scikit-learn` (협업 필터링, 콘텐츠 기반 추천)
  - `pandas` (데이터 분석)
  - `numpy` (수치 연산)

### 19. 여행 플래너
- **우선순위**: 낮음 (데이터 축적 후)
- **설명**: 조건 입력 → 실제 데이터 기반 일정 자동 생성
- **추가 라이브러리**: 기존 LLM + 추천 시스템 조합

### 20. 자체 AI 모델 학습
- **우선순위**: 장기 목표
- **설명**: 이동 수단 분류, 체류 시간 예측, 경로 추천, LLM 파인튜닝
- **추가 라이브러리**:
  - 2단계: `scikit-learn`, `TensorFlow Lite` 또는 `PyTorch`
  - 3단계: `surprise` (추천 시스템), `implicit` (협업 필터링)
  - 4단계: `transformers` (HuggingFace), `peft` (LoRA 파인튜닝)
- **전제 조건**: #17 데이터 정규화 완료, 수만 건 데이터 축적, 개인정보 동의/익명화

---

## DB 모델 현황 (10개 테이블)

| 테이블 | 설명 | 상태 |
|--------|------|------|
| Post | 여행 게시글 | ✅ 구현 |
| Photo | 사진 정보 | ✅ 구현 |
| Location | GPS/위치 메타데이터 | ✅ 구현 |
| Category | 여행 카테고리 | ✅ 구현 |
| RecommendedRoute | AI 추천 경로 | ✅ 구현 |
| User | 사용자 (Auth0) | ✅ 구현 |
| UserAuthProvider | 멀티 인증 | ✅ 구현 |
| PhotoLabel | 자동 라벨 | ✅ 구현 |
| LLMAnalysis | LLM 분석 결과 | ✅ 구현 |
| ImageMetadata | 확장 메타데이터 | ✅ 구현 |
| Route | 경로 정보 | 📋 예정 (#17) |
| RouteStop | 경유지 | 📋 예정 (#17) |
| RouteSegment | 이동 구간 | 📋 예정 (#17) |
| Place | 장소 마스터 | 📋 예정 (#17) |
| UserCorrection | 사용자 수정 이력 (학습 라벨) | 📋 예정 (#17) |

---

## API 엔드포인트 현황

| 경로 | 메서드 | 설명 | 상태 |
|------|--------|------|------|
| `/api/v1/users/signin` | POST | 로그인/가입 | ✅ |
| `/api/v1/photos/presigned-url` | POST | S3 업로드 URL | ✅ |
| `/api/v1/photos/batch-presigned-urls` | POST | 배치 URL | ✅ |
| `/api/v1/photos/extract-exif` | POST | EXIF 추출 | ✅ |
| `/api/v1/photos/process-exif-with-llm` | POST | LLM EXIF 처리 | ✅ |
| `/api/v1/photos/batch-process` | POST | 배치 처리 | ✅ |
| `/api/v1/posts/` | CRUD | 게시글 관리 | ✅ |
| `/api/v1/posts/auto-create` | POST | 자동 생성 | ✅ |
| `/api/v1/location-estimate` | POST | 위치 추정 | ✅ |
| `/api/v1/route-recommend` | POST | 경로 추천 | ✅ |
| `/api/v1/generate-itinerary` | POST | 일정 생성 | ✅ |
| `/api/v1/generate-blog` | POST | 블로그 생성 | ✅ |
| `/api/v1/photos/filter` | POST | 사진 필터링 | 📋 예정 (#15) |
| `/api/v1/routes/directions` | GET | 도로 경로 | 📋 예정 (#11) |
| `/api/v1/routes/transport-mode` | GET | 이동 수단 추정 | 📋 예정 (#12) |
| `/api/v1/places/info` | GET | 장소 정보 | 📋 예정 (#13) |
| `/api/v1/recommend/routes` | GET | 경로 추천 | 📋 예정 (#18) |
| `/api/v1/planner/generate` | POST | 여행 플래너 | 📋 예정 (#19) |

---

## 외부 서비스 & API 키 현황

| 서비스 | 용도 | 상태 | 환경변수 |
|--------|------|------|----------|
| Auth0 | 인증 | ✅ 사용 중 | `AUTH0_DOMAIN`, `AUTH0_AUDIENCE` |
| AWS S3 | 파일 저장 | ✅ 사용 중 | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| Google Maps | 지도 표시 | ✅ 사용 중 | `REACT_APP_GOOGLE_MAPS_API_KEY` |
| Groq | LLM (기본) | ✅ 사용 중 | `GROQ_API_KEY` |
| OpenAI | LLM (선택) | ✅ 설정됨 | `OPENAI_API_KEY` |
| Anthropic | LLM (선택) | ✅ 설정됨 | `ANTHROPIC_API_KEY` |
| Google Directions | 도로 경로 | 📋 예정 | Google Maps 키 공유 |
| Google Places | 장소 정보 | 📋 예정 | Google Maps 키 공유 |
