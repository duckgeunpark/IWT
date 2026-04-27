import os
import time
from typing import Dict, Optional
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import httpx
from sqlalchemy.orm import Session

from app.db.session import get_db

# 콤마로 구분된 관리자 이메일 목록 (예: "admin@example.com,dev@example.com")
_ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.getenv("ADMIN_EMAILS", "").split(",")
    if e.strip()
}

security = HTTPBearer()

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
ALGORITHMS = ["RS256"]

if not AUTH0_DOMAIN or not AUTH0_AUDIENCE:
    raise RuntimeError(
        "AUTH0_DOMAIN과 AUTH0_AUDIENCE 환경변수가 설정되어야 합니다. "
        ".env 파일을 확인해주세요."
    )

# JWKS 캐싱 (매 요청마다 가져오지 않도록)
_jwks_cache: Optional[Dict] = None
_jwks_cache_time: float = 0
JWKS_CACHE_TTL = 3600  # 1시간


async def _get_jwks() -> Dict:
    global _jwks_cache, _jwks_cache_time

    if _jwks_cache and (time.time() - _jwks_cache_time) < JWKS_CACHE_TTL:
        return _jwks_cache

    jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    async with httpx.AsyncClient() as client:
        response = await client.get(jwks_url, timeout=10.0)
        response.raise_for_status()
        _jwks_cache = response.json()
        _jwks_cache_time = time.time()
        return _jwks_cache


def get_token_auth_header(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    return credentials.credentials


async def verify_jwt_token(token: str) -> Dict:
    try:
        jwks = await _get_jwks()
        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }
                break

        if not rsa_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="적절한 공개키를 찾을 수 없습니다.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=ALGORITHMS,
            audience=AUTH0_AUDIENCE,
            issuer=f"https://{AUTH0_DOMAIN}/",
        )
        return payload

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except httpx.HTTPError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="인증 서버에 연결할 수 없습니다.",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"토큰 검증 오류: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _is_user_active(sub: str, db: Session) -> bool:
    """sub에 해당하는 User의 is_active 확인. 레코드가 없으면 True (최초 로그인 등)."""
    if not sub:
        return True
    from app.models.db_models import User
    user = db.query(User).filter(User.id == sub).first()
    if user is None:
        return True
    return user.is_active is not False


async def get_current_user(
    token: str = Depends(get_token_auth_header),
    db: Session = Depends(get_db),
) -> Dict:
    payload = await verify_jwt_token(token)
    if not _is_user_active(payload.get("sub", ""), db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비활성화된 계정입니다. 관리자에게 문의하세요.",
        )
    return payload


async def require_admin(current_user: Dict = Depends(get_current_user)) -> Dict:
    """관리자 전용 엔드포인트 의존성. ADMIN_EMAILS에 email 또는 sub가 있으면 통과."""
    email = (current_user.get("email") or "").lower()
    sub = (current_user.get("sub") or "").lower()
    if not _ADMIN_EMAILS or (email not in _ADMIN_EMAILS and sub not in _ADMIN_EMAILS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다.",
        )
    return current_user


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
) -> Optional[Dict]:
    """인증 선택적 - 토큰 없어도 None 반환, 있으면 검증. 비활성 계정은 익명으로 취급."""
    if not credentials:
        return None
    try:
        payload = await verify_jwt_token(credentials.credentials)
    except HTTPException:
        return None
    if not _is_user_active(payload.get("sub", ""), db):
        return None
    return payload
