"""검색 API 테스트"""
import pytest
import json
from fastapi.testclient import TestClient


class TestSearchAPI:
    """검색 API 테스트"""

    def test_search_empty(self, client, sample_user):
        res = client.get("/api/v1/search/posts")
        assert res.status_code == 200
        data = res.json()
        assert "posts" in data
        assert "total" in data

    def test_search_by_keyword(self, client, sample_user, sample_post):
        res = client.get("/api/v1/search/posts?q=제주도")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 1

    def test_search_tags_are_list(self, client, sample_user, sample_post):
        """tags가 배열로 반환되는지 검증 (JSON 문자열 파싱 확인)"""
        res = client.get("/api/v1/search/posts?q=제주도")
        assert res.status_code == 200
        data = res.json()
        if data["posts"]:
            tags = data["posts"][0]["tags"]
            assert isinstance(tags, list), f"tags가 list여야 하는데 {type(tags)}입니다"

    def test_search_sort_newest(self, client, sample_user, sample_post):
        res = client.get("/api/v1/search/posts?sort=newest")
        assert res.status_code == 200

    def test_search_sort_popular(self, client, sample_user, sample_post):
        res = client.get("/api/v1/search/posts?sort=popular")
        assert res.status_code == 200

    def test_search_sort_most_liked(self, client, sample_user, sample_post):
        res = client.get("/api/v1/search/posts?sort=most_liked")
        assert res.status_code == 200

    def test_search_suggestions(self, client, sample_user, sample_post):
        res = client.get("/api/v1/search/suggestions?q=제주")
        assert res.status_code == 200
        data = res.json()
        assert "regions" in data
        assert "tags" in data

    def test_search_no_auth_required(self):
        """비로그인 사용자도 검색 가능해야 함 (인증 없이 200 반환)"""
        from app.main import app
        from app.db.session import get_db
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool
        from app.models.db_models import Base

        test_engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        TestSession = sessionmaker(bind=test_engine)
        Base.metadata.create_all(bind=test_engine)

        def override_db():
            db = TestSession()
            try:
                yield db
            finally:
                db.close()

        # 인증 오버라이드 없이 DB만 오버라이드
        app.dependency_overrides[get_db] = override_db
        try:
            with TestClient(app) as anon_client:
                res = anon_client.get("/api/v1/search/posts")
                assert res.status_code == 200, "비로그인 사용자도 검색 가능해야 합니다"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(bind=test_engine)

    def test_search_region_filter(self, client, sample_user, sample_post):
        """지역 필터 동작 확인"""
        res = client.get("/api/v1/search/posts?region=제주")
        assert res.status_code == 200
        data = res.json()
        assert "posts" in data

    def test_search_theme_filter(self, client, sample_user, sample_post):
        """테마 필터 동작 확인"""
        res = client.get("/api/v1/search/posts?theme=맛집")
        assert res.status_code == 200
        data = res.json()
        assert "posts" in data
