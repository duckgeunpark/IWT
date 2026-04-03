"""검색 API 테스트"""
import pytest
import json


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

    def test_search_sort_newest(self, client, sample_user, sample_post):
        res = client.get("/api/v1/search/posts?sort=newest")
        assert res.status_code == 200

    def test_search_sort_popular(self, client, sample_user, sample_post):
        res = client.get("/api/v1/search/posts?sort=popular")
        assert res.status_code == 200

    def test_search_suggestions(self, client, sample_user, sample_post):
        res = client.get("/api/v1/search/suggestions?q=제주")
        assert res.status_code == 200
        data = res.json()
        assert "regions" in data
        assert "tags" in data
