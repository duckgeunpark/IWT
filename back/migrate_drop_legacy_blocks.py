"""
v0/v1 레거시 게시글 정리 + Post.blocks/Post.blocks_mode 컬럼 제거.

배경:
  - Phase 1 통합으로 신규 게시글은 모두 blocks_mode='v2' (post_blocks 테이블 사용)
  - v0(post.description 마크다운) / v1(post.blocks JSON) 데이터는 더 이상 재생성 불가
  - 출시 전 정리

동작 (idempotent — 재실행 안전):
  1) DELETE FROM posts WHERE blocks_mode != 'v2' OR blocks_mode IS NULL
  2) ALTER TABLE posts DROP COLUMN blocks (존재하면)
  3) ALTER TABLE posts DROP COLUMN blocks_mode (존재하면)

배포 서버 적용:
  - 자동 마이그레이션(`app/db/migrations.py`)에도 동일 로직이 들어가서 부팅 시 자동 실행됨
  - 본 스크립트는 배포 전 수동 검증용 또는 부팅 외 시점 수동 실행용

사용법:
  python migrate_drop_legacy_blocks.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text, inspect

from app.db.session import get_engine


def _column_exists(conn, table: str, column: str) -> bool:
    inspector = inspect(conn)
    cols = {c["name"] for c in inspector.get_columns(table)}
    return column in cols


def run() -> None:
    engine = get_engine()

    with engine.begin() as conn:
        # 1) 레거시 게시글 삭제
        result = conn.execute(text(
            "SELECT COUNT(*) FROM posts WHERE blocks_mode IS NULL OR blocks_mode <> 'v2'"
        ))
        legacy_count = result.scalar() or 0

        if legacy_count > 0:
            conn.execute(text(
                "DELETE FROM posts WHERE blocks_mode IS NULL OR blocks_mode <> 'v2'"
            ))
            print(f"[migration] 레거시 게시글 {legacy_count}건 삭제 완료")
        else:
            print("[migration] 삭제할 레거시 게시글 없음")

        # 2) Post.blocks 컬럼 제거
        if _column_exists(conn, "posts", "blocks"):
            conn.execute(text("ALTER TABLE posts DROP COLUMN blocks"))
            print("[migration] posts.blocks 컬럼 제거 완료")
        else:
            print("[migration] posts.blocks 컬럼 이미 없음")

        # 3) Post.blocks_mode 컬럼 제거
        if _column_exists(conn, "posts", "blocks_mode"):
            conn.execute(text("ALTER TABLE posts DROP COLUMN blocks_mode"))
            print("[migration] posts.blocks_mode 컬럼 제거 완료")
        else:
            print("[migration] posts.blocks_mode 컬럼 이미 없음")

    print("[migration] 정리 완료.")


if __name__ == "__main__":
    run()
