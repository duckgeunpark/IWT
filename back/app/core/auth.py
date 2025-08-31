import os
from typing import Dict
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
import requests

# HTTP Bearer 인증 스키마
security = HTTPBearer()

# Auth0 환경변수 세팅
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")
ALGORITHMS = ["RS256"]

if not AUTH0_DOMAIN or not AUTH0_AUDIENCE:
    print("⚠️ 경고: AUTH0_DOMAIN과 AUTH0_AUDIENCE 환경변수가 설정되지 않았습니다. 개발 모드로 실행됩니다.")
    # 개발 모드용 기본값 설정
    AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "dev.auth0.com")
    AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "dev-audience")

def get_token_auth_header(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Authorization 헤더에서 토큰을 추출합니다.
    """
    return credentials.credentials

def verify_jwt_token(token: str) -> Dict:
    """
    JWT 토큰을 검증하고 payload를 반환합니다.
    """
    try:
        # Auth0 JWKS(공개키) 가져오기
        jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
        jwks = requests.get(jwks_url).json()
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
        # 토큰 검증
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=ALGORITHMS,
            audience=AUTH0_AUDIENCE,
            issuer=f"https://{AUTH0_DOMAIN}/"
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"토큰 검증 오류: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user(token: str = Depends(get_token_auth_header)) -> Dict:
    """
    현재 인증된 사용자 정보를 반환합니다.
    """
    return verify_jwt_token(token) 