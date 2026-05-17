"""
Тесты для SqliteRunRepository и ensure_schema.

Тестируем:
- первичное создание схемы
- upsert + get
- обновление существующей записи
- list_all
- миграция схемы (атомарность)
- get несуществующего ключа
"""

import sqlite3
from pathlib import Path

from main_app.domain.work_with_pdf.actions.files.sqlite.schema import (
    RUN_COLUMNS,
    _get_existing_columns,
    _needs_migration,
    ensure_schema,
)
from main_app.domain.work_with_pdf.actions.files.sqlite.sqlite_repo import SqliteRunRepository

# ---------------------------------------------------------------------------
# ensure_schema
# ---------------------------------------------------------------------------


class TestEnsureSchema:
    def test_creates_table_and_index(self, tmp_db: Path):
        ensure_schema(tmp_db)
        assert tmp_db.exists()

        with sqlite3.connect(str(tmp_db)) as conn:
            cols = _get_existing_columns(conn)
            assert set(cols) == set(RUN_COLUMNS)

            # индекс создан
            indexes = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='runs'"
            ).fetchall()
            index_names = [r[0] for r in indexes]
            assert "idx_runs_status" in index_names

    def test_idempotent(self, tmp_db: Path):
        """Двойной вызов ensure_schema не ломает БД."""
        ensure_schema(tmp_db)
        ensure_schema(tmp_db)

        with sqlite3.connect(str(tmp_db)) as conn:
            cols = _get_existing_columns(conn)
        assert set(cols) == set(RUN_COLUMNS)

    def test_wal_mode(self, tmp_db: Path):
        ensure_schema(tmp_db)
        with sqlite3.connect(str(tmp_db)) as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"

    def test_migration_from_old_schema(self, tmp_db: Path):
        """
        Если в БД старая схема (например без created_at) —
        ensure_schema должна атомарно мигрировать данные.
        """
        tmp_db.parent.mkdir(parents=True, exist_ok=True)

        # Создаём старую схему вручную
        with sqlite3.connect(str(tmp_db)) as conn:
            conn.execute("""
                CREATE TABLE runs (
                    run_key    TEXT PRIMARY KEY,
                    status     TEXT NOT NULL,
                    output_txt TEXT NOT NULL
                )
            """)
            conn.execute("INSERT INTO runs VALUES ('old_key', 'ok', '/tmp/old.txt')")
            conn.commit()

        # Применяем миграцию
        ensure_schema(tmp_db)

        with sqlite3.connect(str(tmp_db)) as conn:
            cols = _get_existing_columns(conn)
            assert "created_at" in cols

            # Данные сохранились
            row = conn.execute("SELECT * FROM runs WHERE run_key='old_key'").fetchone()
            assert row is not None

    def test_needs_migration_true(self):
        assert _needs_migration(["run_key", "status"]) is True

    def test_needs_migration_false_empty(self):
        assert _needs_migration([]) is False

    def test_needs_migration_false_correct(self):
        assert _needs_migration(list(RUN_COLUMNS)) is False


# ---------------------------------------------------------------------------
# SqliteRunRepository
# ---------------------------------------------------------------------------


class TestSqliteRunRepository:
    def test_get_nonexistent_returns_none(self, tmp_db: Path):
        repo = SqliteRunRepository(tmp_db)
        assert repo.get("no_such_key") is None

    def test_upsert_and_get(self, tmp_db: Path):
        repo = SqliteRunRepository(tmp_db)
        row = {"run_key": "k1", "status": "ok", "output_txt": "/tmp/k1.txt"}
        repo.upsert(row)

        result = repo.get("k1")
        assert result is not None
        assert result["run_key"] == "k1"
        assert result["status"] == "ok"
        assert result["output_txt"] == "/tmp/k1.txt"

    def test_upsert_updates_existing(self, tmp_db: Path):
        repo = SqliteRunRepository(tmp_db)
        repo.upsert({"run_key": "k1", "status": "ok", "output_txt": "/tmp/old.txt"})
        repo.upsert({"run_key": "k1", "status": "failed", "output_txt": "/tmp/new.txt"})

        result = repo.get("k1")
        assert result["status"] == "failed"
        assert result["output_txt"] == "/tmp/new.txt"

    def test_list_all_empty(self, tmp_db: Path):
        repo = SqliteRunRepository(tmp_db)
        assert repo.list_all() == []

    def test_list_all_multiple(self, tmp_db: Path):
        repo = SqliteRunRepository(tmp_db)
        repo.upsert({"run_key": "k1", "status": "ok", "output_txt": "/a.txt"})
        repo.upsert({"run_key": "k2", "status": "failed", "output_txt": "/b.txt"})

        rows = repo.list_all()
        assert len(rows) == 2
        keys = {r["run_key"] for r in rows}
        assert keys == {"k1", "k2"}

    def test_created_at_set_automatically(self, tmp_db: Path):
        repo = SqliteRunRepository(tmp_db)
        repo.upsert({"run_key": "k1", "status": "ok", "output_txt": "/a.txt"})
        result = repo.get("k1")
        assert result.get("created_at") is not None

    def test_concurrent_upserts_same_key(self, tmp_db: Path):
        """Несколько последовательных upsert по одному ключу не создают дубли."""
        repo = SqliteRunRepository(tmp_db)
        for i in range(5):
            repo.upsert({"run_key": "same_key", "status": "ok", "output_txt": f"/f{i}.txt"})

        rows = repo.list_all()
        assert len(rows) == 1
        assert rows[0]["output_txt"] == "/f4.txt"
