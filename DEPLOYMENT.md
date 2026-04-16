# IWT 오라클 클라우드 배포 가이드

## 인스턴스 정보
| 항목 | 값 |
|------|-----|
| IP | 144.24.85.97 |
| OS | Ubuntu 22.04 Minimal aarch64 |
| Shape | VM.Standard.A1.Flex |
| 스펙 | 4 OCPU / 24GB RAM |
| 리전 | ap-chuncheon-1 |
| 사용자 | ubuntu |

---

## 1단계: 서버 초기 설정

### 시스템 업데이트
```bash
sudo apt-get update && sudo apt-get upgrade -y
# 커널 업그레이드 후 재부팅 권장
sudo reboot
```

### Docker 설치
```bash
sudo apt-get install -y ca-certificates curl gnupg lsb-release git nano

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker $USER
sudo systemctl enable docker && sudo systemctl start docker
# 이후 exit 후 재접속 필수 (docker 권한 적용)
```

### 방화벽 설정
```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 7 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save
```

---

## 2단계: 프로젝트 클론

```bash
sudo mkdir -p /opt/iwt
sudo chown ubuntu:ubuntu /opt/iwt
cd /opt/iwt
git clone https://github.com/duckgeunpark/IWT.git .
```

---

## 3단계: 환경변수 설정

### .env.prod 생성
```bash
# SECRET_KEY 생성
python3 -c "import secrets; print(secrets.token_hex(32))"

cat > /opt/iwt/.env.prod << 'EOF'
DB_HOST=mysql
DB_PORT=3306
DB_NAME=iwt_db
DB_USER=iwt_user
DB_PASSWORD=<비밀번호>
AUTH0_DOMAIN=duckgeunpark.us.auth0.com
AUTH0_AUDIENCE=https://duckgeunpark.us.auth0.com/api/v2/
AUTH0_ALGORITHMS=RS256
OCI_S3_ENDPOINT=https://axgk3nbeozag.compat.objectstorage.ap-chuncheon-1.oraclecloud.com
OCI_ACCESS_KEY_ID=<액세스키>
OCI_SECRET_ACCESS_KEY=<시크릿키>
OCI_REGION=ap-chuncheon-1
OCI_BUCKET_NAME=iwt-storage
LLM_PROVIDER=gemini
LLM_MODEL_NAME=gemini-2.0-flash-lite
GEMINI_API_KEY=<Gemini API Key>
REDIS_URL=redis://redis:6379/0
CACHE_TTL=3600
SECRET_KEY=<생성된 SECRET_KEY>
DEBUG=false
LOG_LEVEL=INFO
ALLOWED_ORIGINS=["http://144.24.85.97"]
RATE_LIMIT_DEFAULT=60/minute
RATE_LIMIT_LLM=10/minute
MAX_FILE_SIZE=10485760
REACT_APP_AUTH0_DOMAIN=duckgeunpark.us.auth0.com
REACT_APP_AUTH0_CLIENT_ID=<Auth0 Client ID>
REACT_APP_AUTH0_CALLBACK_URL=http://144.24.85.97
REACT_APP_AUTH0_AUDIENCE=https://duckgeunpark.us.auth0.com/api/v2/
REACT_APP_GOOGLE_MAPS_API_KEY=<Google Maps API Key>
REACT_APP_API_URL=http://144.24.85.97
EOF
```

> **주의**: docker compose는 `.env.prod`를 자동으로 읽지 않음
> 반드시 `--env-file .env.prod` 플래그 사용 필요

### alias 등록 (편의용)
```bash
echo "alias dcprod='docker compose --env-file /opt/iwt/.env.prod -f /opt/iwt/docker-compose.prod.yml'" >> ~/.bashrc
source ~/.bashrc
```

이후 사용법:
```bash
dcprod up -d
dcprod down
dcprod ps
dcprod logs -f
dcprod logs -f backend
```

---

## 4단계: OCI Object Storage 설정

### Customer Secret Key (S3 호환 API 키)
- OCI 콘솔 → 우측 상단 프로필 → 내 사용자 → **Customer secret keys**
- SSH 키와 다른 별도의 키
- 생성 직후 Secret Key 반드시 복사 (이후 재확인 불가)

### Namespace 확인
- OCI 콘솔 → 우측 상단 프로필 → **Tenancy** → Object storage namespace

---

## 5단계: 빌드 및 실행

```bash
cd /opt/iwt
dcprod build --no-cache   # 최초 빌드 (10~20분 소요)
dcprod up -d
dcprod ps                 # 상태 확인
```
ssh -i C:\Users\DK\Downloads\ssh-key-2026-04-15.key ubuntu@144.24.85.97

---

## 6단계: HTTPS 설정 (진행 예정)

Auth0 SPA SDK는 HTTPS 필수. HTTP로는 로그인 불가.

### DuckDNS 무료 도메인 사용
1. [duckdns.org](https://www.duckdns.org) 가입
2. 도메인 생성: `iwt-app.duckdns.org` → IP `144.24.85.97` 연결
3. 인증서 발급:
```bash
dcprod down
sudo certbot certonly --standalone -d iwt-app.duckdns.org
dcprod up -d
```
4. nginx HTTPS 설정 추가 (443 포트, 인증서 경로 연결)
5. docker-compose.prod.yml에 포트 443 추가
6. Auth0 콜백 URL을 `https://iwt-app.duckdns.org`로 변경
7. .env.prod URL 전부 https로 변경 후 재빌드

---

## 알려진 이슈

| 이슈 | 원인 | 상태 |
|------|------|------|
| `Table 'users' already exists` | 9개 워커 동시 테이블 생성 충돌 | 일부 워커 재시작으로 자동 복구됨 |
| `google.generativeai` FutureWarning | 구버전 Gemini 패키지 사용 중 | 추후 `google-genai`로 마이그레이션 필요 |
| HTTPS 미적용 | 인증서 미발급 | 다음 작업 예정 |

---

## 아키텍처

```
[브라우저]
    ↓ :80 (HTTP) / :443 (HTTPS 예정)
[Frontend - nginx:alpine]
    ↓ /api/* proxy_pass
[Backend - FastAPI uvicorn × 9 workers]
    ↓                    ↓
[MySQL 8.0]         [Redis 7]
    ↓
[OCI Object Storage (S3 호환)]
```

---

## GitHub Actions 자동 배포

`.github/workflows/deploy.yml` — main 브랜치 push 시 자동 배포

### 필요한 GitHub Secrets
| Secret | 값 |
|--------|-----|
| `OCI_VM_IP` | `144.24.85.97` |
| `OCI_VM_USER` | `ubuntu` |
| `OCI_SSH_PRIVATE_KEY` | 인스턴스 SSH 프라이빗 키 |

---

*최초 작성: 2026-04-15*
