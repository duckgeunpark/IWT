"""
기존 posts 테이블에 status 컬럼을 추가하는 one-off 마이그레이션 스크립트.
신규 환경에서는 실행 불필요 (create_all이 처리함).
기존 운영 DB에서 한 번만 실행하면 됨.

사용법: python migrate_add_status.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from app.db.session import get_engine

def run():
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='posts' AND column_name='status'"
        ))
        if result.fetchone():
            print("status 컬럼이 이미 존재합니다.")
            return

        conn.execute(text(
            "ALTER TABLE posts ADD COLUMN status VARCHAR(50) NOT NULL DEFAULT 'published'"
        ))
        conn.commit()
        print("status 컬럼 추가 완료.")

if __name__ == "__main__":
    run()
