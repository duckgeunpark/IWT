#!/usr/bin/env python3

from app.db.session import get_engine
from sqlalchemy import text

def check_database():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            # 테이블 목록 확인
            result = conn.execute(text("SHOW TABLES"))
            print("테이블 목록:")
            for row in result:
                print(f"  - {row[0]}")
            
            # users 테이블 구조 확인
            try:
                result = conn.execute(text("DESCRIBE users"))
                print("\nusers 테이블 구조:")
                for row in result:
                    print(f"  - {row[0]}: {row[1]}")
            except Exception as e:
                print(f"users 테이블이 존재하지 않습니다: {e}")
                
    except Exception as e:
        print(f"데이터베이스 연결 오류: {e}")

if __name__ == "__main__":
    check_database() 