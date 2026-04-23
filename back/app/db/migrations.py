"""
자동 컬럼 마이그레이션 — db_models.py 정의와 실제 DB를 비교해
누락된 컬럼을 자동으로 ALTER TABLE로 추가한다.

처리 범위:
  ✅ 새 테이블  → create_all()이 담당 (이 모듈 아님)
  ✅ 기존 테이블의 누락 컬럼 → 자동 감지 후 ADD COLUMN
  ❌ 컬럼 타입 변경 / 컬럼 삭제 → 수동 (데이터 손실 위험)
"""
import logging
from sqlalchemy import inspect, text
from sqlalchemy import String, Text, Integer, Boolean, Float, DateTime, Numeric

logger = logging.getLogger(__name__)


def _col_type_sql(col) -> str:
    """SQLAlchemy 컬럼 타입 → MySQL DDL 타입 문자열"""
    t = col.type
    if isinstance(t, String):
        return f"VARCHAR({t.length or 255})"
    if isinstance(t, Text):
        return "LONGTEXT"
    if isinstance(t, Boolean):
        return "TINYINT(1)"
    if isinstance(t, Integer):
        return "INT"
    if isinstance(t, Float):
        return "FLOAT"
    if isinstance(t, DateTime):
        return "DATETIME"
    if isinstance(t, Numeric):
        return f"DECIMAL({t.precision or 10},{t.scale or 2})"
    return "TEXT"  # 알 수 없는 타입 fallback


def _col_default_sql(col) -> str:
    """컬럼 default 값 → SQL DEFAULT 절"""
    if col.default is None or col.default.is_callable:
        return ""
    val = col.default.arg
    if isinstance(val, bool):
        return f"DEFAULT {1 if val else 0}"
    if isinstance(val, (int, float)):
        return f"DEFAULT {val}"
    if isinstance(val, str):
        return f"DEFAULT '{val}'"
    return ""


def run_column_migrations(engine, metadata) -> None:
    """
    metadata의 모든 테이블을 순회하며 실제 DB에 없는 컬럼을 추가한다.
    PK, FK 컬럼은 create_all()이 담당하므로 건너뛴다.
    """
    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names())
    applied = 0

    for table_name, table in metadata.tables.items():
        if table_name not in db_tables:
            # 테이블 자체가 없으면 create_all()이 처리하므로 스킵
            continue

        existing_cols = {col["name"] for col in inspector.get_columns(table_name)}

        for col in table.columns:
            if col.name in existing_cols:
                continue
            if col.primary_key:
                continue  # PK는 건드리지 않음

            col_type  = _col_type_sql(col)
            nullable  = "NULL" if col.nullable else "NOT NULL"
            default   = _col_default_sql(col)
            ddl = f"ALTER TABLE `{table_name}` ADD COLUMN `{col.name}` {col_type} {nullable} {default}".strip()

            try:
                with engine.begin() as conn:
                    conn.execute(text(ddl))
                logger.info(f"[migration] {table_name}.{col.name} 추가 완료 ({col_type})")
                applied += 1
            except Exception as e:
                logger.error(f"[migration] {table_name}.{col.name} 추가 실패: {e}")

    if applied == 0:
        logger.info("[migration] 스키마 최신 상태 — 변경 없음")
    else:
        logger.info(f"[migration] 총 {applied}개 컬럼 추가 완료")
