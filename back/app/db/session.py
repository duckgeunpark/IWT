from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import settings, DatabaseConfig

# config.py의 settings에서 DATABASE_URL 가져오기
DATABASE_URL = settings.database_url
if not DATABASE_URL or DATABASE_URL == "mysql+pymysql://root:@localhost:3306/iwt_db":
    DATABASE_URL = (
        f"mysql+pymysql://{settings.db_user}:{settings.db_password}"
        f"@{settings.db_host}:{settings.db_port}/{settings.db_name}"
    )

engine_args = DatabaseConfig.get_engine_args()
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_recycle=3600,
    connect_args={
        "charset": "utf8mb4",
    },
    **engine_args,
)

session_args = DatabaseConfig.get_session_args()
SessionLocal = sessionmaker(bind=engine, **session_args)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_engine():
    return engine
