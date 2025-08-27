from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# AWS RDS MySQL 설정
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # 개별 환경 변수로 설정
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "password")
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
    MYSQL_DB = os.getenv("MYSQL_DB", "trip_db")
    
    DATABASE_URL = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"

# AWS RDS에 최적화된 엔진 설정
engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_DEBUG", "false").lower() == "true",
    poolclass=QueuePool,
    pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
    pool_pre_ping=True,  # 연결 상태 확인
    pool_recycle=3600,   # 1시간마다 연결 재생성
    connect_args={
        "charset": "utf8mb4",
        "sql_mode": "STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO"
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """데이터베이스 세션 의존성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_engine():
    """엔진 인스턴스 반환"""
    return engine 