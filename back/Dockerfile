FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

# 무거운 의존성 먼저 복사 및 설치 (Docker 레이어 캐싱 활용)
COPY requirements.base.txt .
RUN uv pip install --system --no-cache -r requirements.base.txt

# 나머지 의존성 복사 및 설치 (자주 변경되는 패키지)
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# 소스 코드 복사
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 