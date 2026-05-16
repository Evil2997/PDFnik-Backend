import sqlite3
from pathlib import Path

RUN_COLUMNS: tuple[str, ...] = (
    "run_key",
    "status",
    "output_txt",
    "created_at",
)

# Используется только для первичного создания (не в транзакции миграции).
_SCHEMA_SQL_INITIAL = """
CREATE TABLE IF NOT EXISTS runs (
    run_key    TEXT PRIMARY KEY,
    status     TEXT NOT NULL,
    output_txt TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
"""


def _get_existing_columns(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("PRAGMA table_info(runs);").fetchall()
    return [r[1] for r in rows]


def _needs_migration(existing_cols: list[str]) -> bool:
    if not existing_cols:
        return False
    return set(existing_cols) != set(RUN_COLUMNS)


def _run_migration(conn: sqlite3.Connection, existing_cols: list[str]) -> None:
    """
    Выполняет DDL-миграцию: rename → create → copy → drop → index.
    Вызывается из-под BEGIN EXCLUSIVE — атомарная операция.
    """
    conn.execute("ALTER TABLE runs RENAME TO runs_old")

    conn.execute("""
        CREATE TABLE runs (
            run_key    TEXT PRIMARY KEY,
            status     TEXT NOT NULL,
            output_txt TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )
    """)

    # Копируем только те колонки, которые есть в обеих версиях схемы
    cols_old = set(existing_cols)
    copy_cols = ["run_key", "status", "output_txt"]
    if "created_at" in cols_old:
        copy_cols.append("created_at")

    cols_str = ", ".join(copy_cols)
    conn.execute(f"INSERT INTO runs ({cols_str}) SELECT {cols_str} FROM runs_old")
    conn.execute("DROP TABLE runs_old")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)")


def ensure_schema(db_path: Path) -> None:
    db_path = db_path.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # isolation_level=None → autocommit; PRAGMAs не работают внутри транзакций,
    # а BEGIN EXCLUSIVE нужен нам явно только для миграции.
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    try:
        # PRAGMA должны быть вне транзакции
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

        existing_cols = _get_existing_columns(conn)

        if not existing_cols:
            # Чистая БД — создаём схему
            conn.executescript(_SCHEMA_SQL_INITIAL)
            return

        if _needs_migration(existing_cols):
            # FIX: вся миграция в одной EXCLUSIVE транзакции.
            # Старый код использовал executescript() который делает неявный COMMIT
            # до начала работы, что могло оставить БД в полусломанном состоянии
            # при крэше (runs_old существует, runs не существует).
            conn.execute("BEGIN EXCLUSIVE")
            try:
                _run_migration(conn, existing_cols)
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            return

        # Схема актуальна — ничего не делаем (индексы уже созданы при инициализации)

    finally:
        conn.close()
