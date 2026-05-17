"""
Pytest general fixtures.

Run the entire suite:
uv run pytest tests/ -v

Run a single group:
uv run pytest tests/unit/test_run_logic.py -v
"""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub modules for dependencies that are not present in the test environment
# (pdfnik_contracts, reportlab, PIL, etc., are required only in integration tests)
# ---------------------------------------------------------------------------


def _make_stub(name: str) -> ModuleType:
    mod = ModuleType(name)
    sys.modules[name] = mod
    return mod


def _ensure_stubs() -> None:
    """
    Creates minimal stub modules so that imports in the code under test
    do not fail with an ImportError in the absence of heavy dependencies.
    """
    stubs = [
        "faster_whisper",
        "reportlab",
        "reportlab.lib",
        "reportlab.lib.pagesizes",
        "reportlab.pdfbase",
        "reportlab.pdfbase.pdfmetrics",
        "reportlab.pdfbase.ttfonts",
        "reportlab.pdfgen",
        "reportlab.pdfgen.canvas",
        "PIL",
        "PIL.Image",
        "PIL.ImageOps",
        "pdfnik_contracts",
        "pdfnik_contracts.pdf_content",
    ]
    for name in stubs:
        if name not in sys.modules:
            _make_stub(name)

    # reportlab.lib.pagesizes requires A4
    sys.modules["reportlab.lib.pagesizes"].A4 = (595.27, 841.89)

    # faster_whisper.WhisperModel — Stub
    sys.modules["faster_whisper"].WhisperModel = MagicMock


_ensure_stubs()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Path to the temporary SQLite database. The file does not exist until `ensure_schema` is called."""
    return tmp_path / "runs.db"


@pytest.fixture()
def tmp_dir(tmp_path: Path) -> Path:
    """Empty temporary directory."""
    return tmp_path
