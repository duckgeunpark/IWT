"""소셜 기능 API 테스트 (좋아요, 북마크, 댓글, 팔로우)"""
import pytest


class TestLikeAPI:
    """좋아요 API 테스트"""

    def test_toggle_like(self, client, sample_user, sample_post):
        # 좋아요
        res = client.post(f"/api/v1/posts/{sample_post.id}/like")
        assert res.status_code == 200
        data = res.json()
        assert data["liked"] is True
        assert data["likes_count"] == 1

        # 좋아요 취소
        res = client.post(f"/api/v1/posts/{sample_post.id}/like")
        assert res.status_code == 200
        data = res.json()
        assert data["liked"] is False
        assert data["likes_count"] == 0

    def test_like_nonexistent_post(self, client, sample_user):
        res = client.post("/api/v1/posts/99999/like")
        assert res.status_code == 404


class TestBookmarkAPI:
    """북마크 API 테스트"""

    def test_toggle_bookmark(self, client, sample_user, sample_post):
        # 북마크
        res = client.post(f"/api/v1/posts/{sample_post.id}/bookmark")
        assert res.status_code == 200
        data = res.json()
        assert data["bookmarked"] is True
        assert data["bookmarks_count"] == 1

        # 북마크 취소
        res = client.post(f"/api/v1/posts/{sample_post.id}/bookmark")
        data = res.json()
        assert data["bookmarked"] is False
        assert data["bookmarks_count"] == 0

    def test_get_bookmarked_posts(self, client, sample_user, sample_post):
        # 북마크 추가
        client.post(f"/api/v1/posts/{sample_post.id}/bookmark")

        # 북마크 목록 조회
        res = client.get("/api/v1/posts/bookmarked")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1
        assert len(data["posts"]) == 1
        assert data["posts"][0]["id"] == sample_post.id


class TestCommentAPI:
    """댓글 API 테스트"""

    def test_create_comment(self, client, sample_user, sample_post):
        res = client.post(
            f"/api/v1/posts/{sample_post.id}/comments",
            json={"content": "좋은 여행이네요!"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["content"] == "좋은 여행이네요!"
        assert data["post_id"] == sample_post.id
        assert data["user_id"] == sample_user.id

    def test_get_comments(self, client, sample_user, sample_post):
        # 댓글 2개 작성
        client.post(f"/api/v1/posts/{sample_post.id}/comments", json={"content": "댓글1"})
        client.post(f"/api/v1/posts/{sample_post.id}/comments", json={"content": "댓글2"})

        res = client.get(f"/api/v1/posts/{sample_post.id}/comments")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 2

    def test_delete_comment(self, client, sample_user, sample_post):
        # 댓글 작성
        res = client.post(f"/api/v1/posts/{sample_post.id}/comments", json={"content": "삭제할 댓글"})
        comment_id = res.json()["id"]

        # 삭제
        res = client.delete(f"/api/v1/comments/{comment_id}")
        assert res.status_code == 200

        # 확인
        res = client.get(f"/api/v1/posts/{sample_post.id}/comments")
        assert res.json()["total"] == 0

    def test_create_reply(self, client, sample_user, sample_post):
        # 부모 댓글
        res = client.post(f"/api/v1/posts/{sample_post.id}/comments", json={"content": "부모 댓글"})
        parent_id = res.json()["id"]

        # 답글
        res = client.post(
            f"/api/v1/posts/{sample_post.id}/comments",
            json={"content": "답글입니다", "parent_id": parent_id},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["parent_id"] == parent_id


class TestFollowAPI:
    """팔로우 API 테스트"""

    def test_toggle_follow(self, client, sample_user, other_user):
        # 팔로우
        res = client.post(f"/api/v1/users/{other_user.id}/follow")
        assert res.status_code == 200
        data = res.json()
        assert data["following"] is True
        assert data["followers_count"] == 1

        # 언팔로우
        res = client.post(f"/api/v1/users/{other_user.id}/follow")
        data = res.json()
        assert data["following"] is False
        assert data["followers_count"] == 0

    def test_cannot_follow_self(self, client, sample_user):
        res = client.post(f"/api/v1/users/{sample_user.id}/follow")
        assert res.status_code == 400

    def test_get_followers(self, client, sample_user, other_user):
        # 팔로우
        client.post(f"/api/v1/users/{other_user.id}/follow")

        # 팔로워 목록
        res = client.get(f"/api/v1/users/{other_user.id}/followers")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1

    def test_get_following(self, client, sample_user, other_user):
        # 팔로우
        client.post(f"/api/v1/users/{other_user.id}/follow")

        # 팔로잉 목록
        res = client.get(f"/api/v1/users/{sample_user.id}/following")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1


class TestSocialInfoAPI:
    """게시글 소셜 정보 API 테스트"""

    def test_get_post_social_info(self, client, sample_user, sample_post):
        # 좋아요 + 북마크
        client.post(f"/api/v1/posts/{sample_post.id}/like")
        client.post(f"/api/v1/posts/{sample_post.id}/bookmark")
        client.post(f"/api/v1/posts/{sample_post.id}/comments", json={"content": "테스트"})

        res = client.get(f"/api/v1/posts/{sample_post.id}/social")
        assert res.status_code == 200
        data = res.json()
        assert data["likes_count"] == 1
        assert data["comments_count"] == 1
        assert data["bookmarks_count"] == 1
        assert data["is_liked"] is True
        assert data["is_bookmarked"] is True


class TestFeedAPI:
    """피드 API 테스트"""

    def test_empty_feed(self, client, sample_user):
        res = client.get("/api/v1/feed")
        assert res.status_code == 200
        data = res.json()
        assert data["posts"] == []
        assert data["total"] == 0

    def test_feed_with_following(self, client, sample_user, other_user, db_session):
        from app.models.db_models import Post
        import json

        # other_user의 게시글 생성
        post = Post(title="타인의 여행", description="test", tags=json.dumps([]), user_id=other_user.id)
        db_session.add(post)
        db_session.commit()

        # 팔로우
        client.post(f"/api/v1/users/{other_user.id}/follow")

        # 피드 조회
        res = client.get("/api/v1/feed")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 1
        assert data["posts"][0]["title"] == "타인의 여행"
