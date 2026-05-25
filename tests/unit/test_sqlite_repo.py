"""
Tests for SqliteRunRepository and ensure_schema.

Covers:
- initial schema creation
- upsert + get
- updating an existing row
- list_all
- schema migration (atomicity)
- get of a non-existent key
- get_summary / save_summary caching
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

            indexes = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='runs'"
            ).fetchall()
            index_names = [r[0] for r in indexes]
            assert "idx_runs_status" in index_names

    def test_idempotent(self, tmp_db: Path):
        """Calling ensure_schema twice does not corrupt the DB."""
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
        """ensure_schema atomically migrates a DB with an outdated schema."""
        tmp_db.parent.mkdir(parents=True, exist_ok=True)

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

        ensure_schema(tmp_db)

        with sqlite3.connect(str(tmp_db)) as conn:
            cols = _get_existing_columns(conn)
            assert "created_at" in cols
            assert "summary" in cols

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
        """Multiple sequential upserts on the same key do not create duplicates."""
        repo = SqliteRunRepository(tmp_db)
        for i in range(5):
            repo.upsert({"run_key": "same_key", "status": "ok", "output_txt": f"/f{i}.txt"})

        rows = repo.list_all()
        assert len(rows) == 1
        assert rows[0]["output_txt"] == "/f4.txt"


class TestSqliteRunRepositorySummary:
    def test_get_summary_returns_none_when_no_row(self, tmp_db: Path):
        repo = SqliteRunRepository(tmp_db)
        assert repo.get_summary("nonexistent") is None

    def test_get_summary_returns_none_before_save(self, tmp_db: Path):
        repo = SqliteRunRepository(tmp_db)
        repo.upsert({"run_key": "k1", "status": "ok", "output_txt": "/a.txt"})
        assert repo.get_summary("k1") is None

    def test_save_and_get_summary(self, tmp_db: Path):
        repo = SqliteRunRepository(tmp_db)
        repo.upsert({"run_key": "k1", "status": "ok", "output_txt": "/a.txt"})
        repo.save_summary("k1", "This is the summary.")
        assert repo.get_summary("k1") == "This is the summary."

    def test_save_summary_overwrites(self, tmp_db: Path):
        repo = SqliteRunRepository(tmp_db)
        repo.upsert({"run_key": "k1", "status": "ok", "output_txt": "/a.txt"})
        repo.save_summary("k1", "First summary.")
        repo.save_summary("k1", "Updated summary.")
        assert repo.get_summary("k1") == "Updated summary."

    def test_summary_isolated_per_run_key(self, tmp_db: Path):
        repo = SqliteRunRepository(tmp_db)
        repo.upsert({"run_key": "k1", "status": "ok", "output_txt": "/a.txt"})
        repo.upsert({"run_key": "k2", "status": "ok", "output_txt": "/b.txt"})
        repo.save_summary("k1", "Summary for k1.")
        assert repo.get_summary("k2") is None
