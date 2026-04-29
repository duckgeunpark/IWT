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

# 컬럼 타입 변경이 필요한 케이스 (table, column, 현재 DB 타입, 변경할 DDL)
# TEXT → LONGTEXT처럼 safe한 확장 방향만 여기에 추가
_TYPE_MIGRATIONS = [
    ("posts", "blocks", {"text"}, "ALTER TABLE `posts` MODIFY COLUMN `blocks` LONGTEXT NULL"),
    ("posts", "description", {"text"}, "ALTER TABLE `posts` MODIFY COLUMN `description` LONGTEXT NULL"),
]


def run_type_migrations(engine) -> None:
    """특정 컬럼의 타입을 안전한 방향으로 변경 (TEXT → LONGTEXT 등)"""
    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names())

    for table, column, old_types, ddl in _TYPE_MIGRATIONS:
        if table not in db_tables:
            continue
        cols = {c["name"]: c for c in inspector.get_columns(table)}
        if column not in cols:
            continue
        current_type = str(cols[column]["type"]).lower()
        if any(t in current_type for t in old_types):
            try:
                with engine.begin() as conn:
                    conn.execute(text(ddl))
                logger.info(f"[migration] {table}.{column} 타입 변경 완료 ({current_type} → LONGTEXT)")
            except Exception as e:
                logger.error(f"[migration] {table}.{column} 타입 변경 실패: {e}")


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


# ── 레거시 데이터/컬럼 정리 (Phase 1 통합 후 일회성, 재실행 안전) ──────

def run_legacy_blocks_cleanup(engine) -> None:
    """
    Post.blocks (LONGTEXT JSON, v1 레거시) / Post.blocks_mode (v0/v1/v2 구분자) 정리.

    동작 (idempotent):
      1) blocks_mode 컬럼이 있으면 → 'v2'가 아닌 게시글 DELETE
      2) blocks 컬럼이 있으면 → DROP COLUMN
      3) blocks_mode 컬럼이 있으면 → DROP COLUMN

    배경: Phase 1 통합으로 모든 게시글이 post_blocks 테이블 사용. 레거시 형식은 재생성 불가하므로
          출시 전 일괄 정리. 컬럼이 이미 제거된 환경에서는 자동으로 스킵.
    """
    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names())
    if "posts" not in db_tables:
        return

    cols = {c["name"] for c in inspector.get_columns("posts")}
    has_blocks = "blocks" in cols
    has_blocks_mode = "blocks_mode" in cols

    if not has_blocks and not has_blocks_mode:
        return  # 이미 정리됨

    try:
        with engine.begin() as conn:
            # 1) 레거시 게시글 삭제 (blocks_mode 컬럼이 있을 때만)
            if has_blocks_mode:
                count_row = conn.execute(text(
                    "SELECT COUNT(*) FROM posts WHERE blocks_mode IS NULL OR blocks_mode <> 'v2'"
                )).scalar() or 0
                if count_row > 0:
                    conn.execute(text(
                        "DELETE FROM posts WHERE blocks_mode IS NULL OR blocks_mode <> 'v2'"
                    ))
                    logger.info(f"[migration] 레거시 게시글 {count_row}건 삭제")

            # 2) blocks 컬럼 제거
            if has_blocks:
                conn.execute(text("ALTER TABLE posts DROP COLUMN blocks"))
                logger.info("[migration] posts.blocks 컬럼 제거 완료")

            # 3) blocks_mode 컬럼 제거
            if has_blocks_mode:
                conn.execute(text("ALTER TABLE posts DROP COLUMN blocks_mode"))
                logger.info("[migration] posts.blocks_mode 컬럼 제거 완료")
    except Exception as e:
        logger.error(f"[migration] 레거시 정리 실패: {e}")
