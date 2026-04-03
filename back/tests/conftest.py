"""
테스트 설정 - SQLite 인메모리 DB 사용
실제 MySQL/Redis 없이 테스트 가능
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.db_models import Base
from app.db.session import get_db


# 인메모리 SQLite 엔진
SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# 테스트용 가짜 인증 유저
MOCK_USER = {
    "sub": "auth0|test_user_001",
    "email": "test@example.com",
    "name": "Test User",
}


def mock_get_current_user():
    return MOCK_USER


@pytest.fixture(scope="function")
def db_session():
    """각 테스트마다 깨끗한 DB 세션"""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI 테스트 클라이언트 (인증 모킹 포함)"""
    from app.main import app
    from app.core.auth import get_current_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = mock_get_current_user

    # 테이블 생성
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_user(db_session):
    """테스트용 유저 생성"""
    from app.models.db_models import User

    user = User(
        id=MOCK_USER["sub"],
        email=MOCK_USER["email"],
        name=MOCK_USER["name"],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def other_user(db_session):
    """다른 테스트 유저"""
    from app.models.db_models import User

    user = User(
        id="auth0|test_user_002",
        email="other@example.com",
        name="Other User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_post(db_session, sample_user):
    """테스트용 게시글"""
    from app.models.db_models import Post
    import json

    post = Post(
        title="제주도 여행기",
        description="# 제주도 3일\n\n아름다운 여행이었다.",
        tags=json.dumps(["제주도", "맛집", "자연"]),
        user_id=sample_user.id,
    )
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)
    return post
