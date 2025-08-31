# Trip Photo API 🚀

여행 사진 관리 및 AI 기반 분석을 위한 FastAPI 백엔드 서비스

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![MySQL](https://img.shields.io/badge/MySQL-8.0+-orange.svg)](https://mysql.com)

## 🌟 주요 기능

- **🔐 사용자 관리**: Auth0 기반 인증 및 사용자 프로필 관리
- **📸 사진 업로드**: S3 기반 파일 저장 및 EXIF 데이터 추출
- **🤖 AI 분석**: LLM을 활용한 위치 추정 및 이미지 분석
- **🗺️ 여행 경로 추천**: 사진 기반 맞춤형 여행 루트 생성
- **🏷️ 자동 라벨링**: AI 기반 사진 자동 분류 및 태깅
- **📊 실시간 모니터링**: 구조화된 로깅 및 성능 모니터링

## 🏗️ 개선된 아키텍처

새로운 모듈화된 구조로 유지보수성과 확장성을 크게 향상시켰습니다.

```
app/
├── api/v1/endpoints/     # 🔌 API 엔드포인트
│   ├── user_auth0.py    # 사용자 관리 (개선됨)
│   ├── photo_route.py   # 사진 업로드
│   ├── llm_route.py     # LLM 분석
│   └── post_route.py    # 포스트 관리
├── core/                # ⚙️ 핵심 설정 및 유틸리티 (신규)
│   ├── config.py        # 중앙화된 설정 관리
│   ├── exceptions.py    # 커스텀 예외 처리
│   ├── logging.py       # 구조화된 로깅 시스템
│   └── auth.py          # 인증 관련
├── models/              # 🗃️ 데이터베이스 모델
│   └── db_models.py     # SQLAlchemy 모델
├── schemas/             # 📋 Pydantic 스키마 (신규)
│   ├── user.py          # 사용자 스키마
│   ├── photo.py         # 사진 스키마
│   └── ...
├── services/            # 🔧 비즈니스 로직 (개선됨)
│   ├── user_service.py  # 사용자 서비스 로직
│   ├── llm_base.py      # LLM 추상화 계층
│   └── ...
├── repositories/        # 🗄️ 데이터 접근 계층 (신규)
│   ├── user_repository.py
│   └── photo_repository.py
└── main.py             # 🚀 애플리케이션 진입점 (개선됨)
```

## 🚀 빠른 시작

### 환경 설정

1. **Python 환경 설정**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **환경 변수 설정**
   ```bash
   cp .env.example .env
   # .env 파일을 편집하여 필요한 설정 입력
   ```

3. **데이터베이스 설정**
   ```bash
   # MySQL 데이터베이스 생성
   mysql -u root -p
   CREATE DATABASE trip_db;
   
   # 마이그레이션 실행
   alembic upgrade head
   ```

### 서버 실행

```bash
# 개발 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 프로덕션 서버 실행
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## 📋 환경 변수

| 변수명 | 설명 | 기본값 | 필수 |
|--------|------|--------|------|
| `DEBUG` | 디버그 모드 | `False` | ❌ |
| `DATABASE_URL` | 데이터베이스 연결 URL | - | ✅ |
| `AUTH0_DOMAIN` | Auth0 도메인 | - | ✅ |
| `AUTH0_AUDIENCE` | Auth0 Audience | - | ✅ |
| `AWS_ACCESS_KEY_ID` | AWS 액세스 키 | - | ✅ |
| `AWS_SECRET_ACCESS_KEY` | AWS 시크릿 키 | - | ✅ |
| `S3_BUCKET_NAME` | S3 버킷 이름 | - | ✅ |
| `GROQ_API_KEY` | Groq LLM API 키 | - | ✅ |

## 프로젝트 구조

### 주요 디렉토리
```
back/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── user_auth0.py
│   │       │   ├── photo_route.py
│   │       │   ├── llm_route.py
│   │       │   └── post_route.py
│   │       └── routes/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── services/
│   │   ├── s3_presigned_url.py
│   │   ├── exif_extract_service.py
│   │   ├── llm_location_search.py
│   │   ├── ocr_augmenter.py
│   │   ├── reverse_geocoder.py
│   │   ├── album_category_service.py
│   │   └── llm_route_recommend.py
│   ├── schemas/
│   ├── repositories/
│   └── main.py
├── scheduler/
│   └── clean_orphan_files.py
├── requirements.txt
└── Dockerfile
```

## 주요 서비스 및 모듈

### 핵심 서비스

#### `services/s3_presigned_url.py`
- **기능**: S3 presigned URL 발급, S3 업로드 취약점 관리
- **역할**:
  - 클라이언트에게 안전한 S3 업로드 URL 발급
  - 업로드 권한 및 만료 시간 관리
  - 보안 취약점 방지를 위한 URL 검증

#### `services/exif_extract_service.py`
- **기능**: 이미지 EXIF 메타데이터(위치/시간 등) 신뢰성 있게 추출
- **역할**:
  - 업로드된 이미지에서 GPS 좌표, 촬영 시간 추출
  - 메타데이터 유효성 검증
  - 추출 실패 시 대체 방법 제공

#### `services/llm_location_search.py`
- **기능**: 이미지/EXIF 기반 LLM 위치 인식(지명, 위경도 등)
- **역할**:
  - EXIF 데이터를 기반으로 LLM이 위치 정보 추정
  - 이미지 분석을 통한 지명 인식
  - 위경도 좌표와 지명 매핑

#### `services/ocr_augmenter.py`
- **기능**: 이미지 내 표지판/텍스트 OCR로 위치 보완(옵션)
- **역할**:
  - 이미지 내 텍스트 추출을 통한 위치 정보 보완
  - 표지판, 간판 등의 텍스트 인식
  - EXIF 데이터와 결합하여 정확도 향상

#### `services/reverse_geocoder.py`
- **기능**: 위경도 → 국가/도시 등 카테고리 변환, LLM 보조 프롬프트 데이터 제공
- **역할**:
  - GPS 좌표를 국가, 도시, 지역으로 변환
  - LLM 추천 시스템을 위한 지역 정보 제공
  - 카테고리 분류를 위한 메타데이터 생성

#### `services/album_category_service.py`
- **기능**: 사진/여행별 국가, 도시, 테마 카테고리 자동 분류/저장
- **역할**:
  - 업로드된 사진들을 자동으로 카테고리별 분류
  - 국가, 도시, 테마별 태깅 자동 생성
  - 앨범 구성에 필요한 메타데이터 관리

#### `services/llm_route_recommend.py`
- **기능**: 카테고리(국가/도시/테마)별 DB 정보+LLM 기반 여행 경로/루트 추천
- **역할**:
  - 기존 여행 데이터와 LLM을 결합한 경로 추천
  - 사용자 선호도 기반 맞춤형 추천
  - 실시간 경로 최적화

### 데이터베이스

#### `models/db_models.py`
- **기능**: 게시글, 사진, 위치, 카테고리, 추천 경로 등 DB 모델 정의
- **역할**:
  - SQLAlchemy ORM 모델 정의
  - 데이터베이스 스키마 관리
  - 관계형 데이터 모델링

### API 라우트

#### `api/v1/endpoints/photo_route.py`
- **기능**: 사진 업로드/메타데이터 관련 API 엔드포인트
- **역할**:
  - 사진 업로드 처리
  - EXIF 메타데이터 추출 API
  - 사진 미리보기 및 관리

#### `api/v1/endpoints/llm_route.py`
- **기능**: LLM 위치추정, 경로추천 관련 API 엔드포인트
- **역할**:
  - LLM 기반 위치 추정 API
  - 여행 경로 추천 API
  - AI 기반 여행 계획 생성

#### `api/v1/endpoints/post_route.py`
- **기능**: 게시글(여행) 등록 및 관리 API
- **역할**:
  - 여행 게시글 CRUD 작업
  - 게시글 상태 관리
  - 사용자별 게시글 관리

### 유틸리티

#### `scheduler/clean_orphan_files.py`
- **기능**: S3 temp 폴더 내 고아 파일(임시) 자동 삭제
- **역할**:
  - 정기적인 임시 파일 정리
  - 스토리지 비용 최적화
  - 시스템 리소스 관리

## 사진 업로드~게시글 작성 흐름 (LLM 기반 경로 추천 설계 포함)

### 1. 프론트엔드 파일/컴포넌트 흐름
```
1. PostCreatePage.jsx (메인 페이지)
   ↓
2. ImageUpload.jsx (사진 선택)
   ↓
3. ExifExtract.js (메타데이터 추출)
   ↓
4. PhotoPreview.jsx (미리보기)
   ↓
5. LocationConfirmModal.jsx (위치 확인/수정)
   ↓
6. AlbumCategory.jsx (카테고리 분류)
   ↓
7. TimelineViewer.jsx (타임라인 구성)
   ↓
8. MapRouteViewer.jsx (경로 시각화)
   ↓
9. Recommendation.jsx (추천 결과 표시)
```

### 2. 백엔드 파일/모듈 흐름
```
1. photo_route.py (사진 업로드 API)
   ↓
2. s3_presigned_url.py (S3 URL 발급)
   ↓
3. exif_extract_service.py (EXIF 추출)
   ↓
4. llm_location_search.py (LLM 위치 추정)
   ↓
5. ocr_augmenter.py (OCR 보완 - 옵션)
   ↓
6. reverse_geocoder.py (지역 정보 변환)
   ↓
7. album_category_service.py (카테고리 분류)
   ↓
8. llm_route_recommend.py (경로 추천)
   ↓
9. post_route.py (게시글 저장)
   ↓
10. db_models.py (데이터베이스 저장)
```

## 실행 방법

### 개발 환경
```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 데이터베이스 마이그레이션
alembic upgrade head

# 서버 실행
uvicorn app.main:app --reload
```

### Docker 환경
```bash
# 컨테이너 빌드 및 실행
docker-compose up --build
```

## API 문서
서버 실행 후 다음 URL에서 API 문서를 확인할 수 있습니다:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc 